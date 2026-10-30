"""Escenarios reales de 2FA sobre la base UUID desechable del ejecutor API."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from unittest.mock import patch

import pyotp
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from backend import mfa
from datos import db
from entorno_pg import CasoPostgres


CLAVE = 'PruebaPostgres2026!'


class MFATests(CasoPostgres):
    aplicacion = None

    def setUp(self):
        super().setUp()
        self.client = self.aplicacion.test_client()
        self.patch_reloj = patch('backend.mfa.time.time',return_value=1800000010)
        self.reloj = self.patch_reloj.start()
        self.addCleanup(self.patch_reloj.stop)

    def tearDown(self):
        with self.aplicacion.app_context():db.session.remove()
        super().tearDown()

    def cabecera(self, token):
        return {'Authorization':'Bearer '+token}

    def post(self,ruta,token=None,**datos):
        return self.client.post('/api/auth/'+ruta,headers=self.cabecera(token) if token else {},json=datos)

    def login(self,nombre='admin'):
        r = self.post('login',correo=nombre+'@example.test',password=CLAVE)
        self.assertEqual(r.status_code,200,r.json)
        return r.json

    def codigo(self,secreto,nuevo=False):
        if nuevo:self.reloj.return_value += 30
        return pyotp.TOTP(secreto).at(self.reloj.return_value)

    def activar(self,nombre='admin'):
        token = self.login(nombre)['access_token']
        r = self.post('mfa/preparar',token,password=CLAVE)
        self.assertEqual(r.status_code,200,r.json)
        secreto = r.json['secreto']
        r = self.post('mfa/confirmar',token,password=CLAVE,codigo=self.codigo(secreto))
        self.assertEqual(r.status_code,200,r.json)
        return r.json['access_token'],secreto,r.json['codigos_respaldo'],token

    def me(self,token):
        return self.client.get('/api/auth/me',headers=self.cabecera(token))

    def test_activar_confirma_codigo_cifra_semilla_revoca_sesiones_y_no_publica_secreto(self):
        otro = self.login()['access_token']
        token,secreto,respaldos,anterior = self.activar()
        self.assertEqual(len(respaldos),10);self.assertEqual(len(set(respaldos)),10)
        self.assertEqual(self.me(token).status_code,200)
        for viejo in (otro,anterior):self.assertEqual(self.me(viejo).status_code,401)
        with self.engine.connect() as c:
            config = c.execute(text('SELECT * FROM usuario_mfa WHERE id_usuario=1')).mappings().one()
            privados = str(c.execute(text('SELECT * FROM codigo_respaldo')).all())
            bitacora = str(c.execute(text('SELECT * FROM bitacora_auditoria')).all())
        self.assertTrue(config['activo']);self.assertNotEqual(config['secreto_cifrado'],secreto)
        self.assertIsNone(config['pendiente_cifrado'])
        for privado in [secreto,CLAVE,*respaldos]:
            self.assertNotIn(privado,privados);self.assertNotIn(privado,bitacora)
        self.assertIn('MFA_ACTIVADO',bitacora)
        estado = self.client.get('/api/auth/mfa',headers=self.cabecera(token)).json
        self.assertEqual(estado,{'activo':True,'respaldos_restantes':10})
        self.assertNotIn(secreto,str(self.me(token).json))

    def test_clave_sola_no_emite_tokens_y_codigo_completa_ingreso(self):
        _,secreto,_,_ = self.activar()
        reto = self.login()
        self.assertTrue(reto['requiere_2fa']);self.assertNotIn('access_token',reto)
        self.assertEqual(self.me(reto['reto']).status_code,401)
        self.assertIsNone(self.client.get_cookie('refresh_token_cookie',path='/api/auth'))
        r = self.post('login/segundo-factor',reto=reto['reto'],codigo=self.codigo(secreto,True))
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.me(r.json['access_token']).status_code,200)
        self.assertFalse(r.json['uso_respaldo'])

    def test_totp_no_se_puede_reutilizar_incluso_en_otro_reto(self):
        _,secreto,_,_ = self.activar()
        reto = self.login()['reto']
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto)).status_code,401)
        nuevo = self.codigo(secreto,True)
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=nuevo).status_code,200)
        otro = self.login()['reto']
        self.assertEqual(self.post('login/segundo-factor',reto=otro,codigo=nuevo).status_code,401)

    def test_reto_de_un_solo_uso_y_rechazo_de_otro_cliente_sin_reto(self):
        _,secreto,_,_ = self.activar()
        reto = self.login()['reto']
        codigo = self.codigo(secreto,True)
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=codigo).status_code,200)
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto,True)).status_code,401)
        self.assertEqual(self.post('login/segundo-factor',reto='falso',codigo=codigo).status_code,401)

    def test_reto_expirado_no_crea_sesion_y_cambio_password_lo_invalida(self):
        _,secreto,_,_ = self.activar()
        reto = self.login()['reto']
        with self.engine.begin() as c:
            c.execute(text("UPDATE reto_mfa SET expira=NOW()-INTERVAL '1 second' WHERE huella=:h"),{'h':mfa.huella(reto)})
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto,True)).status_code,401)
        reto = self.login()['reto']
        with self.engine.begin() as c:
            c.execute(text('UPDATE usuario SET hash_contrasena=:h WHERE id_usuario=1'),{'h':generate_password_hash('ClaveCambiadaSoloPrueba!')})
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto,True)).status_code,401)

    def test_cuenta_desactivada_no_completa_reto(self):
        _,secreto,_,_ = self.activar()
        reto = self.login()['reto']
        with self.engine.begin() as c:c.exec_driver_sql('UPDATE usuario SET estado=FALSE WHERE id_usuario=1')
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto,True)).status_code,401)

    def test_respaldo_funciona_una_vez_y_mfa_sigue_activo(self):
        token,_,codigos,_ = self.activar()
        reto = self.login()['reto']
        r = self.post('login/segundo-factor',reto=reto,codigo=codigos[0].lower())
        self.assertEqual(r.status_code,200,r.json);self.assertTrue(r.json['uso_respaldo'])
        estado = self.client.get('/api/auth/mfa',headers=self.cabecera(r.json['access_token'])).json
        self.assertEqual(estado,{'activo':True,'respaldos_restantes':9})
        reto = self.login()['reto']
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=codigos[0]).status_code,401)

    def test_limite_cinco_por_reto_persistente(self):
        _,secreto,_,_ = self.activar()
        reto = self.login()['reto']
        for _ in range(5):self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo='incorrecto').status_code,401)
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto,True)).status_code,401)
        otro = self.login()['reto']
        self.assertEqual(self.post('login/segundo-factor',reto=otro,codigo=self.codigo(secreto,True)).status_code,200)

    def test_limite_por_usuario_no_se_elude_solicitando_retos_nuevos(self):
        self.activar()
        for _ in range(2):
            reto = self.login()['reto']
            for _ in range(5):self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo='incorrecto').status_code,401)
        reto = self.login()['reto']
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo='incorrecto').status_code,429)
        # La ventana se controla con PostgreSQL y se conserva entre clientes/procesos.
        with self.engine.begin() as c:c.exec_driver_sql("UPDATE limite_auth SET inicio=NOW()-INTERVAL '6 minutes'")
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo='incorrecto').status_code,401)

    def test_limite_password_y_exito_limpia_fallos(self):
        for _ in range(20):
            self.assertEqual(self.post('login',correo='noexiste@example.test',password='Incorrecta').status_code,401)
        self.assertEqual(self.post('login',correo='noexiste@example.test',password='Incorrecta').status_code,429)
        self.assertIn('access_token',self.login())

    def test_preparar_requiere_contrasena_y_no_activa_hasta_confirmar(self):
        token = self.login()['access_token']
        self.assertEqual(self.post('mfa/preparar',token,password='incorrecta').status_code,400)
        setup = self.post('mfa/preparar',token,password=CLAVE)
        self.assertEqual(setup.status_code,200,setup.json)
        self.assertTrue(setup.json['qr'].startswith('data:image/svg+xml;base64,'))
        estado = self.client.get('/api/auth/mfa',headers=self.cabecera(token)).json
        self.assertFalse(estado['activo'])
        self.assertEqual(self.post('mfa/confirmar',token,password=CLAVE,codigo='incorrecto').status_code,400)
        self.assertIn('access_token',self.login())

    def test_vinculacion_ligada_a_sesion_expira_y_puede_cancelarse(self):
        token = self.login()['access_token']
        otro = self.login()['access_token']
        secreto = self.post('mfa/preparar',token,password=CLAVE).json['secreto']
        self.assertEqual(self.post('mfa/confirmar',otro,password=CLAVE,codigo=self.codigo(secreto)).status_code,400)
        with self.engine.begin() as c:c.exec_driver_sql("UPDATE usuario_mfa SET pendiente_hasta=NOW()-INTERVAL '1 second'")
        self.assertEqual(self.post('mfa/confirmar',token,password=CLAVE,codigo=self.codigo(secreto)).status_code,400)
        self.assertEqual(self.post('mfa/cancelar',token).status_code,200)
        with self.engine.connect() as c:
            self.assertIsNone(c.execute(text('SELECT pendiente_cifrado FROM usuario_mfa WHERE id_usuario=1')).scalar_one())

    def test_no_se_puede_reemplazar_factor_activo_solo_con_password(self):
        token,_,_,_ = self.activar()
        self.assertEqual(self.post('mfa/preparar',token,password=CLAVE).status_code,400)
        self.assertEqual(self.post('mfa/desactivar',token,password=CLAVE).status_code,400)
        self.assertEqual(self.post('mfa/respaldos',token,password=CLAVE).status_code,400)

    def test_desactivar_exige_ambos_factores_y_revoca_todas_las_sesiones(self):
        token,secreto,_,_ = self.activar()
        self.assertEqual(self.post('mfa/desactivar',token,password='incorrecta',codigo=self.codigo(secreto,True)).status_code,400)
        r = self.post('mfa/desactivar',token,password=CLAVE,codigo=self.codigo(secreto))
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.me(token).status_code,401)
        self.assertEqual(self.me(r.json['access_token']).status_code,200)
        self.assertIn('access_token',self.login())
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM codigo_respaldo')).scalar_one(),0)
            self.assertIsNone(c.execute(text('SELECT secreto_cifrado FROM usuario_mfa WHERE id_usuario=1')).scalar_one())

    def test_recuperar_sin_celular_y_regenerar_invalida_respaldos_y_retos_previos(self):
        token,_,codigos,_ = self.activar()
        reto_viejo = self.login()['reto']
        r = self.post('mfa/respaldos',token,password=CLAVE,codigo=codigos[0])
        self.assertEqual(r.status_code,200,r.json)
        self.assertTrue(set(codigos).isdisjoint(r.json['codigos_respaldo']))
        self.assertEqual(self.me(token).status_code,401)
        self.assertEqual(self.post('login/segundo-factor',reto=reto_viejo,codigo=codigos[1]).status_code,401)
        reto = self.login()['reto']
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=codigos[1]).status_code,401)
        self.assertEqual(self.post('login/segundo-factor',reto=reto,codigo=r.json['codigos_respaldo'][0]).status_code,200)

    def test_tres_roles_configuran_solo_su_propia_cuenta(self):
        for nombre,uid in [('admin',1),('cajero1',2),('bodeguero',4)]:
            token = self.login(nombre)['access_token']
            r = self.post('mfa/preparar',token,password=CLAVE,id_usuario=999)
            self.assertEqual(r.status_code,200,r.json)
            with self.engine.connect() as c:
                self.assertIsNotNone(c.execute(text('SELECT pendiente_cifrado FROM usuario_mfa WHERE id_usuario=:uid'),{'uid':uid}).scalar_one())
        self.assertEqual(self.post('mfa/preparar',password=CLAVE).status_code,401)

    def test_autenticacion_anterior_no_elude_mfa_ni_con_cookie_preexistente(self):
        # Cookie de Flask válida antes de activar 2FA.
        with self.client.session_transaction() as sesion:sesion['_user_id']='1';sesion['_fresh']=True
        token,_,_,_ = self.activar()
        legacy = self.app.app.test_client()
        with legacy.session_transaction() as sesion:sesion['_user_id']='1';sesion['_fresh']=True
        self.assertEqual(legacy.get('/').status_code,302)
        self.app.app.config['WTF_CSRF_ENABLED']=False
        try:
            r = legacy.post('/login',data={'correo':'admin@example.test','password':CLAVE})
            self.assertEqual(r.status_code,403)
            self.assertNotIn('secret',r.text.lower())
        finally:self.app.app.config['WTF_CSRF_ENABLED']=True

    def test_respaldo_concurrente_se_consume_una_sola_vez(self):
        _,_,codigos,_ = self.activar()
        retos = [self.login()['reto'],self.login()['reto']]
        def intentar(reto):
            cliente = self.aplicacion.test_client()
            r = cliente.post('/api/auth/login/segundo-factor',json={'reto':reto,'codigo':codigos[0]})
            with self.aplicacion.app_context():db.session.remove()
            return r.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:resultados=list(pool.map(intentar,retos))
        self.assertEqual(sorted(resultados),[200,401])

    def test_semilla_no_depende_de_jwt_y_error_de_clave_no_revela_secreto(self):
        token,secreto,codigos,_ = self.activar()
        original = self.aplicacion.config['SECRET_KEY']
        self.aplicacion.config['SECRET_KEY']='otra-clave-estable-de-cifrado-totalmente-distinta'
        try:
            # Los respaldos siguen permitiendo recuperación sin descifrar la semilla.
            reto = self.login()['reto']
            r = self.post('login/segundo-factor',reto=reto,codigo=self.codigo(secreto,True))
            self.assertEqual(r.status_code,400);self.assertNotIn(secreto,r.text)
            r = self.post('login/segundo-factor',reto=reto,codigo=codigos[0])
            self.assertEqual(r.status_code,200,r.json)
        finally:self.aplicacion.config['SECRET_KEY']=original
