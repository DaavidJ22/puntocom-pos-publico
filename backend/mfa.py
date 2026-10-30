"""TOTP, recuperación de un solo uso y límites persistentes, sin emitir sesiones."""
import base64
from hashlib import sha256
import hmac
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app
import pyotp
import qrcode
from qrcode.image.svg import SvgPathImage
from sqlalchemy import text

from auditoria import registrar_acceso
from datos import db, one, value


def huella(valor):
    return sha256(valor.encode()).hexdigest()


def cifrador():
    # Clave de propósito separado, derivada del secreto estable del servidor.
    # No depende de JWT_SECRET_KEY, ni se envía al navegador.
    origen = current_app.config.get('MFA_ENCRYPTION_KEY') or current_app.config['SECRET_KEY']
    if len(origen)<32:
        raise ValueError('Configura una clave privada estable de al menos 32 caracteres para utilizar 2FA.')
    clave = HKDF(algorithm=hashes.SHA256(),length=32,salt=b'puntocom-mfa-v1',
                 info=b'cifrado-semilla-totp').derive(origen.encode())
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar(secreto):
    return cifrador().encrypt(secreto.encode()).decode()


def descifrar(secreto):
    try:
        return cifrador().decrypt(secreto.encode()).decode()
    except InvalidToken:
        raise ValueError('No se pudo leer la configuración 2FA. Utiliza un código de respaldo y consulta al administrador.') from None


def limitar(ambito, identificador, *, maximo=10, segundos=300):
    """Incremento atómico compartido por procesos. El llamador confirma también los fallos."""
    clave = huella(ambito+':'+str(identificador))
    db.session.execute(text("DELETE FROM limite_auth WHERE inicio<NOW()-INTERVAL '1 day'"))
    fila = one('''INSERT INTO limite_auth(clave,intentos) VALUES(:clave,1)
        ON CONFLICT(clave) DO UPDATE SET
          intentos=CASE WHEN limite_auth.inicio<NOW()-make_interval(secs=>:segundos) THEN 1
                        ELSE LEAST(limite_auth.intentos+1,:maximo+1) END,
          inicio=CASE WHEN limite_auth.inicio<NOW()-make_interval(secs=>:segundos) THEN NOW() ELSE limite_auth.inicio END
        RETURNING intentos''',clave=clave,segundos=segundos,maximo=maximo)
    return fila['intentos']<=maximo


def limpiar_limite(ambito, identificador):
    db.session.execute(text('DELETE FROM limite_auth WHERE clave=:clave'),{'clave':huella(ambito+':'+str(identificador))})


def usuario_bloqueado(uid):
    # Todas las operaciones de autenticación/configuración bloquean primero usuario.
    return one('''SELECT u.*,r.nombre AS rol FROM usuario u JOIN rol r USING(id_rol)
        WHERE u.id_usuario=:uid AND u.estado=TRUE AND r.nombre IN ('Administrador','Cajero','Bodeguero')
        FOR UPDATE OF u''',uid=uid)


def configuracion(uid):
    return one('SELECT * FROM usuario_mfa WHERE id_usuario=:uid',uid=uid)


def paso_valido(secreto, codigo, ultimo=-1, ahora=None):
    if not isinstance(codigo,str) or not re.fullmatch(r'[0-9]{6}',codigo):
        return None
    paso = int(time.time() if ahora is None else ahora)//30
    totp = pyotp.TOTP(secreto)
    for candidato in (paso,paso-1,paso+1):
        if candidato>ultimo and hmac.compare_digest(totp.at(candidato*30),codigo):
            return candidato
    return None


def comprobar_factor(uid, config, codigo):
    """Llamar con usuario bloqueado; consume TOTP o respaldo dentro de la transacción."""
    codigo = str(codigo or '').strip()
    if re.fullmatch(r'[0-9]{6}',codigo):
        paso = paso_valido(descifrar(config['secreto_cifrado']),codigo,config['ultimo_paso'])
        if paso is None:
            return None
        db.session.execute(text('UPDATE usuario_mfa SET ultimo_paso=:paso WHERE id_usuario=:uid'),dict(paso=paso,uid=uid))
        return 'totp'
    respaldo = codigo.replace('-','').replace(' ','').upper()
    if not re.fullmatch(r'[0-9A-F]{20}',respaldo):
        return None
    consumido = value('''UPDATE codigo_respaldo SET usado=NOW()
        WHERE id_usuario=:uid AND huella=:hash AND usado IS NULL RETURNING id_codigo''',
        uid=uid,hash=huella(str(uid)+':'+respaldo))
    return 'respaldo' if consumido else None


def crear_respaldos(uid):
    db.session.execute(text('DELETE FROM codigo_respaldo WHERE id_usuario=:uid'),dict(uid=uid))
    codigos = []
    for _ in range(10):
        codigo = secrets.token_hex(10).upper()
        db.session.execute(text('INSERT INTO codigo_respaldo(id_usuario,huella) VALUES(:uid,:hash)'),
                           dict(uid=uid,hash=huella(str(uid)+':'+codigo)))
        codigos.append('-'.join(codigo[i:i+5] for i in range(0,20,5)))
    return codigos


def revocar_sesiones(uid):
    db.session.execute(text('UPDATE sesion_token SET revocada=NOW() WHERE id_usuario=:uid AND revocada IS NULL'),dict(uid=uid))
    db.session.execute(text('UPDATE reto_mfa SET consumido=NOW() WHERE id_usuario=:uid AND consumido IS NULL'),dict(uid=uid))


def crear_reto(usuario, config):
    secreto = secrets.token_urlsafe(32)
    db.session.execute(text("DELETE FROM reto_mfa WHERE expira<NOW()-INTERVAL '1 day'"))
    db.session.execute(text('''INSERT INTO reto_mfa(huella,id_usuario,version,credencial_hash,expira)
        VALUES(:hash,:uid,:version,:credencial,NOW()+INTERVAL '5 minutes')'''),
        dict(hash=huella(secreto),uid=usuario['id_usuario'],version=config['version'],
             credencial=huella(usuario['hash_contrasena'])))
    return secreto


def preparar(uid, sid):
    secreto = pyotp.random_base32()
    db.session.execute(text('''INSERT INTO usuario_mfa(id_usuario,pendiente_cifrado,pendiente_hasta,pendiente_sesion)
        VALUES(:uid,:secreto,NOW()+INTERVAL '10 minutes',CAST(:sid AS uuid))
        ON CONFLICT(id_usuario) DO UPDATE SET pendiente_cifrado=EXCLUDED.pendiente_cifrado,
          pendiente_hasta=EXCLUDED.pendiente_hasta,pendiente_sesion=EXCLUDED.pendiente_sesion'''),
        dict(uid=uid,secreto=cifrar(secreto),sid=sid))
    correo = value('SELECT correo FROM usuario WHERE id_usuario=:uid',uid=uid)
    uri = pyotp.TOTP(secreto).provisioning_uri(name=correo,issuer_name='Punto Com')
    qr = qrcode.make(uri,image_factory=SvgPathImage)
    imagen = base64.b64encode(qr.to_string()).decode()
    return dict(secreto=secreto,qr='data:image/svg+xml;base64,'+imagen,expira_en=600)
