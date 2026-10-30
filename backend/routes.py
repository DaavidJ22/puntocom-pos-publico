"""Rutas JSON. Las operaciones críticas reutilizan los servicios transaccionales."""

from datetime import datetime, timedelta
from io import BytesIO

from flask import Blueprint, abort, jsonify, request, send_file
from flask_login import current_user
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from administracion_servicio import asignar_rol, bloquear_admin, operar_registro, preparar_listado
from backend.auth import proteger
from configuracion import TZ
from datos import db, one, rows, value
from inventario_servicio import aprobar_ajuste, registrar_conteo, registrar_movimiento, rechazar_ajuste
from permisos import ROLES, tiene_permiso, usuario_con_permiso
from reportes_excel import generar_excel_ventas, resolver_rango_fechas
from validaciones import entero, money, solo_letras, validar_correo, validar_datos_gestion
from ventas_servicio import anular_venta, registrar_venta
from auditoria import consultar as consultar_auditoria

api = Blueprint('api', __name__, url_prefix='/api')


@api.get('/auditoria')
@proteger('auditoria.ver')
def bitacora():
    return jsonify(consultar_auditoria(request.args))


CRUD = {
    'categorias': ('categoria', 'id_categoria', ['nombre','descripcion'], 'productos.gestionar', 'productos.gestionar', 'productos.gestionar'),
    'clientes': ('cliente', 'id_cliente', ['nombre_razon_social','nit_dpi','telefono','correo','direccion_fiscal'], 'clientes.ver', 'clientes.crear', 'clientes.gestionar'),
    'proveedores': ('proveedor', 'id_proveedor', ['razon_social','nit','contacto','telefono','correo','direccion'], 'proveedores.ver', 'proveedores.gestionar', 'proveedores.gestionar'),
}


def datos():
    contenido = request.get_json()
    if not isinstance(contenido, dict):
        raise ValueError('Se esperaba un objeto JSON.')
    return contenido


def exigir(permiso):
    if not tiene_permiso(permiso):
        abort(403)


def uid():
    return int(current_user.id)


def guardar(resultado=None):
    db.session.commit()
    return jsonify(ok=True, resultado=resultado)


def alcance(alias='v'):
    return ('', {}) if tiene_permiso('ventas.todas') else (f' AND {alias}.id_usuario=:uid', {'uid': uid()})


def productos():
    costo = ',p.costo' if tiene_permiso('costos.ver') else ''
    return rows(f'''SELECT p.id_producto,p.id_categoria,p.codigo,p.codigo_barras,p.nombre,p.marca,
        p.unidad,p.precio_venta,p.stock_minimo,p.estado,c.nombre AS categoria,vi.existencia_actual{costo}
        FROM producto p JOIN categoria c USING(id_categoria) JOIN vista_inventario vi USING(id_producto)
        ORDER BY p.codigo''')


def turno_actual(bloquear=False):
    return one("SELECT * FROM turno_caja WHERE id_usuario=:uid AND estado='ABIERTO' ORDER BY id_turno DESC LIMIT 1"
               + (' FOR UPDATE' if bloquear else ''), uid=uid())


@api.get('/health')
def health():
    try:
        value('SELECT 1')
    except OperationalError:
        db.session.rollback()
        return jsonify(ok=False, servicio='Punto Com API', base_datos='no disponible'), 503
    return jsonify(ok=True, servicio='Punto Com API', base_datos='conectada')


@api.get('/dashboard')
@proteger('configuracion.gestionar')
def dashboard():
    resumen = one('''SELECT
        (SELECT COALESCE(SUM(total),0) FROM venta WHERE fecha_hora::date=CURRENT_DATE AND estado='COMPLETADA') AS ventas,
        (SELECT COUNT(*) FROM venta WHERE fecha_hora::date=CURRENT_DATE AND estado='COMPLETADA') AS nventas,
        (SELECT COUNT(*) FROM producto WHERE estado=TRUE) AS productos,
        (SELECT COUNT(*) FROM cliente) AS clientes,
        (SELECT COUNT(*) FROM vista_inventario vi JOIN producto p USING(id_producto)
          WHERE p.estado=TRUE AND vi.existencia_actual<=vi.stock_minimo) AS bajos,
        (SELECT COALESCE(SUM(d.precio_unitario*d.cantidad-d.descuento-d.costo_unitario_historico*d.cantidad),0)
         FROM detalle_venta d JOIN venta v USING(id_venta)
         WHERE v.estado='COMPLETADA' AND v.fecha_hora::date=CURRENT_DATE) AS ganancia''')
    dias = rows('''SELECT d::date AS fecha,COALESCE(SUM(v.total),0) AS total
        FROM generate_series(CURRENT_DATE-INTERVAL '6 days',CURRENT_DATE,INTERVAL '1 day') d
        LEFT JOIN venta v ON v.fecha_hora::date=d::date AND v.estado='COMPLETADA'
        GROUP BY d ORDER BY d''')
    meses = rows('''SELECT make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int,m.mes,1) AS fecha,
        COALESCE(SUM(v.total),0) AS total FROM generate_series(1,12) AS m(mes)
        LEFT JOIN venta v ON EXTRACT(MONTH FROM v.fecha_hora)=m.mes
          AND EXTRACT(YEAR FROM v.fecha_hora)=EXTRACT(YEAR FROM CURRENT_DATE)
          AND v.estado='COMPLETADA' GROUP BY m.mes ORDER BY m.mes''')
    return jsonify(resumen=resumen, dias=dias, meses=meses,
                   alertas=[p for p in productos() if p['estado'] and p['existencia_actual']<=p['stock_minimo']])


@api.get('/catalogo')
@proteger('ventas.registrar')
def catalogo():
    return jsonify(productos=[p for p in productos() if p['estado']],
                   clientes=rows('SELECT id_cliente,nombre_razon_social FROM cliente WHERE estado=TRUE ORDER BY nombre_razon_social'),
                   turno=turno_actual())


@api.get('/registros/<modulo>')
@proteger()
def registros(modulo):
    if modulo == 'productos':
        exigir('productos.ver')
        registros = productos()
        if tiene_permiso('productos.gestionar'):
            preparar_listado(db.session, modulo, registros, uid())
        return jsonify(data=registros, categorias=rows('SELECT id_categoria,nombre,estado FROM categoria ORDER BY nombre'))
    if modulo == 'usuarios':
        exigir('usuarios.gestionar')
        registros = rows('''SELECT u.id_usuario,u.id_rol,u.nombre,u.correo,u.estado,r.nombre AS rol
            FROM usuario u JOIN rol r USING(id_rol) ORDER BY u.id_usuario''')
        preparar_listado(db.session, modulo, registros, uid())
        return jsonify(data=registros, roles=rows("SELECT * FROM rol WHERE nombre IN ('Administrador','Cajero','Bodeguero')"))
    if modulo not in CRUD:
        abort(404)
    tabla, pk, campos, ver, crear, editar = CRUD[modulo]
    exigir(ver)
    registros = rows(f'SELECT * FROM {tabla} ORDER BY {pk} DESC')
    if tiene_permiso(editar):
        preparar_listado(db.session, modulo, registros, uid())
    return jsonify(data=registros)


@api.post('/registros/<modulo>')
@api.put('/registros/<modulo>/<int:rid>')
@proteger()
def registro_guardar(modulo, rid=None):
    d = datos()
    if modulo == 'productos':
        exigir('productos.gestionar')
        usuario_con_permiso(db.session, uid(), 'productos.gestionar')
        actual = one('SELECT * FROM producto WHERE id_producto=:id FOR UPDATE', id=rid) if rid else None
        if rid and not actual:
            abort(404)
        categoria = entero(d.get('id_categoria'), 1, 'categoría')
        cat = one('SELECT * FROM categoria WHERE id_categoria=:id FOR SHARE', id=categoria)
        if not cat or (not cat['estado'] and (not actual or actual['id_categoria'] != categoria)):
            raise ValueError('Selecciona una categoría activa.')
        valores = dict(id_categoria=categoria, codigo=str(d.get('codigo', '')).strip(),
            codigo_barras=str(d.get('codigo_barras') or '').strip() or None,
            nombre=str(d.get('nombre', '')).strip(), marca=solo_letras(d.get('marca',''), 'Marca', obligatorio=False),
            unidad=str(d.get('unidad', '')).strip(), costo=money(d.get('costo',0)),
            precio_venta=money(d.get('precio_venta',0)), stock_minimo=entero(d.get('stock_minimo',0),0,'mínimo'),
            estado=d.get('estado', True) is True)
        if not valores['codigo'] or not valores['nombre'] or not valores['unidad']:
            raise ValueError('Completa código, nombre y unidad.')
        if valores['costo']<0 or valores['precio_venta']<0:
            raise ValueError('Los importes no pueden ser negativos.')
        if rid:
            db.session.execute(text('UPDATE producto SET '+','.join(f'{c}=:{c}' for c in valores)+' WHERE id_producto=:rid'),{**valores,'rid':rid})
        else:
            rid = value('INSERT INTO producto('+','.join(valores)+') VALUES('+','.join(':'+c for c in valores)+') RETURNING id_producto',**valores)
            stock = entero(d.get('stock_inicial',0),0,'stock inicial')
            if stock:
                registrar_movimiento(db.session, {'id_producto':rid, 'cantidad':stock, 'tipo':'ENTRADA','motivo':'Inventario inicial'},uid())
        return guardar(rid)
    if modulo == 'usuarios':
        exigir('usuarios.gestionar')
        bloquear_admin(db.session, uid())
        if rid:
            asignar_rol(db.session,rid,entero(d.get('id_rol'),1,'rol'),uid())
        else:
            nombre = solo_letras(d.get('nombre'), 'Nombre')
            correo = validar_correo(d.get('correo'))
            clave = str(d.get('password',''))
            rol = entero(d.get('id_rol'),1,'rol')
            if len(clave)<12 or len(nombre)>100 or len(correo)>150:
                raise ValueError('Revisa el nombre, correo y contraseña de al menos 12 caracteres.')
            if value('SELECT nombre FROM rol WHERE id_rol=:id',id=rol) not in ROLES:
                raise ValueError('Rol inválido.')
            rid = value('''INSERT INTO usuario(id_rol,nombre,correo,hash_contrasena,estado)
                VALUES(:rol,:nombre,:correo,:hash,TRUE) RETURNING id_usuario''',rol=rol,nombre=nombre,correo=correo,hash=generate_password_hash(clave))
        return guardar(rid)
    if modulo not in CRUD:
        abort(404)
    tabla, pk, campos, ver, crear, editar = CRUD[modulo]
    permiso = editar if rid else crear
    exigir(permiso)
    usuario_con_permiso(db.session,uid(),permiso)
    valores = validar_datos_gestion(modulo, {c:str(d.get(c) or '').strip() or None for c in campos})
    if rid:
        actual = one(f'SELECT * FROM {tabla} WHERE {pk}=:rid FOR UPDATE',rid=rid)
        if not actual:
            abort(404)
        if modulo=='clientes' and (actual.get('nit_dpi') or '').upper()=='CF' and (
            valores.get('nit_dpi')!='CF' or valores.get('nombre_razon_social','').casefold()!='consumidor final'):
            raise ValueError('No se puede cambiar la identidad de Consumidor Final.')
    if modulo in ('clientes','proveedores'):
        doc = 'nit_dpi' if modulo=='clientes' else 'nit'
        if valores.get(doc):
            db.session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':f'gestion:{modulo}:{valores[doc]}'})
            if one(f'SELECT {pk} FROM {tabla} WHERE UPPER({doc})=:doc AND {pk}<>:rid',doc=valores[doc],rid=rid or -1):
                raise ValueError('Ya existe un registro con ese NIT o DPI.')
    if rid:
        db.session.execute(text(f'UPDATE {tabla} SET '+','.join(f'{c}=:{c}' for c in campos)+f' WHERE {pk}=:rid'),{**valores,'rid':rid})
    else:
        rid=value(f'INSERT INTO {tabla}('+','.join(campos)+') VALUES('+','.join(':'+c for c in campos)+f') RETURNING {pk}',**valores)
    return guardar(rid)


@api.post('/registros/<modulo>/<int:rid>/estado')
@api.delete('/registros/<modulo>/<int:rid>')
@proteger()
def estado(modulo,rid):
    if modulo not in {*CRUD,'productos','usuarios'}:
        abort(404)
    accion = 'eliminar' if request.method=='DELETE' else datos().get('accion')
    operar_registro(db.session,modulo,rid,uid(),accion)
    return guardar()


@api.get('/ventas')
@proteger('ventas.ver')
def ventas():
    condicion, params=alcance()
    return jsonify(data=rows(f'''SELECT v.*,c.nombre_razon_social,u.nombre AS cajero
        FROM venta v JOIN cliente c USING(id_cliente) JOIN usuario u USING(id_usuario)
        WHERE v.numero_ticket ILIKE :q {condicion} ORDER BY v.id_venta DESC LIMIT 250''',q='%'+request.args.get('q','')+'%',**params))


@api.post('/ventas')
@proteger('ventas.registrar')
def cobrar():
    return guardar(registrar_venta(db.session,datos(),uid()))


@api.get('/ventas/<int:vid>')
@proteger('ventas.ver')
def ticket(vid):
    venta=one('''SELECT v.*,c.nombre_razon_social,c.nit_dpi,u.nombre AS cajero
        FROM venta v JOIN cliente c USING(id_cliente) JOIN usuario u USING(id_usuario) WHERE v.id_venta=:id''',id=vid)
    if not venta:
        abort(404)
    if not tiene_permiso('ventas.todas') and venta['id_usuario']!=uid():
        abort(403)
    return jsonify(venta=venta,detalle=rows('''SELECT d.cantidad,d.precio_unitario,d.descuento,p.nombre
        FROM detalle_venta d JOIN producto p USING(id_producto) WHERE d.id_venta=:id ORDER BY d.id_detalle_venta''',id=vid))


@api.post('/ventas/<int:vid>/anular')
@proteger('ventas.anular')
def anular(vid):
    anular_venta(db.session,vid,uid(),datos().get('motivo'))
    return guardar()


@api.route('/caja',methods=['GET','POST'])
@proteger('ventas.registrar')
def caja():
    if request.method=='POST':
        d=datos();accion=d.get('accion')
        usuario_con_permiso(db.session,uid(),'ventas.registrar',bloqueo='NO KEY UPDATE' if accion=='abrir' else 'SHARE')
        turno=turno_actual(True)
        if accion=='abrir':
            if turno:
                raise ValueError('Ya tienes un turno abierto.')
            fondo=money(d.get('fondo_inicial',0))
            if fondo<0:
                raise ValueError('El fondo no puede ser negativo.')
            db.session.execute(text("INSERT INTO turno_caja(id_usuario,fondo_inicial,estado) VALUES(:u,:f,'ABIERTO')"),{'u':uid(),'f':fondo})
        elif accion=='cerrar':
            if not turno:
                raise ValueError('No tienes un turno abierto.')
            contado=money(d.get('efectivo_contado',0))
            if contado<0:
                raise ValueError('El efectivo no puede ser negativo.')
            db.session.execute(text("UPDATE turno_caja SET estado='CERRADO',cierre=NOW(),efectivo_contado=:c WHERE id_turno=:id"),{'c':contado,'id':turno['id_turno']})
        elif accion=='movimiento':
            monto=money(d.get('monto',0));tipo=d.get('tipo');concepto=str(d.get('concepto','')).strip()
            if not turno or monto<=0 or tipo not in ('INGRESO','EGRESO') or not concepto:
                raise ValueError('Revisa turno, tipo, concepto y monto.')
            db.session.execute(text('INSERT INTO movimiento_caja(id_turno,tipo,concepto,monto) VALUES(:t,:tipo,:c,:m)'),{'t':turno['id_turno'],'tipo':tipo,'c':concepto,'m':monto})
        else:
            raise ValueError('Acción de caja inválida.')
        return guardar()
    turno=turno_actual()
    movimientos=rows('SELECT * FROM movimiento_caja WHERE id_turno=:id ORDER BY fecha_hora DESC',id=turno['id_turno']) if turno else []
    saldo=turno['fondo_inicial']+sum(m['monto'] if m['tipo']=='INGRESO' else -m['monto'] for m in movimientos) if turno else 0
    cond,params=alcance('t')
    return jsonify(turno=turno,saldo=saldo,movimientos=movimientos,ultimos=rows(f'''SELECT t.*,u.nombre AS usuario
        FROM turno_caja t JOIN usuario u USING(id_usuario) WHERE TRUE {cond} ORDER BY id_turno DESC LIMIT 30''',**params))


@api.get('/inventario')
@proteger('inventario.ver')
def inventario():
    costo=',mi.costo_unitario' if tiene_permiso('costos.ver') else ''
    return jsonify(data=productos(),movimientos=rows(f'''SELECT mi.id_movimiento_inventario,mi.fecha_hora,mi.tipo,
        mi.cantidad,mi.motivo,p.codigo,p.nombre,u.nombre AS responsable{costo}
        FROM movimiento_inventario mi JOIN producto p USING(id_producto)
        LEFT JOIN usuario u ON u.id_usuario=mi.id_usuario ORDER BY mi.id_movimiento_inventario DESC LIMIT 80'''),
        solicitudes=rows('''SELECT s.*,p.codigo,p.nombre,u.nombre AS solicitante FROM solicitud_ajuste s
            JOIN producto p USING(id_producto) JOIN usuario u ON u.id_usuario=s.id_solicitante ORDER BY s.id_solicitud DESC LIMIT 200'''))


@api.post('/inventario/movimientos')
@proteger('inventario.mover')
def movimiento():
    return guardar(registrar_movimiento(db.session,datos(),uid()))


@api.post('/inventario/conteos')
@proteger('inventario.contar')
def conteo():
    return guardar(registrar_conteo(db.session,datos(),uid()))


@api.post('/inventario/ajustes/<int:aid>/<accion>')
@proteger('inventario.aprobar')
def ajuste(aid,accion):
    if accion=='aprobar':
        aprobar_ajuste(db.session,aid,uid())
    elif accion=='rechazar':
        rechazar_ajuste(db.session,aid,uid(),datos().get('motivo',''))
    else:
        abort(404)
    return guardar()


@api.route('/compras',methods=['GET','POST'])
@proteger('proveedores.gestionar')
def compras():
    if request.method=='POST':
        d=datos();cantidad=entero(d.get('cantidad'),1,'cantidad');costo=money(d.get('costo_unitario',0))
        producto=entero(d.get('id_producto'),1,'producto');proveedor=entero(d.get('id_proveedor'),1,'proveedor')
        metodo=d.get('metodo_pago')
        usuario_con_permiso(db.session,uid(),'proveedores.gestionar')
        if metodo not in ('EFECTIVO','TARJETA','TRANSFERENCIA','CRÉDITO') or costo<0:
            raise ValueError('Método o costo inválido.')
        if not one('SELECT id_proveedor FROM proveedor WHERE id_proveedor=:id AND estado=TRUE FOR SHARE',id=proveedor):
            raise ValueError('Proveedor inactivo o inexistente.')
        if not one('SELECT id_producto FROM producto WHERE id_producto=:id AND estado=TRUE FOR UPDATE',id=producto):
            raise ValueError('Producto inactivo o inexistente.')
        cid=value('''INSERT INTO compra(id_proveedor,id_usuario,numero_factura,metodo_pago,total)
            VALUES(:prov,:u,:factura,:metodo,:total) RETURNING id_compra''',prov=proveedor,u=uid(),factura=str(d.get('numero_factura','')),metodo=metodo,total=money(costo*cantidad))
        detalle_id=value('INSERT INTO detalle_compra(id_compra,id_producto,cantidad,costo_unitario) VALUES(:c,:p,:n,:costo) RETURNING id_detalle_compra',c=cid,p=producto,n=cantidad,costo=costo)
        db.session.execute(text("INSERT INTO movimiento_inventario(id_producto,tipo,cantidad,costo_unitario,motivo,id_usuario,id_detalle_compra) VALUES(:p,'ENTRADA',:n,:c,:m,:u,:detalle)"),{'p':producto,'n':cantidad,'c':costo,'m':f'Compra #{cid}','u':uid(),'detalle':detalle_id})
        db.session.execute(text('UPDATE producto SET costo=:c WHERE id_producto=:p'),{'c':costo,'p':producto})
        return guardar(cid)
    return jsonify(data=rows('''SELECT c.*,p.razon_social,u.nombre AS usuario FROM compra c
        JOIN proveedor p USING(id_proveedor) JOIN usuario u USING(id_usuario) ORDER BY id_compra DESC LIMIT 150'''),
        productos=productos(),proveedores=rows('SELECT id_proveedor,razon_social FROM proveedor WHERE estado=TRUE ORDER BY razon_social'))


def reporte_datos():
    inicio,fin=resolver_rango_fechas(request.args,hoy=datetime.now(TZ).date())
    cond,params=alcance()
    limites=dict(inicio=inicio,fin=fin+timedelta(days=1),**params)
    ventas=rows(f'''SELECT v.id_venta,v.numero_ticket,v.fecha_hora,c.nombre_razon_social AS cliente,u.nombre AS cajero,
        v.metodo_pago,v.total,v.estado FROM venta v JOIN cliente c USING(id_cliente) JOIN usuario u USING(id_usuario)
        WHERE v.fecha_hora>=:inicio AND v.fecha_hora<:fin AND v.estado='COMPLETADA' {cond}
        ORDER BY v.fecha_hora DESC,v.id_venta DESC''',**limites)
    return inicio,fin,ventas,cond,limites


@api.get('/reportes')
@proteger('reportes.ventas')
def reportes():
    inicio,fin,ventas,cond,params=reporte_datos()
    top=rows(f'''SELECT p.nombre,SUM(d.cantidad) AS cantidad,SUM(d.precio_unitario*d.cantidad-d.descuento) AS total
        FROM detalle_venta d JOIN venta v USING(id_venta) JOIN producto p USING(id_producto)
        WHERE v.fecha_hora>=:inicio AND v.fecha_hora<:fin AND v.estado='COMPLETADA' {cond}
        GROUP BY p.id_producto,p.nombre ORDER BY cantidad DESC LIMIT 15''',**params)
    dias=rows(f'''SELECT fecha_hora::date AS fecha,SUM(total) AS total FROM venta v
        WHERE fecha_hora>=:inicio AND fecha_hora<:fin AND estado='COMPLETADA' {cond} GROUP BY fecha_hora::date ORDER BY fecha''',**params)
    return jsonify(ventas=ventas,productos=top,dias=dias,desde=inicio,hasta=fin,
                   resumen=dict(cantidad=len(ventas),total=sum(money(v['total']) for v in ventas)))


@api.get('/reportes/excel')
@proteger('reportes.ventas')
def excel_ventas():
    _,_,ventas,_,_=reporte_datos()
    return send_file(generar_excel_ventas(ventas,zona_horaria=TZ),as_attachment=True,download_name='Ventas_Punto_Com.xlsx')


@api.get('/inventario/excel')
@proteger('inventario.ver')
def excel_inventario():
    libro=Workbook();hoja=libro.active;hoja.title='Inventario'
    campos=['codigo','nombre','categoria','precio_venta','existencia_actual','stock_minimo']+(['costo'] if tiene_permiso('costos.ver') else [])
    hoja.append(campos)
    for p in productos():
        hoja.append([p[c] for c in campos])
        for celda in hoja[hoja.max_row]:
            if isinstance(celda.value,str):
                celda.data_type='s'
    hoja.freeze_panes='A2';salida=BytesIO();libro.save(salida);salida.seek(0)
    return send_file(salida,as_attachment=True,download_name='Inventario_Punto_Com.xlsx')
