"""Respaldo privado PostgreSQL en .local; no imprime ni pasa claves por argumentos."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import dotenv_values
from configuracion import cargar_configuracion, TZ


def main():
    env = {k: v for k, v in dotenv_values(ROOT / '.env').items() if v is not None}
    env.update(os.environ)
    url = cargar_configuracion(env)['SQLALCHEMY_DATABASE_URI']
    carpeta = ROOT / '.local' / 'respaldos'
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / ('puntocom_' + datetime.now(TZ).strftime('%Y%m%d_%H%M%S_%f') + '.dump')
    runtime = ROOT / '.local' / 'pgsql' / 'bin'
    hijo = dict(os.environ, PGPASSWORD=url.password or '', PGCONNECT_TIMEOUT='5')
    opciones = dict(env=hijo, check=True, stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    with destino.open('xb') as archivo:
        subprocess.run([str(runtime / 'pg_dump.exe'), '-h', url.host, '-p', str(url.port),
                        '-U', url.username, '-d', url.database, '-Fc', '--no-owner', '--no-acl'],
                       stdout=archivo, **opciones)
    # Valida que pg_restore reconoce el archivo y su catálogo; no restaura ni modifica datos.
    with destino.open('rb') as archivo:
        subprocess.run([str(runtime / 'pg_restore.exe'), '--list'], stdin=archivo,
                       stdout=subprocess.DEVNULL, **opciones)
    print('Respaldo creado; catálogo reconocido por pg_restore:', destino.name)
    print('Guardado en .local/respaldos. Archivo privado; no subir al repositorio.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
