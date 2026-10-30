"""Abonos registrados en el sistema; no procesa cargos bancarios reales."""
from uuid import UUID
from sqlalchemy import text
from datos import one, value
from validaciones import money, entero
from permisos import usuario_con_permiso


def registrar_abono(session, tipo, documento, data, actor):
    if tipo not in ('ventas','compras') or not isinstance(data,dict):
        raise ValueError('Solicitud de abono inválida.')
    documento=entero(documento,1,'documento')
    usuario=usuario_con_permiso(session,actor,'pagos.cobrar' if tipo=='ventas' else 'pagos.proveedores')
    try:solicitud=str(UUID(str(data.get('solicitud',''))))
    except ValueError:raise ValueError('Falta el identificador de la operación. Vuelve a abrir el formulario.') from None
    monto=money(data.get('monto',0));metodo=data.get('metodo')
    referencia=data.get('referencia','')
    if monto<=0 or monto>money('9999999999.99') or metodo not in ('EFECTIVO','TARJETA','TRANSFERENCIA'):
        raise ValueError('Indica un importe positivo y un método válido.')
    if not isinstance(referencia,str) or len(referencia.strip())>100:
        raise ValueError('La referencia admite hasta 100 caracteres.')
    referencia=referencia.strip()
    tabla,columna=('venta','id_venta') if tipo=='ventas' else ('compra','id_compra')
    doc=one(f'SELECT * FROM {tabla} WHERE {columna}=:id FOR UPDATE',session=session,id=documento)
    if not doc:raise ValueError('El documento no existe.')
    if tipo=='ventas' and usuario['rol']!='Administrador' and doc['id_usuario']!=actor:
        raise PermissionError('No tienes permiso para realizar esta acción')
    anterior=one('SELECT * FROM abono WHERE solicitud=:s',session=session,s=solicitud)
    if anterior:
        if (anterior[columna]!=documento or anterior['id_usuario']!=actor or anterior['monto']!=monto
                or anterior['metodo']!=metodo or anterior['referencia']!=referencia):
            raise ValueError('Ese identificador ya corresponde a otra operación.')
        return dict(id_abono=anterior['id_abono'],repetido=True)
    if doc['metodo_pago']!='CRÉDITO' or (tipo=='ventas' and doc['estado']!='COMPLETADA'):
        raise ValueError('Solo se admiten abonos a documentos vigentes a crédito.')
    pagado=value(f'SELECT COALESCE(SUM(monto),0) FROM abono WHERE {columna}=:id',session=session,id=documento)
    saldo=doc['total']-pagado
    if monto>saldo:raise ValueError('El abono supera el saldo pendiente. Actualiza la cuenta.')
    turno=None
    if metodo=='EFECTIVO':
        turno=one("SELECT id_turno FROM turno_caja WHERE id_usuario=:u AND estado='ABIERTO' ORDER BY id_turno DESC LIMIT 1 FOR UPDATE",session=session,u=actor)
        if not turno:raise ValueError('Abre tu caja para registrar un abono en efectivo.')
        if tipo=='compras':
            disponible=value("""SELECT t.fondo_inicial+COALESCE(SUM(CASE WHEN m.tipo='INGRESO' THEN m.monto ELSE -m.monto END),0)
                FROM turno_caja t LEFT JOIN movimiento_caja m USING(id_turno) WHERE t.id_turno=:t GROUP BY t.id_turno""",session=session,t=turno['id_turno'])
            if monto>disponible:raise ValueError('El efectivo disponible en tu caja es insuficiente.')
    aid=value(f'''INSERT INTO abono(solicitud,{columna},id_usuario,id_turno,monto,metodo,referencia)
        VALUES(:s,:doc,:u,:t,:m,:metodo,:r) RETURNING id_abono''',session=session,
        s=solicitud,doc=documento,u=actor,t=turno['id_turno'] if turno else None,m=monto,metodo=metodo,r=referencia)
    if turno:
        session.execute(text('''INSERT INTO movimiento_caja(id_turno,tipo,concepto,monto,id_abono)
            VALUES(:t,:tipo,:c,:m,:a)'''),dict(t=turno['id_turno'],tipo='INGRESO' if tipo=='ventas' else 'EGRESO',
            c=f'Abono #{aid} · {tabla} #{documento}',m=monto,a=aid))
    return dict(id_abono=aid,saldo=money(saldo-monto),repetido=False)
