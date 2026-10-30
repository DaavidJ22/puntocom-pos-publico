"""Contratos externos simulados: no red, ni cuentas, ni datos del negocio."""
from datetime import datetime,timedelta
import unittest
from unittest.mock import patch
from configuracion import TZ
from backend import externos as e

class ExternosTests(unittest.TestCase):
 def setUp(self):e._cache.clear()
 def test_cambio_contrato_cache_y_fallo_con_datos_anteriores(self):
  d={'date':datetime.now(TZ).date().isoformat(),'base':'USD','quote':'GTQ','rate':7.6}
  with patch.object(e,'obtener_json',return_value=d) as red:
   primero=e.consultar('cambio');segundo=e.consultar('cambio')
   self.assertTrue(primero['ok']);self.assertEqual(segundo['estado'],'cache');self.assertEqual(red.call_count,1)
  clave=('cambio',None);t,datos,marca=e._cache[clave];e._cache[clave]=(t-4000,datos,marca)
  with patch.object(e,'obtener_json',side_effect=TimeoutError('privado')):
   self.assertEqual(e.consultar('cambio')['estado'],'desactualizado')
   e._cache[clave]=(t-90000,datos,marca)
   r=e.consultar('cambio');self.assertFalse(r['ok']);self.assertIsNone(r['datos']);self.assertNotIn('privado',str(r))
 def test_datos_numericos_y_fechas_invalidos_no_se_cachean(self):
  for rate in (float('nan'),float('inf'),-1,True,'7.6'):
   with patch.object(e,'obtener_json',return_value={'date':datetime.now(TZ).date().isoformat(),'base':'USD','quote':'GTQ','rate':rate}):
    self.assertFalse(e.consultar('cambio')['ok'])
  self.assertFalse(e._cache)
 def test_no_se_admite_otro_pais_o_anio_en_calendario(self):
  for pais,anio in [('US',2026),('GT',2025)]:
   with patch.object(e,'obtener_json',return_value=[{'countryCode':pais,'date':f'{anio}-01-01','global':True,'name':'Test'}]):
    self.assertFalse(e.consultar('feriados',2026)['ok'])
 def test_dominios_y_resultados_dns_no_equivalen_a_buzon(self):
  for dominio in ('usuario@gmail.com','https://gmail.com','127.0.0.1','localhost','x..com','-x.com','a.com/path'):
   with self.assertRaises(ValueError):e.validar_dominio(dominio)
  for respuesta,esperado in [({'Status':3},'no_existe'),({'Status':0},'sin_mx'),({'Status':0,'Answer':[{'type':15,'data':'0 .'}]},'no_recibe'),({'Status':0,'Answer':[{'type':15,'data':'10 mx.ejemplo.com.'}]},'con_mx')]:
   e._cache.clear()
   with patch.object(e,'obtener_json',return_value=respuesta):self.assertEqual(e.consultar('dominio','ejemplo.com')['datos']['resultado'],esperado)
  e._cache.clear()
  with patch.object(e,'obtener_json',return_value={'Status':2}):self.assertFalse(e.consultar('dominio','ejemplo.com')['ok'])
 def test_calendario_correcto_con_texto_literal(self):
  with patch.object(e,'obtener_json',return_value=[{'countryCode':'GT','date':'2026-01-01','global':True,'name':'Año Nuevo'}]):
   self.assertEqual(e.consultar('feriados',2026)['datos']['feriados'][0]['nombre'],'Año Nuevo')
