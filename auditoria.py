"""Contexto transaccional, accesos y consulta de auditoría sin datos de autenticación."""
from datetime import datetime, time, timedelta
from uuid import uuid4

from flask import g, has_request_context
from sqlalchemy import text

from configuracion import TZ
from datos import db, rows, value
from reportes_excel import resolver_rango_fechas
from validaciones import entero

MODULOS = ('accesos','productos','categorias','clientes','proveedores','usuarios','ventas','compras','caja','inventario','pagos')
ACCIONES = ('CREAR','ACTUALIZAR','ELIMINAR','ACTIVAR','DESACTIVAR','ANULAR','ABRIR_CAJA','CERRAR_CAJA',
            'APROBAR_AJUSTE','RECHAZAR_AJUSTE','CAMBIAR_ROL','CAMBIAR_CLAVE','VACIAR_TABLA',
            'INICIAR_SESION','INGRESO_RECHAZADO','RENOVAR_SESION','CERRAR_SESION','REFRESH_REUTILIZADO',
            'MFA_PREPARADO','MFA_ACTIVADO','MFA_DESACTIVADO','MFA_SOLICITADO','MFA_VERIFICADO',
            'MFA_RECHAZADO','MFA_RESPALDO_USADO','MFA_RESPALDOS_RENOVADOS')


def contexto_usuario(uid, *, origen='api'):
    """Solo el servidor lo llama tras autenticar; SET LOCAL no se filtra al pool."""
    if has_request_context():
        if not getattr(g,'auditoria_solicitud',None):
            g.auditoria_solicitud = str(uuid4())
        solicitud = g.auditoria_solicitud
    else:
        solicitud = str(uuid4())
    db.session.execute(text("""SELECT set_config('puntocom.usuario',:uid,true),
        set_config('puntocom.origen',:origen,true),set_config('puntocom.solicitud',:solicitud,true),
        set_config('puntocom.nombre',COALESCE(u.nombre,''),true),
        set_config('puntocom.rol',COALESCE(r.nombre,''),true)
        FROM (SELECT 1) x LEFT JOIN usuario u ON u.id_usuario=CAST(NULLIF(:uid,'') AS integer)
        LEFT JOIN rol r ON r.id_rol=u.id_rol"""),
        dict(uid=str(int(uid)) if uid is not None else '',origen=origen,solicitud=solicitud))


def registrar_acceso(accion, uid=None, *, origen='api'):
    if accion not in ACCIONES:
        raise ValueError('Evento de auditoría desconocido.')
    contexto_usuario(uid,origen=origen)
    db.session.execute(text("""INSERT INTO bitacora_auditoria(id_usuario,usuario_nombre,usuario_rol,
        origen,solicitud,modulo,entidad,registro,accion,operacion)
        SELECT :uid,COALESCE(u.nombre,'Sin autenticar'),r.nombre,:origen,
        NULLIF(current_setting('puntocom.solicitud',true),'')::uuid,'accesos','sesion',NULL,:accion,'ACCESO'
        FROM (SELECT 1) x LEFT JOIN usuario u ON u.id_usuario=:uid LEFT JOIN rol r ON r.id_rol=u.id_rol"""),
        dict(uid=uid,origen=origen,accion=accion))


def consultar(parametros):
    inicio, fin = resolver_rango_fechas(parametros,hoy=datetime.now(TZ).date())
    pagina = entero(parametros.get('pagina','1'),1,'página')
    limite = entero(parametros.get('limite','25'),1,'límite')
    if limite > 100 or pagina > 100000:
        raise ValueError('La página o el tamaño solicitado supera el límite permitido.')
    filtros = ['fecha_hora>=:inicio','fecha_hora<:fin']
    params = dict(inicio=datetime.combine(inicio,time.min,TZ),
                  fin=datetime.combine(fin+timedelta(days=1),time.min,TZ))
    for campo, opciones in (('modulo',MODULOS),('accion',ACCIONES)):
        valor = parametros.get(campo,'')
        if valor:
            if valor not in opciones:
                raise ValueError('Selecciona un '+campo+' válido.')
            filtros.append(campo+'=:'+campo)
            params[campo] = valor
    if parametros.get('usuario'):
        params['usuario'] = entero(parametros['usuario'],1,'usuario')
        filtros.append('id_usuario=:usuario')
    registro = parametros.get('registro','').strip()
    if len(registro)>100:
        raise ValueError('La referencia no puede superar 100 caracteres.')
    if registro:
        filtros.append('registro=:registro')
        params['registro'] = registro
    condicion = ' AND '.join(filtros)
    total = value('SELECT COUNT(*) FROM bitacora_auditoria WHERE '+condicion,**params)
    eventos = rows('''SELECT id_evento,fecha_hora,id_usuario,usuario_nombre,usuario_rol,origen,solicitud,
        transaccion,modulo,entidad,registro,accion,operacion,antes,despues FROM bitacora_auditoria
        WHERE '''+condicion+' ORDER BY fecha_hora DESC,id_evento DESC LIMIT :limite OFFSET :offset',
        **params,limite=limite,offset=(pagina-1)*limite)
    usuarios = rows('''SELECT DISTINCT ON (id_usuario) id_usuario,usuario_nombre FROM bitacora_auditoria
        WHERE id_usuario IS NOT NULL ORDER BY id_usuario,fecha_hora DESC,id_evento DESC''')
    return dict(data=eventos,total=total,pagina=pagina,limite=limite,paginas=(total+limite-1)//limite,
                desde=inicio,hasta=fin,modulos=MODULOS,acciones=ACCIONES,usuarios=usuarios)
