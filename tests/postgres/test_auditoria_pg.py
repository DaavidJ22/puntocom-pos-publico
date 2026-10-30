"""Integridad de la bitácora sobre PostgreSQL real y desechable."""
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from entorno_pg import CasoPostgres
from migraciones import aplicar_migracion_auditoria


class AuditoriaPostgresTest(CasoPostgres):
    def test_no_se_puede_editar_borrar_o_vaciar_historial(self):
        for sql in ("UPDATE bitacora_auditoria SET accion='FALSO'",'DELETE FROM bitacora_auditoria','TRUNCATE bitacora_auditoria'):
            with self.subTest(sql=sql),self.assertRaises(IntegrityError):
                with self.engine.begin() as c:c.exec_driver_sql(sql)

    def test_cambio_directo_identificado_y_rollback_atomico(self):
        with self.engine.connect() as c:
            antes=c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one()
            c.exec_driver_sql('UPDATE producto SET precio_venta=99 WHERE id_producto=1')
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one(),antes+1)
            c.rollback()
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one(),antes)
        with self.engine.begin() as c:c.exec_driver_sql('UPDATE producto SET precio_venta=18 WHERE id_producto=1')
        with self.engine.connect() as c:
            fila=c.execute(text("SELECT * FROM bitacora_auditoria WHERE entidad='producto' AND operacion='UPDATE' ORDER BY id_evento DESC LIMIT 1")).mappings().one()
        self.assertEqual(fila['antes']['precio_venta'],15)
        self.assertEqual(fila['despues']['precio_venta'],18)
        self.assertIsNone(fila['id_usuario']);self.assertEqual(fila['origen'],'base_datos')

    def test_migracion_repetida_no_duplica_triggers_ni_borra_historial(self):
        with self.engine.connect() as c:
            antes=c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one()
        aplicar_migracion_auditoria(self.engine);aplicar_migracion_auditoria(self.engine)
        with self.engine.begin() as c:
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one(),antes)
            c.exec_driver_sql("UPDATE producto SET nombre='Nombre modificado' WHERE id_producto=1")
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one(),antes+1)

    def test_credencial_nunca_se_copia_ni_con_columnas_nuevas(self):
        with self.engine.begin() as c:
            c.exec_driver_sql("UPDATE usuario SET hash_contrasena='hash-privado-no-copiar' WHERE id_usuario=4")
            fila=c.execute(text("SELECT antes,despues,accion FROM bitacora_auditoria WHERE entidad='usuario' AND operacion='UPDATE' ORDER BY id_evento DESC LIMIT 1")).mappings().one()
            self.assertEqual(fila['accion'],'CAMBIAR_CLAVE')
            self.assertTrue(fila['despues']['credencial_modificada'])
            self.assertNotIn('hash-privado-no-copiar',str(fila));self.assertNotIn('hash_contrasena',str(fila))
            c.exec_driver_sql('ALTER TABLE usuario ADD COLUMN secreto_futuro TEXT')
            try:
                c.exec_driver_sql("UPDATE usuario SET nombre='Otro nombre',secreto_futuro='NO_COPIAR' WHERE id_usuario=4")
                fila=c.execute(text('SELECT despues FROM bitacora_auditoria ORDER BY id_evento DESC LIMIT 1')).scalar_one()
                self.assertNotIn('NO_COPIAR',str(fila))
            finally:c.exec_driver_sql('ALTER TABLE usuario DROP COLUMN secreto_futuro')

    def test_eliminar_usuario_preserva_autoria_historica(self):
        with self.engine.begin() as c:
            c.exec_driver_sql("SELECT set_config('puntocom.usuario','4',true)")
            c.exec_driver_sql("INSERT INTO categoria(nombre) VALUES('Creada por bodega')")
        with self.engine.begin() as c:c.exec_driver_sql('DELETE FROM usuario WHERE id_usuario=4')
        with self.engine.connect() as c:
            fila=c.execute(text("SELECT id_usuario,usuario_nombre,usuario_rol FROM bitacora_auditoria WHERE entidad='categoria' AND id_usuario=4")).one()
        self.assertEqual(tuple(fila),(4,'Bodeguero','Bodeguero'))

    def test_actualizacion_identica_no_llena_historial(self):
        with self.engine.begin() as c:
            antes=c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one()
            c.exec_driver_sql('UPDATE producto SET precio_venta=precio_venta WHERE id_producto=1')
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one(),antes)

    def test_truncate_de_negocio_no_pasa_inadvertido(self):
        with self.engine.begin() as c:
            c.exec_driver_sql('TRUNCATE proveedor CASCADE')
            self.assertGreater(c.execute(text("SELECT COUNT(*) FROM bitacora_auditoria WHERE operacion='TRUNCATE' AND entidad='proveedor'")).scalar_one(),0)
