"""Cuentas a crédito y su historial de abonos."""
from flask import Blueprint, jsonify, request, abort
from flask_login import current_user
from backend.auth import proteger
from datos import db, rows, one
from permisos import tiene_permiso
from pagos_servicio import registrar_abono

pagos_bp=Blueprint('pagos',__name__,url_prefix='/api/cuentas')


def configuracion(tipo):
    if tipo=='ventas':return 'venta','id_venta','ventas.todas'
    if tipo=='compras':return 'compra','id_compra','pagos.proveedores'
    abort(404)


def verificar(tipo):
    permiso='pagos.cobrar' if tipo=='ventas' else 'pagos.proveedores'
    if not tiene_permiso(permiso):abort(403)


@pagos_bp.get('/<tipo>')
@proteger('pagos.cobrar')
def cuentas(tipo):
    tabla,pk,_=configuracion(tipo);verificar(tipo)
    condiciones="d.metodo_pago='CRÉDITO'"+(" AND d.estado='COMPLETADA'" if tipo=='ventas' else '')
    params={}
    if tipo=='ventas' and not tiene_permiso('ventas.todas'):
        condiciones+=' AND d.id_usuario=:u';params['u']=int(current_user.id)
    contacto,relacion,nombre=('cliente','id_cliente','nombre_razon_social') if tipo=='ventas' else ('proveedor','id_proveedor','razon_social')
    # Totales calculados sobre todas las cuentas; no sobre una página limitada.
    consulta=f'''SELECT d.{pk} AS id,d.{('numero_ticket' if tipo=='ventas' else 'numero_factura')} AS numero,
        c.{nombre} AS contacto,d.total,COALESCE(a.pagado,0) AS pagado,d.total-COALESCE(a.pagado,0) AS saldo
        FROM {tabla} d JOIN {contacto} c USING({relacion})
        LEFT JOIN (SELECT {pk},SUM(monto) AS pagado FROM abono GROUP BY {pk}) a USING({pk}) WHERE {condiciones}'''
    resumen=one(f'SELECT COUNT(*) AS cantidad,COALESCE(SUM(saldo),0) AS pendiente FROM ({consulta}) cuentas',**params)
    try:pagina=int(request.args.get('pagina',1))
    except ValueError:raise ValueError('Página inválida.')
    if not 1<=pagina<=100000:raise ValueError('Página inválida.')
    return jsonify(data=rows(consulta+' ORDER BY d.'+pk+' DESC LIMIT 50 OFFSET :offset',**params,offset=(pagina-1)*50),resumen=resumen,pagina=pagina)


@pagos_bp.route('/<tipo>/<int:documento>/abonos',methods=['GET','POST'])
@proteger('pagos.cobrar')
def abonos(tipo,documento):
    tabla,pk,_=configuracion(tipo);verificar(tipo)
    if request.method=='POST':
        resultado=registrar_abono(db.session,tipo,documento,request.get_json(),int(current_user.id))
        db.session.commit()
        return jsonify(ok=True,resultado=resultado)
    doc=one(f'SELECT * FROM {tabla} WHERE {pk}=:id',id=documento)
    if not doc:abort(404)
    if tipo=='ventas' and not tiene_permiso('ventas.todas') and doc['id_usuario']!=int(current_user.id):abort(403)
    historial=rows(f'''SELECT a.id_abono,a.fecha_hora,a.monto,a.metodo,a.referencia,u.nombre AS responsable
        FROM abono a JOIN usuario u USING(id_usuario) WHERE {pk}=:id ORDER BY a.id_abono DESC''',id=documento)
    return jsonify(data=historial,total=doc['total'],pagado=sum(a['monto'] for a in historial),
        saldo=doc['total']-sum(a['monto'] for a in historial) if doc['metodo_pago']=='CRÉDITO' and doc.get('estado','COMPLETADA')=='COMPLETADA' else 0)
