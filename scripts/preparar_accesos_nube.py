"""Crea claves exclusivas de la presentación en un archivo local ignorado por Git."""
from pathlib import Path
import secrets

ROOT=Path(__file__).resolve().parents[1]


def main():
    destino=ROOT/'.local'/'NUBE_PRIVADO.env'
    if destino.exists():
        print('Ya existen claves de presentación; no se reemplazaron.')
        return
    valores={nombre:secrets.token_urlsafe(32) for nombre in
             ('SECRET_KEY','JWT_SECRET_KEY','DEMO_ADMIN_PASSWORD','DEMO_CAJERO_PASSWORD','DEMO_BODEGA_PASSWORD')}
    destino.parent.mkdir(exist_ok=True)
    with destino.open('x',encoding='utf-8') as archivo:
        archivo.write('# Exclusivo de Render; no cargar en el entorno local ni subir a GitHub.\n')
        archivo.write('\n'.join(k+'='+v for k,v in valores.items())+'\n')
    print('Claves nuevas guardadas en .local/NUBE_PRIVADO.env. No se imprimen ni se reutilizan claves locales.')


if __name__=='__main__':main()
