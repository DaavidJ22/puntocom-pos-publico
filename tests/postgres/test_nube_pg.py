"""Instalación en nube simulada únicamente en la base UUID desechable del ejecutor."""
import re

from sqlalchemy import text
from werkzeug.security import check_password_hash
from backend.preparar_nube import preparar, PERFILES
from entorno_pg import CasoPostgres


class PreparacionNubePostgres(CasoPostgres):
    def test_base_existente_no_reemplaza_usuarios_ni_inventario(self):
        with self.engine.connect() as c:
            antes=c.execute(text('SELECT correo,hash_contrasena FROM usuario ORDER BY id_usuario')).all()
        resultado=preparar(self.engine,{})
        self.assertEqual(resultado,{'base_nueva':False,'cuentas_creadas':0})
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT correo,hash_contrasena FROM usuario ORDER BY id_usuario')).all(),antes)
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM movimiento_inventario')).scalar_one(),2)

    def test_instalacion_nueva_y_reinicio_no_duplican_datos_ni_restauran_claves(self):
        # La recreación de public está confinada a la base UUID creada para esta suite.
        self.assertRegex(self.engine.url.database,r'^puntocom_test_[a-f0-9]{32}$')
        with self.engine.begin() as c:
            nombre,marca=c.execute(text("SELECT current_database(),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).one()
            self.assertEqual(nombre,self.engine.url.database)
            self.assertIsNotNone(re.fullmatch(r'puntocom-pruebas:[a-f0-9]{32}',marca))
            c.exec_driver_sql('DROP SCHEMA public CASCADE')
            c.exec_driver_sql('CREATE SCHEMA public')
        claves={variable:'ClaveNubeSoloPruebas-2026-'+str(i) for i,(_,variable,_) in enumerate(PERFILES)}
        # Aun si falla una comprobación, restaura el esquema esperado para otros casos.
        self.addCleanup(preparar,self.engine,claves)
        with self.assertRaisesRegex(ValueError,'DEMO_ADMIN_PASSWORD'):
            preparar(self.engine,{})
        self.assertEqual(preparar(self.engine,claves),{'base_nueva':True,'cuentas_creadas':3})
        with self.engine.connect() as c:
            antes=c.execute(text('SELECT correo,hash_contrasena FROM usuario ORDER BY id_usuario')).all()
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM producto')).scalar_one(),2)
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM movimiento_inventario')).scalar_one(),2)
        for correo,hash_ in antes:
            variable=next(variable for _,variable,email in PERFILES if email==correo)
            self.assertTrue(check_password_hash(hash_,claves[variable]))
        self.assertEqual(preparar(self.engine,{}),{'base_nueva':False,'cuentas_creadas':0})
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT correo,hash_contrasena FROM usuario ORDER BY id_usuario')).all(),antes)
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM movimiento_inventario')).scalar_one(),2)
