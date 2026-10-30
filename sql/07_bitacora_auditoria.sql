-- Auditoría transaccional y aditiva. No reconstruye hechos anteriores.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SELECT pg_advisory_xact_lock(hashtextextended('puntocom:migracion:07_bitacora',0));
CREATE TABLE IF NOT EXISTS bitacora_auditoria (
 id_evento BIGSERIAL PRIMARY KEY,
 fecha_hora TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 id_usuario INTEGER,
 usuario_nombre TEXT NOT NULL,
 usuario_rol TEXT,
 origen TEXT NOT NULL CHECK(origen IN ('api','monolito','base_datos')),
 solicitud UUID,
 transaccion BIGINT NOT NULL DEFAULT txid_current(),
 modulo TEXT NOT NULL,
 entidad TEXT NOT NULL,
 registro TEXT,
 accion TEXT NOT NULL,
 operacion TEXT NOT NULL CHECK(operacion IN ('INSERT','UPDATE','DELETE','TRUNCATE','ACCESO')),
 antes JSONB,
 despues JSONB
);
-- Sin FK al usuario: una baja física autorizada no debe borrar su autoría histórica.
CREATE INDEX IF NOT EXISTS ix_bitacora_fecha ON bitacora_auditoria(fecha_hora DESC,id_evento DESC);
CREATE INDEX IF NOT EXISTS ix_bitacora_usuario_fecha ON bitacora_auditoria(id_usuario,fecha_hora DESC);
CREATE INDEX IF NOT EXISTS ix_bitacora_modulo_fecha ON bitacora_auditoria(modulo,fecha_hora DESC);
CREATE INDEX IF NOT EXISTS ix_bitacora_solicitud ON bitacora_auditoria(solicitud);

CREATE OR REPLACE FUNCTION proteger_bitacora() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'La bitácora es de solo lectura: no se permite modificar ni borrar su historial.' USING ERRCODE='23514';
END $$;
DROP TRIGGER IF EXISTS bitacora_solo_insertar ON bitacora_auditoria;
CREATE TRIGGER bitacora_solo_insertar BEFORE UPDATE OR DELETE OR TRUNCATE ON bitacora_auditoria
 FOR EACH STATEMENT EXECUTE FUNCTION proteger_bitacora();

CREATE OR REPLACE FUNCTION auditar_cambio() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public AS $$
DECLARE
 previo JSONB; nuevo JSONB; raw_previo JSONB; raw_nuevo JSONB;
 responsable INTEGER; nombre TEXT; rol_actual TEXT; fuente TEXT; peticion UUID;
 evento TEXT; clave TEXT; campos TEXT[]; credencial BOOLEAN := FALSE;
BEGIN
 -- Lista positiva por tabla: nuevas columnas privadas nunca se copian automáticamente.
 campos := string_to_array(TG_ARGV[2],',');
 IF TG_OP IN ('UPDATE','DELETE') THEN
   raw_previo := to_jsonb(OLD);
   SELECT jsonb_object_agg(key,value) INTO previo FROM jsonb_each(raw_previo) WHERE key=ANY(campos);
 END IF;
 IF TG_OP IN ('UPDATE','INSERT') THEN
   raw_nuevo := to_jsonb(NEW);
   SELECT jsonb_object_agg(key,value) INTO nuevo FROM jsonb_each(raw_nuevo) WHERE key=ANY(campos);
 END IF;
 IF TG_TABLE_NAME='usuario' AND TG_OP='UPDATE' THEN
   credencial := raw_previo->'hash_contrasena' IS DISTINCT FROM raw_nuevo->'hash_contrasena';
 END IF;
 IF TG_OP='UPDATE' AND previo IS NOT DISTINCT FROM nuevo AND NOT credencial THEN RETURN NULL; END IF;
 evento := CASE TG_OP WHEN 'INSERT' THEN 'CREAR' WHEN 'DELETE' THEN 'ELIMINAR'
                     WHEN 'TRUNCATE' THEN 'VACIAR_TABLA' ELSE 'ACTUALIZAR' END;
 IF TG_OP='UPDATE' THEN
   IF previo->'estado' IS DISTINCT FROM nuevo->'estado' THEN
     evento := CASE nuevo->>'estado' WHEN 'true' THEN 'ACTIVAR' WHEN 'false' THEN 'DESACTIVAR'
       WHEN 'ANULADA' THEN 'ANULAR' WHEN 'CERRADO' THEN 'CERRAR_CAJA'
       WHEN 'APROBADA' THEN 'APROBAR_AJUSTE' WHEN 'RECHAZADA' THEN 'RECHAZAR_AJUSTE' ELSE evento END;
   ELSIF TG_TABLE_NAME='usuario' AND previo->'id_rol' IS DISTINCT FROM nuevo->'id_rol' THEN
     evento := 'CAMBIAR_ROL';
   ELSIF credencial THEN evento := 'CAMBIAR_CLAVE';
   END IF;
 END IF;
 IF TG_TABLE_NAME='turno_caja' AND TG_OP='INSERT' THEN evento := 'ABRIR_CAJA'; END IF;
 IF credencial THEN nuevo := nuevo || jsonb_build_object('credencial_modificada',true); END IF;
 clave := COALESCE(raw_nuevo,raw_previo)->>TG_ARGV[0];
 responsable := NULLIF(current_setting('puntocom.usuario',true),'')::integer;
 SELECT u.nombre,r.nombre INTO nombre,rol_actual FROM public.usuario u JOIN public.rol r USING(id_rol)
   WHERE u.id_usuario=responsable;
 -- Conservar el perfil que realizó la petición aunque modifique su propio rol.
 nombre := COALESCE(NULLIF(current_setting('puntocom.nombre',true),''),nombre);
 rol_actual := COALESCE(NULLIF(current_setting('puntocom.rol',true),''),rol_actual);
 fuente := COALESCE(NULLIF(current_setting('puntocom.origen',true),''),'base_datos');
 peticion := NULLIF(current_setting('puntocom.solicitud',true),'')::uuid;
 INSERT INTO public.bitacora_auditoria(id_usuario,usuario_nombre,usuario_rol,origen,solicitud,
                                     modulo,entidad,registro,accion,operacion,antes,despues)
 VALUES(responsable,COALESCE(nombre,'Sistema / acceso directo a la base'),rol_actual,fuente,peticion,
        TG_ARGV[1],TG_TABLE_NAME,clave,evento,TG_OP,previo,nuevo);
 RETURN NULL;
END $$;

DO $$
DECLARE t RECORD;
BEGIN
 FOR t IN SELECT * FROM (VALUES
 ('producto','id_producto','productos','id_producto,id_categoria,codigo,codigo_barras,nombre,marca,unidad,costo,precio_venta,stock_minimo,estado'),
 ('categoria','id_categoria','categorias','id_categoria,nombre,descripcion,estado'),
 ('cliente','id_cliente','clientes','id_cliente,nombre_razon_social,nit_dpi,telefono,correo,direccion_fiscal,estado'),
 ('proveedor','id_proveedor','proveedores','id_proveedor,razon_social,nit,contacto,telefono,correo,direccion,estado'),
 ('usuario','id_usuario','usuarios','id_usuario,id_rol,nombre,correo,estado'),
 ('rol','id_rol','usuarios','id_rol,nombre'),
 ('venta','id_venta','ventas','id_venta,id_cliente,id_usuario,id_turno,numero_ticket,fecha_hora,metodo_pago,total,estado,id_anulador,fecha_anulacion,motivo_anulacion'),
 ('detalle_venta','id_detalle_venta','ventas','id_detalle_venta,id_venta,id_producto,cantidad,precio_unitario,costo_unitario_historico,descuento,tasa_iva'),
 ('compra','id_compra','compras','id_compra,id_proveedor,id_usuario,numero_factura,fecha,metodo_pago,total'),
 ('detalle_compra','id_detalle_compra','compras','id_detalle_compra,id_compra,id_producto,cantidad,costo_unitario'),
 ('turno_caja','id_turno','caja','id_turno,id_usuario,apertura,cierre,fondo_inicial,efectivo_contado,estado'),
 ('movimiento_caja','id_movimiento_caja','caja','id_movimiento_caja,id_turno,fecha_hora,tipo,concepto,monto,id_venta'),
 ('movimiento_inventario','id_movimiento_inventario','inventario','id_movimiento_inventario,id_producto,fecha_hora,tipo,cantidad,costo_unitario,motivo,id_usuario,id_detalle_venta,id_detalle_compra'),
 ('solicitud_ajuste','id_solicitud','inventario','id_solicitud,id_producto,id_solicitante,fecha_solicitud,existencia_sistema,cantidad_contada,diferencia,motivo,estado,id_aprobador,fecha_resolucion,motivo_resolucion,id_movimiento')
 ) AS lista(tabla,pk,modulo,campos) LOOP
   EXECUTE format('DROP TRIGGER IF EXISTS auditar_fila ON public.%I',t.tabla);
   EXECUTE format('CREATE TRIGGER auditar_fila AFTER INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.auditar_cambio(%L,%L,%L)',t.tabla,t.pk,t.modulo,t.campos);
   EXECUTE format('DROP TRIGGER IF EXISTS auditar_vaciado ON public.%I',t.tabla);
   EXECUTE format('CREATE TRIGGER auditar_vaciado AFTER TRUNCATE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.auditar_cambio(%L,%L,%L)',t.tabla,t.pk,t.modulo,t.campos);
 END LOOP;
END $$;
COMMIT;
