"""Cinco consultas compartidas por pantalla y exportaciones."""
from datetime import datetime,timedelta
from flask import Blueprint,request,jsonify,send_file,abort
from flask_login import current_user
from backend.auth import proteger
from configuracion import TZ
from datos import rows
from permisos import tiene_permiso
from reportes_excel import resolver_rango_fechas
from reportes_documentos import exportar

reportes_bp=Blueprint('reportes_documentos',__name__,url_prefix='/api/informes')
TIPOS={
 'ventas':('Ventas','reportes.ventas',[('numero_ticket','Ticket'),('fecha_hora','Fecha'),('cliente','Cliente'),('cajero','Responsable'),('metodo_pago','Método'),('total','Total Q')]),
 'productos':('Productos más vendidos','reportes.ventas',[('codigo','Código'),('nombre','Producto'),('cantidad','Unidades'),('total','Vendido Q')]),
 'inventario':('Inventario actual','inventario.ver',[('codigo','Código'),('nombre','Producto'),('categoria','Categoría'),('existencia','Existencia'),('stock_minimo','Mínimo'),('precio_venta','Precio Q')]),
 'compras':('Compras','proveedores.gestionar',[('id_compra','Compra'),('fecha','Fecha'),('numero_factura','Factura'),('proveedor','Proveedor'),('metodo_pago','Método'),('total','Total Q')]),
 'caja':('Movimientos de caja','ventas.registrar',[('id_turno','Turno'),('fecha_hora','Fecha'),('responsable','Responsable'),('tipo','Tipo'),('concepto','Concepto'),('monto','Monto Q')]),
}

def consultar(tipo):
    if tipo not in TIPOS:abort(404)
    titulo,permiso,columnas=TIPOS[tipo]
    if not tiene_permiso(permiso):abort(403)
    desde,hasta=resolver_rango_fechas(request.args,hoy=datetime.now(TZ).date())
    params={'desde':desde,'fin':hasta+timedelta(days=1),'uid':int(current_user.id)}
    alcance='' if tiene_permiso('ventas.todas') else ' AND v.id_usuario=:uid'
    if tipo=='ventas':
        sql='''SELECT v.numero_ticket,v.fecha_hora,c.nombre_razon_social AS cliente,u.nombre AS cajero,v.metodo_pago,v.total
          FROM venta v JOIN cliente c USING(id_cliente) JOIN usuario u USING(id_usuario)
          WHERE v.estado='COMPLETADA' AND v.fecha_hora>=:desde AND v.fecha_hora<:fin'''+alcance+' ORDER BY v.fecha_hora,v.id_venta'
    elif tipo=='productos':
        sql='''SELECT p.codigo,p.nombre,SUM(d.cantidad) AS cantidad,SUM(d.cantidad*d.precio_unitario-d.descuento) AS total
          FROM detalle_venta d JOIN venta v USING(id_venta) JOIN producto p USING(id_producto)
          WHERE v.estado='COMPLETADA' AND v.fecha_hora>=:desde AND v.fecha_hora<:fin'''+alcance+''' GROUP BY p.id_producto,p.codigo,p.nombre ORDER BY cantidad DESC,p.codigo'''
    elif tipo=='inventario':
        sql='''SELECT p.codigo,p.nombre,c.nombre AS categoria,vi.existencia_actual AS existencia,p.stock_minimo,p.precio_venta
          FROM producto p JOIN categoria c USING(id_categoria) JOIN vista_inventario vi USING(id_producto)
          WHERE p.estado=TRUE ORDER BY p.codigo'''
    elif tipo=='compras':
        sql='''SELECT c.id_compra,c.fecha,c.numero_factura,p.razon_social AS proveedor,c.metodo_pago,c.total
          FROM compra c JOIN proveedor p USING(id_proveedor) WHERE c.fecha>=:desde AND c.fecha<:fin ORDER BY c.fecha,c.id_compra'''
    else:
        alcance='' if tiene_permiso('ventas.todas') else ' AND t.id_usuario=:uid'
        sql='''SELECT t.id_turno,m.fecha_hora,u.nombre AS responsable,m.tipo,m.concepto,m.monto
          FROM movimiento_caja m JOIN turno_caja t USING(id_turno) JOIN usuario u ON u.id_usuario=t.id_usuario
          WHERE m.fecha_hora>=:desde AND m.fecha_hora<:fin'''+alcance+' ORDER BY m.fecha_hora,m.id_movimiento_caja'
    datos=rows(sql+' LIMIT 5001',**params)
    if len(datos)>5000:raise ValueError('El reporte supera 5000 filas. Reduce el período antes de consultar o exportar.')
    total=sum((r.get('total',0) for r in datos),0)
    if tipo=='caja':total=sum((r['monto'] if r['tipo']=='INGRESO' else -r['monto'] for r in datos),0)
    nota='Existencias actuales al momento de consultar; el rango de fechas no reconstruye stock histórico.' if tipo=='inventario' else 'Solo ventas completadas; excluye anuladas.' if tipo in ('ventas','productos') else 'Movimientos registrados en el período.'
    if tipo=='caja':nota+=' El neto es ingresos menos egresos; no incluye fondos iniciales ni equivale al arqueo.'
    if not tiene_permiso('ventas.todas') and tipo in ('ventas','productos','caja'):nota+=' Solo operaciones propias.'
    return dict(tipo=tipo,titulo=titulo,columnas=columnas,data=datos,desde=desde,hasta=hasta,nota=nota,total=total,
                cantidad=len(datos),generado=datetime.now(TZ),responsable=current_user.nombre)

@reportes_bp.get('/<tipo>')
@proteger()
def informe(tipo):return jsonify(consultar(tipo))

@reportes_bp.get('/<tipo>/<formato>')
@proteger()
def descargar(tipo,formato):
    if formato not in ('pdf','excel'):abort(404)
    reporte=consultar(tipo)
    return send_file(exportar(reporte,formato),as_attachment=True,
        download_name='PuntoCom_'+tipo+('.pdf' if formato=='pdf' else '.xlsx'),
        mimetype='application/pdf' if formato=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
