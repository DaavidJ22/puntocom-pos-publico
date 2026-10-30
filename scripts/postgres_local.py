"""Controla exclusivamente PostgreSQL portable dentro de .local de este proyecto."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
if os.name == 'nt' and LOCAL.exists():
    # initdb de Windows puede interpretar rutas con ñ usando una página de códigos
    # distinta. La ruta corta apunta a los mismos archivos y evita esa ambigüedad.
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(str(LOCAL), buffer, len(buffer)):
        LOCAL = Path(buffer.value)
DATA = LOCAL / 'pgdata'
BIN = LOCAL / 'pgsql' / 'bin'
PORT = 55432
MARCA = LOCAL / 'preparacion.json'
sys.path.insert(0, str(ROOT))


def ejecutar(nombre, *argumentos, comprobar=True):
    return subprocess.run(
        [str(BIN / (nombre + '.exe')), *map(str, argumentos)],
        cwd=LOCAL, check=comprobar,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )


def iniciar():
    if not (DATA / 'PG_VERSION').exists():
        raise RuntimeError('Primero prepara la base local.')
    if ejecutar('pg_ctl', '-D', DATA, 'status', comprobar=False).returncode == 0:
        return
    ejecutar('pg_ctl', '-D', DATA, '-l', LOCAL / 'postgres.log', '-w', '-t', '30', 'start')


def preparar():
    import psycopg2
    from psycopg2 import sql
    from werkzeug.security import generate_password_hash

    if MARCA.exists():
        print('La preparación ya se completó. No se modificaron datos ni credenciales.')
        return
    if (ROOT / '.env').exists() or DATA.exists():
        raise RuntimeError('Hay configuración o datos previos. Revisarlos antes de preparar; no se sobrescriben.')
    LOCAL.mkdir(exist_ok=True)
    clave_postgres = secrets.token_urlsafe(36)
    clave_app = secrets.token_urlsafe(36)
    archivo_clave = LOCAL / 'postgres.password'
    archivo_clave.write_text(clave_postgres + '\n', encoding='ascii')
    ejecutar('initdb', '-D', DATA, '-U', 'postgres', '--encoding=UTF8', '--locale=C',
             '--auth=scram-sha-256', '--pwfile', archivo_clave)
    with (DATA / 'postgresql.conf').open('a', encoding='utf-8') as archivo:
        archivo.write("\n# Instancia exclusiva de desarrollo Punto Com\n"
                      "listen_addresses = '127.0.0.1'\n"
                      f"port = {PORT}\n"
                      "timezone = 'America/Guatemala'\n"
                      "log_timezone = 'America/Guatemala'\n")
    iniciar()
    conexion = psycopg2.connect(host='127.0.0.1', port=PORT, user='postgres',
                               password=clave_postgres, dbname='postgres', connect_timeout=5)
    try:
        conexion.autocommit = True
        with conexion.cursor() as cursor:
            cursor.execute('SHOW data_directory')
            if not os.path.samefile(cursor.fetchone()[0], DATA):
                raise RuntimeError('El servidor no pertenece a esta copia del proyecto.')
            # CREATEDB permite la suite existente de integración sobre bases desechables.
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN CREATEDB NOSUPERUSER PASSWORD %s').format(
                sql.Identifier('puntocom_local')), (clave_app,))
            cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING %s').format(
                sql.Identifier('puntocom_pos_local'), sql.Identifier('puntocom_local')), ('UTF8',))
    finally:
        conexion.close()
    conexion = psycopg2.connect(host='127.0.0.1', port=PORT, user='puntocom_local',
                               password=clave_app, dbname='puntocom_pos_local', connect_timeout=5)
    accesos = []
    try:
        # Cada script incluye sus propias restricciones; solo se cargan en esta base nueva.
        conexion.autocommit = True
        with conexion.cursor() as cursor:
            for nombre in ('01_esquema.sql', '02_datos_iniciales.sql', '04_roles_inventario.sql', '05_sesiones_token.sql', '06_integridad_trazabilidad.sql'):
                cursor.execute((ROOT / 'sql' / nombre).read_text(encoding='utf-8'))
        conexion.autocommit = False
        with conexion.cursor() as cursor:
            for nombre, correo, rol in (
                ('Administrador Local', 'admin@puntocom.local', 'Administrador'),
                ('Cajero Local', 'cajero@puntocom.local', 'Cajero'),
                ('Bodeguero Local', 'bodega@puntocom.local', 'Bodeguero'),
            ):
                clave = secrets.token_urlsafe(18)
                cursor.execute('''INSERT INTO usuario(id_rol,nombre,correo,hash_contrasena,estado)
                    SELECT id_rol,%s,%s,%s,TRUE FROM rol WHERE nombre=%s''',
                    (nombre, correo, generate_password_hash(clave), rol))
                accesos.append(f'{rol}\nCorreo: {correo}\nContraseña: {clave}\n')
        conexion.commit()
    finally:
        conexion.close()
    (ROOT / '.env').write_text(
        'APP_ENV=development\nAPP_DEBUG=false\n'
        f'SECRET_KEY={secrets.token_hex(32)}\nSESSION_COOKIE_SECURE=false\n'
        f'DB_HOST=127.0.0.1\nDB_PORT={PORT}\nDB_NAME=puntocom_pos_local\n'
        f'DB_USER=puntocom_local\nDB_PASSWORD={clave_app}\n', encoding='utf-8')
    (LOCAL / 'ACCESO_LOCAL.txt').write_text(
        'PUNTO COM - Accesos exclusivos de desarrollo local\n'
        'Dirección: http://127.0.0.1:5173\n'
        'No compartir este archivo ni usar estas cuentas en producción.\n\n'
        + '\n'.join(accesos), encoding='utf-8')
    MARCA.write_text(json.dumps({'database': 'puntocom_pos_local', 'port': PORT,
                                'host': '127.0.0.1', 'runtime': 'PostgreSQL 17.11'}, indent=2), encoding='utf-8')
    print('Base independiente preparada con tres perfiles locales y productos DEMO.')
    print('Los accesos se guardaron en .local/ACCESO_LOCAL.txt; no se imprimen contraseñas.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=('preparar', 'iniciar', 'detener', 'estado', 'aplicacion'))
    accion = parser.parse_args().accion
    if accion == 'preparar':
        preparar()
    elif accion in ('iniciar', 'aplicacion'):
        iniciar()
        if accion == 'aplicacion':
            print('Aplicación local: http://127.0.0.1:5000/login', flush=True)
            return subprocess.call([sys.executable, str(ROOT / 'app.py')], cwd=ROOT)
    elif accion == 'detener':
        ejecutar('pg_ctl', '-D', DATA, '-m', 'fast', '-w', 'stop')
    else:
        return ejecutar('pg_ctl', '-D', DATA, 'status', comprobar=False).returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
