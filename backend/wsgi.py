"""Entrada de Gunicorn para Render. No inicia el servidor de desarrollo."""
from backend.app import create_app

app = create_app()
