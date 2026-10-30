"""Genera la configuración pública Vercel cuando se conoce la URL real de la API."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def configuracion(api_url):
    url = urlsplit(api_url.strip())
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.path not in ('','/') or url.query or url.fragment or url.port
            or not url.hostname.endswith('.onrender.com')):
        raise ValueError('Indica únicamente el origen HTTPS real de la API en Render, sin rutas ni credenciales.')
    origen = 'https://' + url.hostname
    return {
        '$schema': 'https://openapi.vercel.sh/vercel.json',
        'framework': 'vite', 'buildCommand': 'pnpm run build', 'outputDirectory': 'dist',
        'installCommand': 'pnpm install --frozen-lockfile',
        'rewrites': [
            {'source': '/api/:path*', 'destination': origen + '/api/:path*'},
            {'source': '/((?!api/|assets/).*)', 'destination': '/index.html'},
        ],
        'headers': [
            {'source': '/api/:path*', 'headers': [
                {'key': 'Cache-Control', 'value': 'no-store'},
                {'key': 'CDN-Cache-Control', 'value': 'no-store'},
            ]},
            {'source': '/(.*)', 'headers': [
                {'key': 'X-Content-Type-Options', 'value': 'nosniff'},
                {'key': 'Referrer-Policy', 'value': 'same-origin'},
            ]},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', required=True)
    args = parser.parse_args()
    config = configuracion(args.api_url)
    destino = ROOT / 'frontend' / 'vercel.json'
    destino.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Configuración del frontend generada para:', args.api_url)
    print('No contiene secretos. Las peticiones /api conservan el origen y las cookies del navegador.')


if __name__ == '__main__':
    main()
