"""Configuración del entorno, sin conexiones ni lectura de secretos al importar."""

import os
import secrets
from zoneinfo import ZoneInfo

from sqlalchemy.engine import URL, make_url


TZ = ZoneInfo('America/Guatemala')


def _booleano(entorno, nombre, predeterminado=False):
    valor = entorno.get(nombre)
    if valor is None or not valor.strip():
        return predeterminado
    valor = valor.strip().lower()
    if valor in ('1', 'true', 'yes', 'on'):
        return True
    if valor in ('0', 'false', 'no', 'off'):
        return False
    raise ValueError(f'{nombre} debe ser true o false.')


def cargar_configuracion(entorno=None):
    """Permite pasar un entorno explícito para probar sin acceder al .env real."""
    entorno = os.environ if entorno is None else entorno
    ambiente = entorno.get('APP_ENV', 'development').strip().lower()
    if ambiente not in ('development', 'testing', 'production'):
        raise ValueError('APP_ENV debe ser development, testing o production.')
    produccion = ambiente == 'production'
    clave = entorno.get('SECRET_KEY', '').strip()
    if produccion and not clave:
        raise ValueError('Configura SECRET_KEY antes de iniciar en producción.')
    debug = _booleano(entorno, 'APP_DEBUG')
    if produccion and debug:
        raise ValueError('APP_DEBUG no se puede habilitar en producción.')
    direccion = entorno.get('DATABASE_URL', '').strip()
    if direccion:
        try:
            uri = make_url(direccion)
            if uri.drivername not in ('postgres', 'postgresql', 'postgresql+psycopg2'):
                raise ValueError()
            if not uri.host or not uri.database or not uri.username:
                raise ValueError()
            if uri.port is not None and not 1 <= uri.port <= 65535:
                raise ValueError()
            uri = uri.set(drivername='postgresql+psycopg2')
        except Exception:
            raise ValueError('DATABASE_URL debe ser una conexión PostgreSQL válida.') from None
        if produccion:
            ssl = uri.query.get('sslmode', 'require')
            if ssl not in ('require', 'verify-ca', 'verify-full'):
                raise ValueError('DATABASE_URL debe exigir una conexión TLS en producción.')
            uri = uri.update_query_dict({'sslmode': ssl})
    else:
        try:
            puerto = int(entorno.get('DB_PORT', '5433'))
            if not 1 <= puerto <= 65535:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError('DB_PORT debe ser un puerto válido.') from None
        uri = URL.create('postgresql+psycopg2', username=entorno.get('DB_USER', 'postgres'),
                         password=entorno.get('DB_PASSWORD', ''), host=entorno.get('DB_HOST', '127.0.0.1'),
                         port=puerto, database=entorno.get('DB_NAME', 'puntocom_pos'))
    cookies_seguras = _booleano(entorno, 'SESSION_COOKIE_SECURE', produccion)
    if produccion and not cookies_seguras:
        raise ValueError('SESSION_COOKIE_SECURE debe ser true en producción.')
    return {
        'APP_ENV': ambiente,
        'SECRET_KEY': clave or ('dev-only-' + secrets.token_hex(32)),
        'MFA_ENCRYPTION_KEY': entorno.get('MFA_ENCRYPTION_KEY','').strip(),
        'DEBUG': debug,
        'SQLALCHEMY_DATABASE_URI': uri,
        'TRUST_PROXY': _booleano(entorno, 'TRUST_PROXY'),
        # TIMESTAMP/CURRENT_DATE/NOW() comparten el horario del negocio.
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_pre_ping': True,
            # Tras esperar un bloqueo, la siguiente consulta de stock debe ver
            # los movimientos recién confirmados por la otra transacción.
            'isolation_level': 'READ COMMITTED',
            'connect_args': {'options': '-c timezone=America/Guatemala'},
        },
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': cookies_seguras,
        'REMEMBER_COOKIE_HTTPONLY': True,
        'REMEMBER_COOKIE_SAMESITE': 'Lax',
        'REMEMBER_COOKIE_SECURE': cookies_seguras,
        'MAX_CONTENT_LENGTH': 4 * 1024 * 1024,
    }
