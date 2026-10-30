"""Aplica las migraciones incrementales 04, 05 y 06; requiere el esquema inicial."""
from pathlib import Path
from backend.app import create_app
from datos import db
from migraciones import aplicar_migracion_roles, aplicar_migracion_integridad

if __name__ == '__main__':
    app=create_app()
    with app.app_context():
        aplicar_migracion_roles(db.engine)
        with db.engine.begin() as conexion:
            conexion.exec_driver_sql((Path(__file__).resolve().parents[1]/'sql/05_sesiones_token.sql').read_text(encoding='utf-8'))
        aplicar_migracion_integridad(db.engine)
    print('Migraciones 04, 05 y 06 aplicadas; registros e identificadores conservados.')
