-- Migración aditiva para la API; nunca modifica ventas ni inventario.
CREATE TABLE IF NOT EXISTS sesion_token (
    id_sesion UUID PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuario(id_usuario),
    refresh_hash VARCHAR(64) NOT NULL,
    creada TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira TIMESTAMPTZ NOT NULL,
    revocada TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sesion_token_usuario ON sesion_token(id_usuario);
