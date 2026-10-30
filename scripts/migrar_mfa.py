"""Añade las tablas privadas de 2FA en la base local; no activa usuarios."""
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import create_engine,text
from configuracion import cargar_configuracion
from migraciones import aplicar_migracion_mfa


def main():
    entorno = {k:v for k,v in dotenv_values(ROOT/'.env').items() if v is not None}
    entorno.update(os.environ)
    config = cargar_configuracion(entorno)
    if config['SQLALCHEMY_DATABASE_URI'].host not in ('127.0.0.1','localhost','::1'):
        raise SystemExit('Este comando solo admite la base local. Render aplica la migración al desplegar.')
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'],**config['SQLALCHEMY_ENGINE_OPTIONS'])
    try:
        aplicar_migracion_mfa(engine)
        with engine.connect() as c:
            activos = c.execute(text('SELECT COUNT(*) FROM usuario_mfa WHERE activo')).scalar_one()
        print('Estructuras de 2FA instaladas. Cuentas ya activas conservadas:',activos)
    except Exception as error:
        raise SystemExit('No se pudo instalar 2FA: '+type(error).__name__) from None
    finally:engine.dispose()


if __name__=='__main__':main()
