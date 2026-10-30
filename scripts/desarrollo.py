"""Entradas para Visual Studio Code: API, frontend y comprobaciones separadas."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion',choices=['api','frontend','celular','compilar','pruebas-api'])
    accion=parser.parse_args().accion
    if accion in ('api','pruebas-api'):
        subprocess.run([sys.executable,str(ROOT/'scripts/postgres_local.py'),'iniciar'],cwd=ROOT,check=True)
        args=['-m','backend.app'] if accion=='api' else ['tests/api/ejecutar.py']
        return subprocess.call([sys.executable,*args],cwd=ROOT)
    node=shutil.which('node')
    herramientas=ROOT/'.local/herramientas.json'
    if not node and herramientas.exists():
        node=json.loads(herramientas.read_text(encoding='utf-8')).get('node')
    if not node or not Path(node).exists():
        raise SystemExit('Instala Node.js y abre de nuevo Visual Studio Code, o configura .local/herramientas.json.')
    args=['build'] if accion=='compilar' else ['--host','127.0.0.1','--port','5173','--strictPort']
    if accion=='celular':
        # Consultar la ruta predeterminada sin enviar datos por la conexión UDP.
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as conexion:
            conexion.connect(('1.1.1.1',80))
            host=conexion.getsockname()[0]
        if not (ROOT/'frontend/dist/index.html').exists():
            subprocess.run([node,str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'build'],cwd=ROOT/'frontend',check=True)
        if not (ROOT/'.local/celular-cert.pem').exists() or not (ROOT/'.local/celular-key.pem').exists():
            raise SystemExit('Primero configura un certificado TLS local para la IP de esta PC.')
        os.environ['PUNTOCOM_MOBILE_TLS']='1'
        print(f'Conecta el celular a la misma Wi-Fi y abre https://{host}:4173',flush=True)
        print('La API debe estar iniciada y este origen debe figurar en FRONTEND_ORIGINS.',flush=True)
        args=['preview','--host',host,'--port','4173','--strictPort']
    return subprocess.call([node,str(ROOT/'frontend/node_modules/vite/bin/vite.js'),*args],cwd=ROOT/'frontend')


if __name__=='__main__':raise SystemExit(main())
