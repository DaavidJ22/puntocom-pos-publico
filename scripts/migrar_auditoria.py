"""Instala la bitácora en PostgreSQL local sin modificar el catálogo ni crear operaciones."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from configuracion import cargar_configuracion
from migraciones import aplicar_migracion_auditoria


def main():
    entorno = {k:v for k,v in dotenv_values(ROOT/'.env').items() if v is not None}
    entorno.update(os.environ)
    config = cargar_configuracion(entorno)
    if config['SQLALCHEMY_DATABASE_URI'].host not in ('127.0.0.1','localhost','::1'):
        raise SystemExit('Este comando solo admite la base local. Render aplica la migración al desplegar.')
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'],**config['SQLALCHEMY_ENGINE_OPTIONS'])
    try:
        aplicar_migracion_auditoria(engine)
        with engine.connect() as c:
            total = c.execute(text('SELECT COUNT(*) FROM bitacora_auditoria')).scalar_one()
        print('Bitácora instalada. Registros históricos conservados:',total)
    except Exception as error:
        raise SystemExit('No se pudo instalar la bitácora: '+type(error).__name__) from None
    finally:
        engine.dispose()


if __name__=='__main__':main()
