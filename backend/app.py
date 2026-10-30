"""Servidor JSON separado. Ejecutar: python -m backend.app."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from urllib.parse import urlsplit

from configuracion import cargar_configuracion
from datos import db


class JSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(obj):
        if isinstance(obj, Decimal):
            return str(obj)  # conservar importes sin pérdida decimal en el transporte
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return DefaultJSONProvider.default(obj)


def create_app(config=None):
    if config is None:
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')
        config = cargar_configuracion()
    app = Flask(__name__, static_folder=None)
    app.json = JSONProvider(app)
    app.config.update(config)
    if app.config.get('TRUST_PROXY'):
        # Render termina TLS delante de Gunicorn. No confiar en Host ni en IP
        # enviados por visitantes; solo en el protocolo del último proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    produccion = app.config.get('APP_ENV') == 'production'
    origenes = {o.strip().rstrip('/') for o in
                (os.environ.get('FRONTEND_ORIGIN', '') + ',' + os.environ.get('FRONTEND_ORIGINS', '')).split(',') if o.strip()}
    if produccion and any(urlsplit(o).scheme != 'https' or not urlsplit(o).netloc
                          or urlsplit(o).path or urlsplit(o).query or urlsplit(o).fragment for o in origenes):
        raise ValueError('FRONTEND_ORIGIN y FRONTEND_ORIGINS deben contener orígenes HTTPS en producción.')
    app.config.update(
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY') or app.config['SECRET_KEY'],
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=10),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(hours=8),
        JWT_COOKIE_SECURE=app.config['SESSION_COOKIE_SECURE'],
        JWT_COOKIE_SAMESITE='Strict', JWT_COOKIE_CSRF_PROTECT=True,
        JWT_REFRESH_COOKIE_PATH='/api/auth', JWT_REFRESH_CSRF_COOKIE_PATH='/',
        JWT_TOKEN_LOCATION=['headers'],
    )
    db.init_app(app)
    from backend.auth import instalar_auth
    from backend.routes import api
    instalar_auth(app)
    app.register_blueprint(api)
    from backend.reportes import reportes_bp
    app.register_blueprint(reportes_bp)
    from backend.externos import externos_bp
    app.register_blueprint(externos_bp)
    from backend.pagos import pagos_bp
    app.register_blueprint(pagos_bp)

    @app.before_request
    def comprobar_origen():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origen = request.headers.get('Origin')
            permitidos = set(origenes)
            if not produccion:
                permitidos.update({'http://127.0.0.1:5173', 'http://localhost:5173', request.host_url.rstrip('/')})
            if origen and origen not in permitidos:
                return jsonify(error='Origen de solicitud no permitido.'), 403

    @app.after_request
    def cabeceras(respuesta):
        respuesta.headers['Cache-Control'] = 'no-store'
        respuesta.headers['CDN-Cache-Control'] = 'no-store'
        respuesta.headers['Vercel-CDN-Cache-Control'] = 'no-store'
        respuesta.headers['X-Content-Type-Options'] = 'nosniff'
        respuesta.headers['Referrer-Policy'] = 'same-origin'
        return respuesta

    @app.errorhandler(Exception)
    def error(error):
        db.session.rollback()
        if isinstance(error, HTTPException):
            mensajes = {401: 'Inicia sesión para continuar.', 403: 'No tienes permiso para realizar esta acción',
                        404: 'El registro o recurso no existe.', 415: 'Envía los datos en formato JSON.'}
            return jsonify(error=mensajes.get(error.code, error.description)), error.code
        if isinstance(error, PermissionError):
            return jsonify(error='No tienes permiso para realizar esta acción'), 403
        if isinstance(error, ValueError):
            return jsonify(error=str(error)), 400
        if isinstance(error, IntegrityError):
            return jsonify(error='Datos duplicados, inválidos o con relaciones existentes.'), 409
        app.logger.exception('Error de API')
        return jsonify(error='No se pudo completar la operación.'), 500
    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5001, debug=False)
