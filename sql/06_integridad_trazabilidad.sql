-- Se aplica sobre 01 + 04 + 05. Conserva todos los registros e identificadores.
-- Si hay datos incompatibles, revierte todo: nunca los corrige ni borra en silencio.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
SELECT pg_advisory_xact_lock(hashtextextended('puntocom:migracion:06_integridad_trazabilidad',0));

ALTER TABLE movimiento_inventario ADD COLUMN IF NOT EXISTS id_detalle_venta INTEGER REFERENCES detalle_venta(id_detalle_venta);
ALTER TABLE movimiento_inventario ADD COLUMN IF NOT EXISTS id_detalle_compra INTEGER REFERENCES detalle_compra(id_detalle_compra);
ALTER TABLE movimiento_caja ADD COLUMN IF NOT EXISTS id_venta INTEGER REFERENCES venta(id_venta);

-- Las relaciones son opcionales para inventario inicial, ajustes y caja manual.
-- No se infieren relaciones históricas a partir de textos libres.
DO $migracion$
DECLARE r RECORD;
BEGIN
 FOR r IN SELECT * FROM (VALUES
  ('turno_caja','ck_turno_estado', $$estado IN ('ABIERTO','CERRADO')$$),
  ('turno_caja','ck_turno_fechas', $$cierre IS NULL OR cierre>=apertura$$),
  ('venta','ck_venta_estado', $$estado IN ('COMPLETADA','ANULADA')$$),
  ('venta','ck_venta_metodo', $$metodo_pago IN ('EFECTIVO','TARJETA','TRANSFERENCIA')$$),
  ('compra','ck_compra_metodo', $$metodo_pago IN ('EFECTIVO','TARJETA','TRANSFERENCIA','CRÉDITO')$$),
  ('detalle_venta','ck_detalle_descuento', $$descuento<=cantidad::numeric*precio_unitario AND tasa_iva<=100$$),
  ('movimiento_inventario','ck_movimiento_origen', $$id_detalle_venta IS NULL OR id_detalle_compra IS NULL$$),
  ('movimiento_inventario','ck_compra_entrada', $$id_detalle_compra IS NULL OR tipo='ENTRADA'$$),
  ('sesion_token','ck_sesion_fechas', $$expira>creada AND (revocada IS NULL OR revocada>=creada)$$),
  ('sesion_token','ck_sesion_hash', $$refresh_hash ~ '^[0-9a-f]{64}$'$$)
 ) AS x(tabla,nombre,regla) LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('public.'||r.tabla) AND conname=r.nombre) THEN
   EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I CHECK (%s)',r.tabla,r.nombre,r.regla);
  END IF;
 END LOOP;
END $migracion$;

-- Reglas también protegidas ante conexiones SQL directas y peticiones simultáneas.
CREATE UNIQUE INDEX IF NOT EXISTS uq_turno_usuario_abierto ON turno_caja(id_usuario) WHERE estado='ABIERTO';
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_correo_normalizado ON usuario(lower(trim(correo)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_cliente_documento ON cliente(upper(trim(nit_dpi))) WHERE nullif(trim(nit_dpi),'') IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedor_documento ON proveedor(upper(trim(nit))) WHERE nullif(trim(nit),'') IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventario_detalle_venta ON movimiento_inventario(id_detalle_venta,tipo) WHERE id_detalle_venta IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventario_detalle_compra ON movimiento_inventario(id_detalle_compra) WHERE id_detalle_compra IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_caja_venta_tipo ON movimiento_caja(id_venta,tipo) WHERE id_venta IS NOT NULL;

-- PostgreSQL no crea automáticamente índices en las columnas hijas de una FK.
CREATE INDEX IF NOT EXISTS ix_usuario_rol ON usuario(id_rol);
CREATE INDEX IF NOT EXISTS ix_turno_usuario ON turno_caja(id_usuario);
CREATE INDEX IF NOT EXISTS ix_caja_turno_fecha ON movimiento_caja(id_turno,fecha_hora);
CREATE INDEX IF NOT EXISTS ix_producto_categoria ON producto(id_categoria);
CREATE INDEX IF NOT EXISTS ix_venta_cliente ON venta(id_cliente);
CREATE INDEX IF NOT EXISTS ix_venta_usuario_fecha ON venta(id_usuario,fecha_hora);
CREATE INDEX IF NOT EXISTS ix_venta_turno ON venta(id_turno);
CREATE INDEX IF NOT EXISTS ix_venta_anulador ON venta(id_anulador);
CREATE INDEX IF NOT EXISTS ix_venta_fecha ON venta(fecha_hora);
CREATE INDEX IF NOT EXISTS ix_detalle_venta_venta ON detalle_venta(id_venta);
CREATE INDEX IF NOT EXISTS ix_detalle_venta_producto ON detalle_venta(id_producto);
CREATE INDEX IF NOT EXISTS ix_compra_proveedor ON compra(id_proveedor);
CREATE INDEX IF NOT EXISTS ix_compra_usuario ON compra(id_usuario);
CREATE INDEX IF NOT EXISTS ix_compra_fecha ON compra(fecha);
CREATE INDEX IF NOT EXISTS ix_detalle_compra_compra ON detalle_compra(id_compra);
CREATE INDEX IF NOT EXISTS ix_detalle_compra_producto ON detalle_compra(id_producto);
CREATE INDEX IF NOT EXISTS ix_inventario_producto_fecha ON movimiento_inventario(id_producto,fecha_hora);
CREATE INDEX IF NOT EXISTS ix_ajuste_producto ON solicitud_ajuste(id_producto);
CREATE INDEX IF NOT EXISTS ix_ajuste_solicitante ON solicitud_ajuste(id_solicitante);
CREATE INDEX IF NOT EXISTS ix_ajuste_aprobador ON solicitud_ajuste(id_aprobador);
CREATE INDEX IF NOT EXISTS ix_sesion_expira ON sesion_token(expira);
COMMIT;
