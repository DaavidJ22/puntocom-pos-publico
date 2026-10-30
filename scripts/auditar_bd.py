"""Inspección de solo lectura: estructura e integridad, sin datos personales ni claves."""

import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from configuracion import cargar_configuracion, TZ


CONTROLES = {
    'abonos_venta_superan_saldo': "SELECT COUNT(*) FROM venta v WHERE (SELECT COALESCE(SUM(monto),0) FROM abono a WHERE a.id_venta=v.id_venta)>v.total",
    'abonos_compra_superan_saldo': "SELECT COUNT(*) FROM compra c WHERE (SELECT COALESCE(SUM(monto),0) FROM abono a WHERE a.id_compra=c.id_compra)>c.total",
    'caja_abono_incoherente': "SELECT COUNT(*) FROM abono a LEFT JOIN movimiento_caja m USING(id_abono) WHERE (a.metodo='EFECTIVO' AND (m.id_abono IS NULL OR m.monto<>a.monto OR m.id_turno<>a.id_turno OR m.tipo<>CASE WHEN a.id_venta IS NOT NULL THEN 'INGRESO' ELSE 'EGRESO' END)) OR (a.metodo<>'EFECTIVO' AND m.id_abono IS NOT NULL)",
    'turnos_abiertos_repetidos': "SELECT COUNT(*) FROM (SELECT id_usuario FROM turno_caja WHERE estado='ABIERTO' GROUP BY id_usuario HAVING COUNT(*)>1) x",
    'correos_usuario_repetidos': 'SELECT COUNT(*) FROM (SELECT lower(trim(correo)) FROM usuario GROUP BY lower(trim(correo)) HAVING COUNT(*)>1) x',
    'documentos_cliente_repetidos': "SELECT COUNT(*) FROM (SELECT upper(trim(nit_dpi)) FROM cliente WHERE nullif(trim(nit_dpi),'') IS NOT NULL GROUP BY upper(trim(nit_dpi)) HAVING COUNT(*)>1) x",
    'documentos_proveedor_repetidos': "SELECT COUNT(*) FROM (SELECT upper(trim(nit)) FROM proveedor WHERE nullif(trim(nit),'') IS NOT NULL GROUP BY upper(trim(nit)) HAVING COUNT(*)>1) x",
    'existencias_negativas': 'SELECT COUNT(*) FROM vista_inventario WHERE existencia_actual<0',
    'total_venta_no_coincide': 'SELECT COUNT(*) FROM venta v WHERE total<>(SELECT coalesce(sum(cantidad*precio_unitario-descuento),0) FROM detalle_venta d WHERE d.id_venta=v.id_venta)',
    'total_compra_no_coincide': 'SELECT COUNT(*) FROM compra c WHERE total<>(SELECT coalesce(sum(cantidad*costo_unitario),0) FROM detalle_compra d WHERE d.id_compra=c.id_compra)',
    'venta_usuario_no_coincide_turno': 'SELECT COUNT(*) FROM venta v JOIN turno_caja t USING(id_turno) WHERE v.id_usuario<>t.id_usuario',
    'venta_sin_detalles': 'SELECT COUNT(*) FROM venta v WHERE NOT EXISTS(SELECT 1 FROM detalle_venta d WHERE d.id_venta=v.id_venta)',
    'compra_sin_detalles': 'SELECT COUNT(*) FROM compra c WHERE NOT EXISTS(SELECT 1 FROM detalle_compra d WHERE d.id_compra=c.id_compra)',
    'sesiones_fechas_invalidas': 'SELECT COUNT(*) FROM sesion_token WHERE expira<=creada OR revocada<creada',
    'origen_venta_producto_o_cantidad_incorrectos': 'SELECT COUNT(*) FROM movimiento_inventario m JOIN detalle_venta d USING(id_detalle_venta) WHERE m.id_producto<>d.id_producto OR m.cantidad<>d.cantidad OR m.costo_unitario<>d.costo_unitario_historico',
    'origen_compra_producto_o_cantidad_incorrectos': 'SELECT COUNT(*) FROM movimiento_inventario m JOIN detalle_compra d USING(id_detalle_compra) WHERE m.id_producto<>d.id_producto OR m.cantidad<>d.cantidad OR m.costo_unitario<>d.costo_unitario',
    'caja_venta_monto_o_metodo_incorrectos': "SELECT COUNT(*) FROM movimiento_caja m JOIN venta v USING(id_venta) WHERE m.monto<>v.total OR v.metodo_pago<>'EFECTIVO'",
}


def auditar(engine):
    with engine.connect() as c:
        c.execute(text('SET TRANSACTION READ ONLY'))
        tablas = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
        relaciones = [dict(r) for r in c.execute(text("""SELECT conrelid::regclass::text AS tabla,
            conname AS nombre, pg_get_constraintdef(oid) AS definicion, convalidated AS validada
            FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace
            ORDER BY conrelid::regclass::text,conname""")).mappings()]
        columnas = [dict(r) for r in c.execute(text("""SELECT t.relname AS tabla,a.attname AS columna,
            format_type(a.atttypid,a.atttypmod) AS tipo,
            CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS acepta_nulo,
            pg_get_expr(d.adbin,d.adrelid) AS predeterminado
            FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
            JOIN pg_attribute a ON a.attrelid=t.oid
            LEFT JOIN pg_attrdef d ON d.adrelid=t.oid AND d.adnum=a.attnum
            WHERE n.nspname='public' AND t.relkind IN ('r','v') AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY t.relname,a.attnum""")).mappings()]
        restricciones = [dict(r) for r in c.execute(text("""SELECT conrelid::regclass::text AS tabla,
            conname AS nombre, contype AS tipo, pg_get_constraintdef(oid) AS definicion
            FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2""")).mappings()]
        indices = [dict(r) for r in c.execute(text("SELECT tablename AS tabla,indexname AS nombre,indexdef AS definicion FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2")).mappings()]
        # Solo identificadores obtenidos del catálogo de PostgreSQL, debidamente citados.
        quote = engine.dialect.identifier_preparer.quote
        conteos = {t: c.execute(text('SELECT COUNT(*) FROM public.' + quote(t))).scalar_one() for t in tablas}
        controles = {nombre: c.execute(text(sql)).scalar_one() for nombre, sql in CONTROLES.items()}
        for r in relaciones:
            if not r['validada']:
                controles['relacion_no_validada:' + r['nombre']] = 1
        return dict(fecha=datetime.now(TZ).isoformat(), base=engine.url.database,
                    tablas=conteos, numero_tablas=len(tablas), numero_relaciones=len(relaciones),
                    relaciones=relaciones, columnas=columnas, restricciones=restricciones,
                    indices=indices, controles=controles,
                    controles_sin_incidencias=all(n == 0 for n in controles.values()))


def main():
    import os
    env = {k: v for k, v in dotenv_values(ROOT / '.env').items() if v is not None}
    env.update(os.environ)
    config = cargar_configuracion(env)
    engine = create_engine(config['SQLALCHEMY_DATABASE_URI'], **config['SQLALCHEMY_ENGINE_OPTIONS'])
    try:
        reporte = auditar(engine)
        destino = ROOT / 'docs' / 'resultado_base_datos.json'
        destino.write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        lineas = ['# Diccionario de la base instalada', '',
                  'Generado por `scripts/auditar_bd.py` a partir de PostgreSQL. No contiene contraseñas ni filas de clientes.', '',
                  '| Tabla | Columna | Tipo | Acepta nulo | Valor predeterminado |',
                  '| --- | --- | --- | --- | --- |']
        for col in reporte['columnas']:
            lineas.append('| ' + ' | '.join(str(col[k] or '—').replace('|','\\|') for k in ('tabla','columna','tipo','acepta_nulo','predeterminado')) + ' |')
        lineas.extend(['', '## Relaciones verificadas', '', '| Tabla hija | Regla |', '| --- | --- |'])
        lineas.extend('| ' + r['tabla'] + ' | ' + r['definicion'] + ' |' for r in reporte['relaciones'])
        (ROOT / 'docs' / 'DICCIONARIO_BASE_DATOS.md').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
        print(json.dumps({k: reporte[k] for k in ('base','numero_tablas','numero_relaciones','tablas','controles','controles_sin_incidencias')}, ensure_ascii=False, indent=2))
        return 0 if reporte['controles_sin_incidencias'] else 1
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
