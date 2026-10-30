BEGIN;
SET LOCAL lock_timeout='5s';
SELECT pg_advisory_xact_lock(hashtextextended('puntocom:migracion:09_abonos_credito',0));
ALTER TABLE venta DROP CONSTRAINT IF EXISTS ck_venta_metodo;
ALTER TABLE venta ADD CONSTRAINT ck_venta_metodo CHECK (metodo_pago IN ('EFECTIVO','TARJETA','TRANSFERENCIA','CRÉDITO'));
CREATE TABLE IF NOT EXISTS abono (
 id_abono SERIAL PRIMARY KEY,
 solicitud UUID UNIQUE NOT NULL,
 id_venta INTEGER REFERENCES venta(id_venta),
 id_compra INTEGER REFERENCES compra(id_compra),
 id_usuario INTEGER NOT NULL REFERENCES usuario(id_usuario),
 id_turno INTEGER REFERENCES turno_caja(id_turno),
 fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 monto NUMERIC(12,2) NOT NULL CHECK(monto>0),
 metodo VARCHAR(30) NOT NULL CHECK(metodo IN ('EFECTIVO','TARJETA','TRANSFERENCIA')),
 referencia VARCHAR(100) NOT NULL DEFAULT '',
 CHECK ((id_venta IS NOT NULL)::int+(id_compra IS NOT NULL)::int=1),
 CHECK ((metodo='EFECTIVO')=(id_turno IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_abono_venta ON abono(id_venta);
CREATE INDEX IF NOT EXISTS ix_abono_compra ON abono(id_compra);
ALTER TABLE movimiento_caja ADD COLUMN IF NOT EXISTS id_abono INTEGER UNIQUE REFERENCES abono(id_abono);

CREATE OR REPLACE FUNCTION validar_abono() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE importe NUMERIC; pagado NUMERIC; forma TEXT; situacion TEXT;
BEGIN
 IF NEW.id_venta IS NOT NULL THEN
   SELECT total,metodo_pago,estado INTO importe,forma,situacion FROM venta WHERE id_venta=NEW.id_venta FOR UPDATE;
   SELECT COALESCE(SUM(monto),0) INTO pagado FROM abono WHERE id_venta=NEW.id_venta;
 ELSE
   SELECT total,metodo_pago,'COMPLETADA' INTO importe,forma,situacion FROM compra WHERE id_compra=NEW.id_compra FOR UPDATE;
   SELECT COALESCE(SUM(monto),0) INTO pagado FROM abono WHERE id_compra=NEW.id_compra;
 END IF;
 IF importe IS NULL OR forma<>'CRÉDITO' OR situacion<>'COMPLETADA' OR NEW.monto>importe-pagado THEN
   RAISE EXCEPTION 'Documento no disponible o abono superior al saldo' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS validar_abono ON abono;
CREATE TRIGGER validar_abono BEFORE INSERT ON abono FOR EACH ROW EXECUTE FUNCTION validar_abono();
CREATE OR REPLACE FUNCTION conservar_abono() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Los abonos confirmados no se editan ni eliminan' USING ERRCODE='23514'; END $$;
DROP TRIGGER IF EXISTS conservar_abono ON abono;
CREATE TRIGGER conservar_abono BEFORE UPDATE OR DELETE ON abono FOR EACH ROW EXECUTE FUNCTION conservar_abono();
DROP TRIGGER IF EXISTS auditar_fila ON abono;
CREATE TRIGGER auditar_fila AFTER INSERT ON abono FOR EACH ROW EXECUTE FUNCTION auditar_cambio('id_abono','pagos','id_abono,solicitud,id_venta,id_compra,id_usuario,id_turno,fecha_hora,monto,metodo,referencia');
COMMIT;
