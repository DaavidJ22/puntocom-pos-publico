"""Contratos de despliegue sin cuentas externas, sin secretos y sin PostgreSQL."""
import unittest
from unittest.mock import patch

from backend.app import create_app
from configuracion import cargar_configuracion
from scripts.preparar_frontend_nube import configuracion


class PublicacionTests(unittest.TestCase):
    def test_proxy_conserva_api_y_rutas_react(self):
        config=configuracion('https://api-prueba.onrender.com/')
        self.assertEqual(config['rewrites'][0],{'source':'/api/:path*','destination':'https://api-prueba.onrender.com/api/:path*'})
        self.assertEqual(config['rewrites'][1]['destination'],'/index.html')
        self.assertNotIn('SECRET_KEY',str(config))

    def test_no_se_publican_credenciales_o_proxy_a_dominio_arbitrario(self):
        for url in ('http://api.onrender.com','https://u:clave@api.onrender.com','https://api.onrender.com/api','https://otro.invalid','https://api.onrender.com?token=clave'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                configuracion(url)

    def app_produccion(self, origen):
        with patch.dict('os.environ',{'FRONTEND_ORIGIN':origen,'FRONTEND_ORIGINS':''}):
            return create_app(cargar_configuracion({'APP_ENV':'production','SECRET_KEY':'clave-ficticia-probar-produccion-123456','TRUST_PROXY':'true'}))

    def test_produccion_no_acepta_origen_local_ni_falso(self):
        app=self.app_produccion('https://puntocom-prueba.vercel.app')
        cliente=app.test_client()
        for origen in ('http://localhost:5173','http://127.0.0.1:5173','https://otro.vercel.app'):
            self.assertEqual(cliente.post('/api/auth/login',headers={'Origin':origen},json={}).status_code,403)
        # Un recurso inexistente demuestra que el origen permitido supera el filtro sin necesitar DB.
        self.assertEqual(cliente.post('/api/no-existe',headers={'Origin':'https://puntocom-prueba.vercel.app'}).status_code,404)

    def test_produccion_rechaza_origen_sin_https_y_cookie_secure(self):
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            self.app_produccion('http://puntocom-prueba.vercel.app')
        app=self.app_produccion('https://puntocom-prueba.vercel.app')
        self.assertTrue(app.config['JWT_COOKIE_SECURE'])
        respuesta=app.test_client().get('/api/no-existe')
        self.assertEqual(respuesta.headers['CDN-Cache-Control'],'no-store')
        self.assertEqual(respuesta.headers['Vercel-CDN-Cache-Control'],'no-store')


if __name__=='__main__':unittest.main()
