"""Servidor de la API para la instancia gratuita de Render (Linux)."""
import os

bind = '0.0.0.0:' + os.environ.get('PORT', '10000')
workers = 1
worker_class = 'gthread'
threads = 4
timeout = 90
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
# No incluir URL completa, query string, cabeceras ni cookies en el registro.
access_log_format = '%(m)s %(U)s %(s)s %(L)s'
