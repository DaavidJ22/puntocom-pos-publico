"""JWT cortos en memoria del cliente y refresh rotatorio en cookie HttpOnly."""

from datetime import datetime, timezone
import hmac
from functools import wraps
from hashlib import sha256
from uuid import UUID, uuid4

from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import (JWTManager, create_access_token, create_refresh_token,
    decode_token, get_jwt, get_jwt_identity, jwt_required, set_refresh_cookies, unset_jwt_cookies)
from flask_login import LoginManager, UserMixin, current_user
from sqlalchemy import text
from werkzeug.security import check_password_hash

from datos import db, one, value
from backend import mfa
from permisos import PERMISOS, ROLES, tiene_permiso
from auditoria import contexto_usuario, registrar_acceso

auth = Blueprint('auth', __name__, url_prefix='/api/auth')


class UsuarioAPI(UserMixin):
    def __init__(self, fila):
        self.id = str(fila['id_usuario'])
        self.nombre, self.correo, self.rol = fila['nombre'], fila['correo'], fila['rol']


def usuario_publico():
    return dict(id=int(current_user.id), nombre=current_user.nombre, correo=current_user.correo,
                rol=current_user.rol, permisos=[p for p in PERMISOS if tiene_permiso(p)])


def proteger(permiso=None):
    def decorar(funcion):
        @wraps(funcion)
        @jwt_required(locations=['headers'])
        def vista(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if permiso and not tiene_permiso(permiso):
                abort(403)
            if request.method in ('POST','PUT','PATCH','DELETE'):
                contexto_usuario(int(current_user.id))
            return funcion(*args, **kwargs)
        return vista
    return decorar


def huella(jti):
    return sha256(jti.encode()).hexdigest()


def emitir_sesion(uid, **extra):
    """Solo después de contraseña y, cuando está activo, segundo factor comprobados."""
    sid = str(uuid4())
    refresh = create_refresh_token(identity=str(uid),additional_claims={'sid':sid})
    token = decode_token(refresh)
    db.session.execute(text('''INSERT INTO sesion_token(id_sesion,id_usuario,refresh_hash,expira)
        VALUES(CAST(:sid AS uuid),:uid,:hash,:expira)'''),
        dict(sid=sid,uid=uid,hash=huella(token['jti']),
             expira=datetime.fromtimestamp(token['exp'],timezone.utc)))
    respuesta = jsonify(access_token=create_access_token(identity=str(uid),additional_claims={'sid':sid}),**extra)
    set_refresh_cookies(respuesta,refresh)
    return respuesta


def datos_auth():
    datos = request.get_json()
    if not isinstance(datos,dict):
        raise ValueError('Se esperaba un objeto JSON.')
    return datos


def clave_valida(usuario, clave):
    return isinstance(clave,str) and len(clave)<=512 and check_password_hash(usuario['hash_contrasena'],clave)


def fallo_mfa(mensaje='No se pudo verificar el código. Usa uno nuevo o un respaldo sin utilizar.', estado=400):
    registrar_acceso('MFA_RECHAZADO')
    db.session.commit()
    return jsonify(error=mensaje),estado


def instalar_auth(app):
    jwt = JWTManager(app)
    login = LoginManager(app)

    @login.request_loader
    def cargar_usuario(_request):
        try:
            identidad = get_jwt_identity()
            fila = one('''SELECT u.id_usuario,u.nombre,u.correo,r.nombre AS rol
                FROM usuario u JOIN rol r USING(id_rol)
                WHERE u.id_usuario=:id AND u.estado=TRUE''', id=int(identidad))
            return UsuarioAPI(fila) if fila and fila['rol'] in ROLES else None
        except (RuntimeError, TypeError, ValueError):
            return None

    @jwt.token_in_blocklist_loader
    def revocado(_cabecera, token):
        try:
            return not one('''SELECT s.id_sesion FROM sesion_token s
                JOIN usuario u USING(id_usuario) JOIN rol r USING(id_rol)
                WHERE s.id_sesion=CAST(:sid AS uuid) AND s.id_usuario=:uid
                  AND s.revocada IS NULL AND s.expira>NOW() AND u.estado=TRUE
                  AND r.nombre IN ('Administrador','Cajero','Bodeguero')''',
                sid=str(UUID(token.get('sid',''))),
                uid=int(token['sub']))
        except (ValueError, TypeError, KeyError):
            return True

    @jwt.unauthorized_loader
    def sin_token(_motivo):
        return jsonify(error='Inicia sesión para continuar.', code='authentication_required'), 401

    @jwt.invalid_token_loader
    def token_invalido(_motivo):
        return jsonify(error='Token inválido.', code='invalid_token'), 401

    @jwt.expired_token_loader
    def vencido(_cabecera, token):
        return jsonify(error='La sesión necesita renovarse.', code='token_expired'), 401

    @jwt.revoked_token_loader
    def rechazado(_cabecera, _token):
        return jsonify(error='La sesión terminó. Inicia sesión nuevamente.', code='session_revoked'), 401

    app.register_blueprint(auth)


@auth.post('/login')
def login():
    datos = datos_auth()
    correo = str(datos.get('correo', '')).strip().lower()
    if not mfa.limitar('password',correo,maximo=20,segundos=900):
        db.session.commit()
        return jsonify(error='Demasiados intentos. Espera 15 minutos antes de volver a ingresar.'),429
    fila = one('''SELECT u.id_usuario,u.nombre,u.correo,u.hash_contrasena,r.nombre AS rol
        FROM usuario u JOIN rol r USING(id_rol) WHERE lower(u.correo)=:correo AND u.estado=TRUE FOR UPDATE OF u''', correo=correo)
    if not fila or fila['rol'] not in ROLES or not clave_valida(fila,datos.get('password')):
        registrar_acceso('INGRESO_RECHAZADO')
        db.session.commit()
        return jsonify(error='Correo o contraseña incorrectos.'), 401
    mfa.limpiar_limite('password',correo)
    config = mfa.configuracion(fila['id_usuario'])
    if config and config['activo']:
        reto = mfa.crear_reto(fila,config)
        registrar_acceso('MFA_SOLICITADO',fila['id_usuario'])
        db.session.commit()
        respuesta = jsonify(requiere_2fa=True,reto=reto,expira_en=300)
        unset_jwt_cookies(respuesta)
        return respuesta
    respuesta = emitir_sesion(fila['id_usuario'])
    registrar_acceso('INICIAR_SESION',fila['id_usuario'])
    db.session.commit()
    return respuesta


@auth.post('/login/segundo-factor')
def segundo_factor():
    datos = datos_auth()
    reto = str(datos.get('reto',''))
    if len(reto)!=43:
        return jsonify(error='El paso de verificación expiró. Vuelve a ingresar tu contraseña.'),401
    preliminar = one('SELECT id_usuario FROM reto_mfa WHERE huella=:hash',hash=mfa.huella(reto))
    if not preliminar:
        return jsonify(error='El paso de verificación expiró. Vuelve a ingresar tu contraseña.'),401
    uid = preliminar['id_usuario']
    if not mfa.limitar('segundo-factor',uid):
        return fallo_mfa('Demasiados intentos de verificación. Espera 5 minutos.',429)
    usuario = mfa.usuario_bloqueado(uid)
    desafio = one('SELECT *,expira>NOW() AS vigente FROM reto_mfa WHERE huella=:hash FOR UPDATE',hash=mfa.huella(reto))
    config = mfa.configuracion(uid)
    if (not usuario or not config or not desafio or not config['activo'] or not desafio['vigente'] or desafio['consumido']
            or desafio['intentos']>=5 or desafio['version']!=config['version']
            or not hmac.compare_digest(desafio['credencial_hash'],mfa.huella(usuario['hash_contrasena']))):
        return fallo_mfa('El paso de verificación expiró. Vuelve a ingresar tu contraseña.',401)
    db.session.execute(text('UPDATE reto_mfa SET intentos=intentos+1 WHERE huella=:hash'),dict(hash=mfa.huella(reto)))
    factor = mfa.comprobar_factor(uid,config,datos.get('codigo'))
    if not factor:
        return fallo_mfa(estado=401)
    db.session.execute(text('UPDATE reto_mfa SET consumido=NOW() WHERE huella=:hash'),dict(hash=mfa.huella(reto)))
    mfa.limpiar_limite('segundo-factor',uid)
    registrar_acceso('MFA_RESPALDO_USADO' if factor=='respaldo' else 'MFA_VERIFICADO',uid)
    respuesta = emitir_sesion(uid,uso_respaldo=factor=='respaldo')
    registrar_acceso('INICIAR_SESION',uid)
    db.session.commit()
    return respuesta


@auth.get('/mfa')
@proteger()
def estado_mfa():
    uid = int(current_user.id)
    config = mfa.configuracion(uid)
    restantes = value('SELECT COUNT(*) FROM codigo_respaldo WHERE id_usuario=:uid AND usado IS NULL',uid=uid)
    return jsonify(activo=bool(config and config['activo']),respaldos_restantes=restantes)


def reautenticar_configuracion(datos):
    uid = int(current_user.id)
    if not mfa.limitar('configurar-mfa',uid):
        return None,None,fallo_mfa('Demasiados intentos. Espera 5 minutos para configurar tu seguridad.',429)
    usuario = mfa.usuario_bloqueado(uid)
    if not usuario or not clave_valida(usuario,datos.get('password')):
        return None,None,fallo_mfa('No se pudo verificar tu contraseña.')
    return uid,mfa.configuracion(uid),None


@auth.post('/mfa/preparar')
@proteger()
def preparar_mfa():
    datos = datos_auth()
    uid,config,error = reautenticar_configuracion(datos)
    if error:
        return error
    if config and config['activo']:
        return fallo_mfa('2FA ya está activo. No puedes reemplazar el autenticador con solo la contraseña.')
    resultado = mfa.preparar(uid,get_jwt()['sid'])
    registrar_acceso('MFA_PREPARADO',uid)
    db.session.commit()
    return jsonify(resultado)


@auth.post('/mfa/confirmar')
@proteger()
def confirmar_mfa():
    datos = datos_auth()
    uid,config,error = reautenticar_configuracion(datos)
    if error:
        return error
    if (not config or config['activo'] or not config['pendiente_cifrado'] or
            str(config['pendiente_sesion'])!=get_jwt()['sid'] or
            config['pendiente_hasta']<=datetime.now(timezone.utc)):
        return fallo_mfa('La configuración expiró o pertenece a otra sesión. Inicia de nuevo la vinculación.')
    paso = mfa.paso_valido(mfa.descifrar(config['pendiente_cifrado']),datos.get('codigo'))
    if paso is None:
        return fallo_mfa()
    db.session.execute(text('''UPDATE usuario_mfa SET activo=TRUE,secreto_cifrado=pendiente_cifrado,
        pendiente_cifrado=NULL,pendiente_hasta=NULL,pendiente_sesion=NULL,ultimo_paso=:paso,version=version+1
        WHERE id_usuario=:uid'''),dict(paso=paso,uid=uid))
    codigos = mfa.crear_respaldos(uid)
    mfa.revocar_sesiones(uid)
    mfa.limpiar_limite('configurar-mfa',uid)
    registrar_acceso('MFA_ACTIVADO',uid)
    respuesta = emitir_sesion(uid,codigos_respaldo=codigos,activo=True)
    db.session.commit()
    return respuesta


@auth.post('/mfa/cancelar')
@proteger()
def cancelar_mfa():
    uid = int(current_user.id)
    if not mfa.usuario_bloqueado(uid):
        abort(401)
    db.session.execute(text('''UPDATE usuario_mfa SET pendiente_cifrado=NULL,pendiente_hasta=NULL,pendiente_sesion=NULL
        WHERE id_usuario=:uid AND pendiente_sesion=CAST(:sid AS uuid)'''),dict(uid=uid,sid=get_jwt()['sid']))
    db.session.commit()
    return jsonify(ok=True)


@auth.post('/mfa/<accion>')
@proteger()
def modificar_mfa(accion):
    if accion not in ('desactivar','respaldos'):
        abort(404)
    datos = datos_auth()
    uid,config,error = reautenticar_configuracion(datos)
    if error:
        return error
    if not config or not config['activo']:
        return fallo_mfa('2FA no está activo en tu cuenta.')
    factor = mfa.comprobar_factor(uid,config,datos.get('codigo'))
    if not factor:
        return fallo_mfa()
    extra = {}
    if accion=='desactivar':
        db.session.execute(text('''UPDATE usuario_mfa SET activo=FALSE,secreto_cifrado=NULL,
            pendiente_cifrado=NULL,pendiente_hasta=NULL,pendiente_sesion=NULL,ultimo_paso=-1,version=version+1
            WHERE id_usuario=:uid'''),dict(uid=uid))
        db.session.execute(text('DELETE FROM codigo_respaldo WHERE id_usuario=:uid'),dict(uid=uid))
        registrar_acceso('MFA_DESACTIVADO',uid)
    else:
        extra['codigos_respaldo'] = mfa.crear_respaldos(uid)
        registrar_acceso('MFA_RESPALDOS_RENOVADOS',uid)
    mfa.revocar_sesiones(uid)
    mfa.limpiar_limite('configurar-mfa',uid)
    respuesta = emitir_sesion(uid,activo=accion!='desactivar',**extra)
    db.session.commit()
    return respuesta


@auth.post('/refresh')
@jwt_required(refresh=True, locations=['cookies'])
def renovar():
    token = get_jwt()
    sesion = one('''SELECT * FROM sesion_token WHERE id_sesion=CAST(:sid AS uuid) FOR UPDATE''', sid=token['sid'])
    if not sesion or sesion['revocada'] or sesion['refresh_hash'] != huella(token['jti']):
        db.session.execute(text('UPDATE sesion_token SET revocada=NOW() WHERE id_sesion=CAST(:sid AS uuid)'), {'sid': token['sid']})
        registrar_acceso('REFRESH_REUTILIZADO',int(get_jwt_identity()))
        db.session.commit()
        respuesta = jsonify(error='Se detectó reutilización del refresh token. Inicia sesión nuevamente.', code='refresh_reused')
        unset_jwt_cookies(respuesta)
        return respuesta, 401
    # Conserva el vencimiento absoluto de la sesión, aunque se rote el token.
    restante = sesion['expira'] - datetime.now(timezone.utc)
    refresh = create_refresh_token(identity=get_jwt_identity(), additional_claims={'sid': token['sid']}, expires_delta=restante)
    db.session.execute(text('UPDATE sesion_token SET refresh_hash=:hash WHERE id_sesion=CAST(:sid AS uuid)'),
                       {'hash': huella(decode_token(refresh)['jti']), 'sid': token['sid']})
    registrar_acceso('RENOVAR_SESION',int(get_jwt_identity()))
    db.session.commit()
    respuesta = jsonify(access_token=create_access_token(identity=get_jwt_identity(), additional_claims={'sid': token['sid']}))
    set_refresh_cookies(respuesta, refresh)
    return respuesta


@auth.post('/logout')
@jwt_required(refresh=True, locations=['cookies'])
def logout():
    db.session.execute(text('UPDATE sesion_token SET revocada=NOW() WHERE id_sesion=CAST(:sid AS uuid)'), {'sid': get_jwt()['sid']})
    registrar_acceso('CERRAR_SESION',int(get_jwt_identity()))
    db.session.commit()
    respuesta = jsonify(ok=True)
    unset_jwt_cookies(respuesta)
    return respuesta


@auth.get('/me')
@proteger()
def me():
    return jsonify(usuario_publico())
