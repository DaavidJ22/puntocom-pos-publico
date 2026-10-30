"""Restricciones persistentes, incluso al escribir SQL fuera de la aplicación."""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from entorno_pg import CasoPostgres
from migraciones import aplicar_migracion_integridad


class EsquemaPostgresTest(CasoPostgres):
    def rechazar(self, sql):
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as c:
                c.exec_driver_sql(sql)

    def test_no_permite_dos_turnos_abiertos_del_mismo_usuario(self):
        self.rechazar('INSERT INTO turno_caja(id_usuario) VALUES(2)')

    def test_correo_usuario_es_unico_sin_importar_mayusculas(self):
        self.rechazar("INSERT INTO usuario(id_rol,nombre,correo,hash_contrasena) VALUES(2,'Duplicado',' ADMIN@example.test ','hash')")

    def test_documentos_unicos_normalizados_y_nulos_repetibles(self):
        for tabla, nombre, doc in [('cliente','nombre_razon_social','nit_dpi'),('proveedor','razon_social','nit')]:
            with self.subTest(tabla=tabla):
                with self.engine.begin() as c:
                    c.exec_driver_sql(f"INSERT INTO {tabla}({nombre},{doc}) VALUES('Prueba','1234567-K'),('Sin documento',NULL),('Otro sin documento',NULL)")
                self.rechazar(f"INSERT INTO {tabla}({nombre},{doc}) VALUES('Duplicado',' 1234567-k ')")

    def test_estados_y_metodos_invalidos_se_rechazan(self):
        for sql in ("UPDATE turno_caja SET estado='OTRO' WHERE id_turno=1",
                    "INSERT INTO venta(id_cliente,id_usuario,id_turno,numero_ticket,metodo_pago) VALUES(1,2,1,'MALO','OTRO')",
                    "INSERT INTO compra(id_proveedor,id_usuario,metodo_pago) VALUES(1,1,'OTRO')"):
            with self.subTest(sql=sql):
                self.rechazar(sql)

    def test_cierre_anterior_a_apertura_se_rechaza(self):
        self.rechazar("UPDATE turno_caja SET cierre=apertura-INTERVAL '1 second' WHERE id_turno=1")

    def test_detalle_no_puede_descontar_mas_del_importe(self):
        with self.engine.begin() as c:
            c.exec_driver_sql("INSERT INTO venta(id_cliente,id_usuario,id_turno,numero_ticket,metodo_pago) VALUES(1,2,1,'DETALLE','TARJETA')")
        self.rechazar('INSERT INTO detalle_venta(id_venta,id_producto,cantidad,precio_unitario,costo_unitario_historico,descuento) VALUES(1,1,1,15,9,16)')

    def test_movimiento_no_puede_apuntar_a_detalle_inexistente(self):
        self.rechazar("INSERT INTO movimiento_inventario(id_producto,tipo,cantidad,id_detalle_venta) VALUES(1,'SALIDA',1,999999)")
        self.rechazar("INSERT INTO movimiento_caja(id_turno,tipo,concepto,monto,id_venta) VALUES(1,'INGRESO','Inválido',10,999999)")

    def test_movimiento_compra_es_entrada_y_no_se_duplica(self):
        with self.engine.begin() as c:
            c.exec_driver_sql("INSERT INTO compra(id_proveedor,id_usuario,metodo_pago,total) VALUES(1,1,'TARJETA',9)")
            c.exec_driver_sql('INSERT INTO detalle_compra(id_compra,id_producto,cantidad,costo_unitario) VALUES(1,1,1,9)')
        self.rechazar("INSERT INTO movimiento_inventario(id_producto,tipo,cantidad,id_detalle_compra) VALUES(1,'SALIDA',1,1)")
        with self.engine.begin() as c:
            c.exec_driver_sql("INSERT INTO movimiento_inventario(id_producto,tipo,cantidad,id_detalle_compra) VALUES(1,'ENTRADA',1,1)")
        self.rechazar("INSERT INTO movimiento_inventario(id_producto,tipo,cantidad,id_detalle_compra) VALUES(1,'ENTRADA',1,1)")

    def test_sesion_no_admite_hash_o_fechas_invalidas(self):
        self.rechazar("INSERT INTO sesion_token(id_sesion,id_usuario,refresh_hash,expira) VALUES('11111111-1111-1111-1111-111111111111',1,'incorrecto',NOW()+INTERVAL '1 hour')")
        self.rechazar("INSERT INTO sesion_token(id_sesion,id_usuario,refresh_hash,expira) VALUES('11111111-1111-1111-1111-111111111111',1,repeat('a',64),NOW()-INTERVAL '1 hour')")

    def test_migracion_repetida_conserva_datos_y_relaciones(self):
        def foto():
            with self.engine.connect() as c:
                return [tuple(r) for r in c.execute(text('SELECT * FROM producto ORDER BY id_producto'))]
        antes = foto()
        aplicar_migracion_integridad(self.engine)
        aplicar_migracion_integridad(self.engine)
        self.assertEqual(foto(), antes)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT COUNT(*) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace AND NOT convalidated")).scalar_one(), 0)
