"""Pagos sobre PostgreSQL desechable: dinero, permisos, rollback y concurrencia."""
from uuid import uuid4
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from entorno_pg import CasoPostgres
from pagos_servicio import registrar_abono


class PagosTests(CasoPostgres):
    aplicacion=None

    def setUp(self):
        super().setUp();self.client=self.aplicacion.test_client()

    def tearDown(self):
        from datos import db
        with self.aplicacion.app_context():db.session.remove()
        super().tearDown()

    def login(self,nombre='cajero1'):
        r=self.client.post('/api/auth/login',json={'correo':nombre+'@example.test','password':'PruebaPostgres2026!'})
        self.assertEqual(r.status_code,200,r.json)
        return {'Authorization':'Bearer '+r.json['access_token']}

    def post(self,url,h,body):return self.client.post('/api'+url,headers=h,json=body)
    def get(self,url,h):return self.client.get('/api'+url,headers=h)
    def scalar(self,sql):
        with self.engine.connect() as c:return c.execute(text(sql)).scalar_one()

    def venta(self,h,metodo='CRÉDITO'):
        r=self.post('/ventas',h,{'cliente_id':1,'metodo':metodo,'recibido':100,'items':[{'id':1,'cantidad':1}]})
        self.assertEqual(r.status_code,200,r.json)
        return r.json['resultado']['id_venta']

    def abono(self,monto='5',metodo='EFECTIVO',**extra):
        return dict(solicitud=str(uuid4()),monto=monto,metodo=metodo,referencia='Prueba',**extra)

    def test_credito_abonos_saldo_caja_auditoria_y_reintento(self):
        h=self.login();vid=self.venta(h);url=f'/cuentas/ventas/{vid}/abonos'
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM movimiento_caja'),0)
        d=self.abono();r=self.post(url,h,d);self.assertEqual(r.status_code,200,r.json)
        aid=r.json['resultado']['id_abono'];self.assertEqual(r.json['resultado']['saldo'],'10.00')
        r=self.post(url,h,d);self.assertTrue(r.json['resultado']['repetido'])
        self.assertEqual(r.json['resultado']['id_abono'],aid)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM abono'),1)
        self.assertEqual(self.scalar('SELECT SUM(monto) FROM movimiento_caja'),Decimal('5'))
        self.assertEqual(self.post(url,h,self.abono('10','TRANSFERENCIA')).status_code,200)
        self.assertEqual(self.get(url,h).json['saldo'],'0.00')
        self.assertEqual(self.get('/cuentas/ventas',h).json['resumen']['pendiente'],'0.00')
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM bitacora_auditoria WHERE entidad='abono' AND id_usuario=2"),2)
        self.assertEqual(self.scalar('SELECT existencia_actual FROM vista_inventario WHERE id_producto=1'),9)
        admin=self.login('admin')
        self.assertEqual(self.post(f'/ventas/{vid}/anular',admin,{'motivo':'Prueba'}).status_code,400)

    def test_compras_credito_egreso_y_no_doble_descuento(self):
        h=self.login('admin');self.post('/caja',h,{'accion':'abrir','fondo_inicial':'20'})
        r=self.post('/compras',h,dict(id_producto=1,id_proveedor=1,cantidad=1,costo_unitario=30,metodo_pago='CRÉDITO',numero_factura='TEST'))
        self.assertEqual(r.status_code,200,r.json);cid=r.json['resultado'];url=f'/cuentas/compras/{cid}/abonos'
        self.assertEqual(self.post(url,h,self.abono('25')).status_code,400)
        self.assertEqual(self.post(url,h,self.abono('10')).status_code,200)
        self.assertEqual(self.scalar("SELECT SUM(monto) FROM movimiento_caja WHERE tipo='EGRESO'"),Decimal('10'))
        self.assertEqual(self.post(url,h,self.abono('20','TARJETA')).status_code,200)
        self.assertEqual(self.get('/cuentas/compras',h).json['resumen']['pendiente'],'0.00')
        self.assertEqual(self.scalar('SELECT existencia_actual FROM vista_inventario WHERE id_producto=1'),11)

    def test_permisos_y_aislamiento_cajeros(self):
        self.assertEqual(self.client.get('/api/cuentas/ventas').status_code,401)
        h=self.login();vid=self.venta(h);otro=self.login('cajero2')
        self.assertEqual(self.get('/cuentas/ventas',otro).json['data'],[])
        self.assertEqual(self.get(f'/cuentas/ventas/{vid}/abonos',otro).status_code,403)
        self.assertEqual(self.post(f'/cuentas/ventas/{vid}/abonos',otro,self.abono()).status_code,403)
        self.assertEqual(self.get('/cuentas/compras',h).status_code,403)
        bodega=self.login('bodeguero')
        self.assertEqual(self.get('/cuentas/ventas',bodega).status_code,403)
        self.assertEqual(self.post(f'/cuentas/ventas/{vid}/abonos',bodega,self.abono()).status_code,403)
        admin=self.login('admin');self.assertEqual(len(self.get('/cuentas/ventas',admin).json['data']),1)

    def test_importes_invalidos_exceso_y_uuid_reutilizado(self):
        h=self.login();vid=self.venta(h);url=f'/cuentas/ventas/{vid}/abonos'
        for monto in ('0','-1','NaN','Infinity',True,'15.01'):
            self.assertEqual(self.post(url,h,self.abono(monto)).status_code,400,monto)
        d=self.abono();self.assertEqual(self.post(url,h,d).status_code,200)
        d['monto']='6';self.assertEqual(self.post(url,h,d).status_code,400)
        self.assertEqual(self.post(url,h,{}).status_code,400)
        self.assertEqual(self.post(url,h,[]).status_code,400)
        self.assertEqual(self.post(url,h,self.abono(metodo='CRÉDITO')).status_code,400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM abono'),1)

    def test_turno_cerrado_no_impide_transferencia_y_contado_no_admite_abono(self):
        h=self.login();vid=self.venta(h);contado=self.venta(h,'TARJETA')
        self.post('/caja',h,{'accion':'cerrar','efectivo_contado':'100'})
        self.assertEqual(self.post(f'/cuentas/ventas/{vid}/abonos',h,self.abono()).status_code,400)
        self.assertEqual(self.post(f'/cuentas/ventas/{vid}/abonos',h,self.abono(metodo='TRANSFERENCIA')).status_code,200)
        self.assertEqual(self.post(f'/cuentas/ventas/{contado}/abonos',h,self.abono(metodo='TRANSFERENCIA')).status_code,400)

    def test_rollback_revierte_abono_caja_y_bitacora(self):
        h=self.login();vid=self.venta(h)
        def fallar(*args):
            registrar_abono(*args)
            raise ValueError('Fallo simulado antes de confirmar')
        with patch('backend.pagos.registrar_abono',side_effect=fallar):
            self.assertEqual(self.post(f'/cuentas/ventas/{vid}/abonos',h,self.abono()).status_code,400)
        for tabla in ('abono','movimiento_caja'):
            self.assertEqual(self.scalar('SELECT COUNT(*) FROM '+tabla),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM bitacora_auditoria WHERE entidad='abono'"),0)

    def test_restricciones_sql_y_migracion_repetida(self):
        h=self.login();vid=self.venta(h);self.post(f'/cuentas/ventas/{vid}/abonos',h,self.abono())
        for sql in ("UPDATE abono SET monto=1",'DELETE FROM abono',
            "INSERT INTO abono(solicitud,id_venta,id_usuario,monto,metodo) VALUES(gen_random_uuid(),1,2,11,'TRANSFERENCIA')"):
            with self.assertRaises(IntegrityError):
                with self.engine.begin() as c:c.execute(text(sql))
        from migraciones import aplicar_migracion_abonos
        aplicar_migracion_abonos(self.engine);aplicar_migracion_abonos(self.engine)
        self.assertEqual(self.scalar('SELECT SUM(monto) FROM abono'),Decimal('5'))

    def test_dos_abonos_simultaneos_no_superan_saldo(self):
        h=self.login();vid=self.venta(h);barrera=Barrier(2)
        def pagar():
            with Session(self.engine) as s:
                barrera.wait(timeout=5)
                try:
                    registrar_abono(s,'ventas',vid,self.abono('10','TRANSFERENCIA'),2);s.commit();return 'aceptado'
                except ValueError:s.rollback();return 'rechazado'
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(pagar);b=pool.submit(pagar)
            self.assertEqual(sorted([a.result(timeout=15),b.result(timeout=15)]),['aceptado','rechazado'])
        self.assertEqual(self.scalar('SELECT SUM(monto) FROM abono'),Decimal('10'))
