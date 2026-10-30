"""Cifrado y TOTP con reloj/vectores conocidos, sin PostgreSQL ni cuentas reales."""
import unittest
from flask import Flask
import pyotp

from backend.mfa import cifrar,descifrar,paso_valido


class MFAUnitarias(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY']='clave-estable-de-prueba-totp-de-al-menos-32-caracteres'

    def test_vector_sha1_rfc6238_seis_digitos_y_replay(self):
        # RFC 6238: secreto ASCII 12345678901234567890, T=59: 94287082 (8), 287082 (6).
        secreto='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        self.assertEqual(paso_valido(secreto,'287082',ahora=59),1)
        self.assertIsNone(paso_valido(secreto,'287082',ultimo=1,ahora=59))

    def test_ventana_de_un_paso_no_acepta_codigos_fuera_o_formatos_ambiguos(self):
        secreto='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        ahora=1800000010
        totp=pyotp.TOTP(secreto)
        self.assertIsNotNone(paso_valido(secreto,totp.at(ahora-30),ahora=ahora))
        self.assertIsNotNone(paso_valido(secreto,totp.at(ahora+30),ahora=ahora))
        self.assertIsNone(paso_valido(secreto,totp.at(ahora-90),ahora=ahora))
        for codigo in (' 287082','287082 ','２８７０８２',287082,None,{},'12345','1234567'):
            self.assertIsNone(paso_valido(secreto,codigo,ahora=59))

    def test_cifrado_aleatorio_autenticado_y_clave_distinta_no_descifra(self):
        secreto='SEMILLA_PRIVADA_SOLO_PRUEBA'
        with self.app.app_context():
            primero,segundo=cifrar(secreto),cifrar(secreto)
            self.assertNotEqual(primero,segundo);self.assertNotIn(secreto,primero)
            self.assertEqual(descifrar(primero),secreto)
            with self.assertRaises(ValueError):descifrar('alterado'+primero)
            self.app.config['SECRET_KEY']='otra-clave-estable-y-distinta-para-probar-el-cifrado'
            with self.assertRaises(ValueError) as error:descifrar(primero)
            self.assertNotIn(secreto,str(error.exception))

    def test_clave_dedicada_preserva_cifrado_si_cambia_clave_de_sesion(self):
        self.app.config['MFA_ENCRYPTION_KEY']='clave-dedicada-de-pruebas-2fa-minimo-32-caracteres'
        with self.app.app_context():
            cifrado=cifrar('SEMILLA_PRUEBA')
            self.app.config['SECRET_KEY']='nuevo-secreto-de-sesion'
            self.assertEqual(descifrar(cifrado),'SEMILLA_PRUEBA')

    def test_no_se_configura_con_clave_debil(self):
        self.app.config['SECRET_KEY']='debil'
        with self.app.app_context(),self.assertRaisesRegex(ValueError,'32'):
            cifrar('SEMILLA_PRUEBA')
