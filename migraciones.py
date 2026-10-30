"""Migraciones explícitas; importar este módulo no lee secretos ni conecta a la BD."""

from sqlalchemy import text
from pathlib import Path


TABLAS_ESTADO = ('categoria', 'cliente', 'proveedor')
SQL_PREPARAR_MIGRACION_BAJAS = (
    "SET LOCAL lock_timeout = '5s'",
    "SET LOCAL statement_timeout = '30s'",
    # Serializa dos ejecuciones de esta migración, incluido el script SQL.
    "SELECT pg_advisory_xact_lock(hashtextextended('puntocom:migracion:03_estado_catalogos', 0))",
)
SQL_COLUMNAS_ESTADO = tuple(
    f'ALTER TABLE public.{tabla} ADD COLUMN IF NOT EXISTS estado BOOLEAN NOT NULL DEFAULT TRUE'
    for tabla in TABLAS_ESTADO
)


def aplicar_migracion_bajas(engine):
    """Añade estados en una transacción y devuelve las columnas recién añadidas.

    Recibe el motor configurado por quien llama. No crea conexiones al importar,
    no cambia estados existentes y no confirma parcialmente una migración fallida.
    Los límites de espera son locales a esta transacción.
    """
    with engine.begin() as conexion:
        for sentencia in SQL_PREPARAR_MIGRACION_BAJAS:
            conexion.execute(text(sentencia))
        existentes = set(conexion.execute(text('''
            SELECT table_name FROM information_schema.columns
            WHERE table_schema='public' AND column_name='estado'
              AND table_name IN ('categoria','cliente','proveedor')
        ''')).scalars())
        for sentencia in SQL_COLUMNAS_ESTADO:
            conexion.execute(text(sentencia))
        agregadas = [f'{tabla}.estado' for tabla in TABLAS_ESTADO if tabla not in existentes]
    return agregadas


def aplicar_migracion_roles(engine):
    """Ejecuta el script transaccional completo en una conexión sin autocommit."""
    script = Path(__file__).with_name('sql').joinpath('04_roles_inventario.sql').read_text(encoding='utf-8')
    with engine.connect() as conexion:
        try:
            conexion.exec_driver_sql(script)
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise


def aplicar_migracion_integridad(engine):
    """Migración 06 atómica, repetible y sin limpieza automática de datos previos."""
    script = Path(__file__).with_name('sql').joinpath('06_integridad_trazabilidad.sql').read_text(encoding='utf-8')
    with engine.connect() as conexion:
        try:
            conexion.execute(text(script))
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise


def aplicar_migracion_auditoria(engine):
    """Añade la bitácora sin reconstruir ni alterar registros previos."""
    script = Path(__file__).with_name('sql').joinpath('07_bitacora_auditoria.sql').read_text(encoding='utf-8')
    with engine.connect() as conexion:
        try:
            conexion.execute(text(script))
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise


def aplicar_migracion_mfa(engine):
    """Crea las estructuras privadas de 2FA sin activar cuentas ni copiar secretos."""
    script = Path(__file__).with_name('sql').joinpath('08_autenticacion_dos_factores.sql').read_text(encoding='utf-8')
    with engine.connect() as conexion:
        try:
            conexion.execute(text(script))
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise


def aplicar_migracion_abonos(engine):
    """Añade el libro de abonos conservando documentos y movimientos previos."""
    script=Path(__file__).with_name('sql').joinpath('09_abonos_credito.sql').read_text(encoding='utf-8')
    with engine.begin() as conexion:
        conexion.execute(text(script))
