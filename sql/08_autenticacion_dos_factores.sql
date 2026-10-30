-- Configuración privada de MFA: nunca copiar estas tablas a la bitácora.
BEGIN;
SET LOCAL lock_timeout='10s';
SELECT pg_advisory_xact_lock(hashtextextended('puntocom:migracion:08_mfa',0));
CREATE TABLE IF NOT EXISTS usuario_mfa (
 id_usuario INTEGER PRIMARY KEY REFERENCES usuario(id_usuario) ON DELETE CASCADE,
 activo BOOLEAN NOT NULL DEFAULT FALSE,
 secreto_cifrado TEXT,
 pendiente_cifrado TEXT,
 pendiente_hasta TIMESTAMPTZ,
 pendiente_sesion UUID,
 ultimo_paso BIGINT NOT NULL DEFAULT -1,
 version INTEGER NOT NULL DEFAULT 0 CHECK(version>=0),
 CHECK(NOT activo OR secreto_cifrado IS NOT NULL),
 CHECK((pendiente_cifrado IS NULL AND pendiente_hasta IS NULL AND pendiente_sesion IS NULL)
    OR (pendiente_cifrado IS NOT NULL AND pendiente_hasta IS NOT NULL AND pendiente_sesion IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS reto_mfa (
 huella VARCHAR(64) PRIMARY KEY CHECK(huella ~ '^[0-9a-f]{64}$'),
 id_usuario INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
 version INTEGER NOT NULL,
 credencial_hash VARCHAR(64) NOT NULL,
 expira TIMESTAMPTZ NOT NULL,
 consumido TIMESTAMPTZ,
 intentos INTEGER NOT NULL DEFAULT 0 CHECK(intentos BETWEEN 0 AND 5)
);
CREATE INDEX IF NOT EXISTS ix_reto_mfa_usuario ON reto_mfa(id_usuario);
CREATE INDEX IF NOT EXISTS ix_reto_mfa_expira ON reto_mfa(expira);
CREATE TABLE IF NOT EXISTS codigo_respaldo (
 id_codigo BIGSERIAL PRIMARY KEY,
 id_usuario INTEGER NOT NULL REFERENCES usuario(id_usuario) ON DELETE CASCADE,
 huella VARCHAR(64) NOT NULL CHECK(huella ~ '^[0-9a-f]{64}$'),
 usado TIMESTAMPTZ,
 UNIQUE(id_usuario,huella)
);
CREATE TABLE IF NOT EXISTS limite_auth (
 clave VARCHAR(64) PRIMARY KEY CHECK(clave ~ '^[0-9a-f]{64}$'),
 intentos INTEGER NOT NULL CHECK(intentos>0),
 inicio TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_limite_auth_inicio ON limite_auth(inicio);
COMMIT;
