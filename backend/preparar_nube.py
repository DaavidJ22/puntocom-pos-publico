"""Prepara exclusivamente la base DATABASE_URL del despliegue; no lee el .env local."""

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

from configuracion import cargar_configuracion

ROOT = Path(__file__).resolve().parents[1]
PERFILES = (
    ('Administrador', 'DEMO_ADMIN_PASSWORD', 'admin@puntocom.demo'),
    ('Cajero', 'DEMO_CAJERO_PASSWORD', 'cajero@puntocom.demo'),
    ('Bodeguero', 'DEMO_BODEGA_PASSWORD', 'bodega@puntocom.demo'),
)


def preparar(engine, entorno):
    """Conserva instalaciones existentes; nunca borra tablas ni restablece contraseñas."""
    with engine.connect() as c:
        c.execute(text("SET lock_timeout='15s'"))
        c.execute(text("SET statement_timeout='60s'"))
        c.execute(text("SELECT pg_advisory_lock(hashtextextended('puntocom:preparar-nube',0))"))
        c.commit()
        try:
            tablas = set(c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
            nueva = not tablas
            esquema_inicial = {'rol','usuario','producto','categoria','cliente','proveedor','venta',
                              'detalle_venta','compra','detalle_compra','turno_caja','movimiento_caja','movimiento_inventario'}
            if tablas and not esquema_inicial <= tablas:
                raise ValueError('La base contiene un esquema desconocido o incompleto. No se modificó.')
            sin_usuarios = nueva or c.execute(text('SELECT COUNT(*) FROM usuario')).scalar_one() == 0
            claves = {}
            if sin_usuarios:
                for rol, variable, correo in PERFILES:
                    clave = entorno.get(variable, '')
                    if len(clave) < 16:
                        raise ValueError(variable + ' debe tener al menos 16 caracteres para preparar las cuentas nuevas.')
                    claves[correo] = clave
                if len(set(claves.values())) != len(PERFILES):
                    raise ValueError('Utiliza contraseñas distintas para cada perfil de demostración.')
            c.commit()
            scripts = ['01_esquema.sql', '02_datos_iniciales.sql'] if nueva else []
            scripts += ['04_roles_inventario.sql','05_sesiones_token.sql','06_integridad_trazabilidad.sql','07_bitacora_auditoria.sql','08_autenticacion_dos_factores.sql','09_abonos_credito.sql']
            for nombre in scripts:
                c.execute(text((ROOT / 'sql' / nombre).read_text(encoding='utf-8')))
                c.commit()
            if sin_usuarios:
                for rol, variable, correo in PERFILES:
                    c.execute(text('''INSERT INTO usuario(id_rol,nombre,correo,hash_contrasena)
                        SELECT id_rol,:nombre,:correo,:hash FROM rol WHERE nombre=:rol'''),
                        dict(nombre=rol + ' Demo', correo=correo, rol=rol,
                             hash=generate_password_hash(claves[correo])))
                c.commit()
            return {'base_nueva': nueva, 'cuentas_creadas': len(PERFILES) if sin_usuarios else 0}
        finally:
            c.rollback()
            c.execute(text("SELECT pg_advisory_unlock(hashtextextended('puntocom:preparar-nube',0))"))
            c.commit()


def main():
    if not os.environ.get('DATABASE_URL') or os.environ.get('APP_ENV') != 'production':
        raise SystemExit('Este comando requiere DATABASE_URL y APP_ENV=production; no utiliza el .env local.')
    config = cargar_configuracion()
    if (config['SQLALCHEMY_DATABASE_URI'].host or '').split('.')[0].endswith('-pooler'):
        raise SystemExit('Utiliza la conexión directa de Neon: desactiva Connection pooling para las migraciones.')
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'], **config['SQLALCHEMY_ENGINE_OPTIONS'])
    try:
        resultado = preparar(engine, os.environ)
        print('Base de presentación preparada. Cuentas nuevas:', resultado['cuentas_creadas'])
        print('Los usuarios y operaciones existentes se conservan. No se imprimen credenciales.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
