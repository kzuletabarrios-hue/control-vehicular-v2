-- ================================================================
-- Control de Acceso y Operaciones CEDI R10
-- Migración: Rondas de Marcación + Novedades + rol recorredor_externo
-- ================================================================

-- 1. Nuevo rol
INSERT INTO roles (nombre, descripcion, permisos) VALUES
  ('recorredor_externo', 'Acceso a Rondas de marcación y Novedades',
   '{"rondas":["read","write"],"novedades":["read","write"]}')
ON CONFLICT (nombre) DO NOTHING;

-- 2. Ampliar permisos en roles existentes para rondas y novedades
UPDATE roles
SET permisos = permisos || '{"rondas":["read","write","delete"],"novedades":["read","write","delete"]}'::jsonb
WHERE nombre = 'admin';

UPDATE roles
SET permisos = permisos || '{"rondas":["read"],"novedades":["read","write"]}'::jsonb
WHERE nombre = 'supervisor';

UPDATE roles
SET permisos = permisos || '{"novedades":["read","write"]}'::jsonb
WHERE nombre IN ('operador','guarda_bodega','guarda_peatonal','guarda_vehicular','consulta');

-- 3. Puntos físicos de marcación
CREATE TABLE IF NOT EXISTS puntos_ronda (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre     TEXT NOT NULL,
    codigo_qr  TEXT NOT NULL UNIQUE,  -- texto codificado en el QR físico instalado
    orden      INT  DEFAULT 1,
    activo     BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_puntos_ronda_activo ON puntos_ronda(activo);
CREATE INDEX IF NOT EXISTS idx_puntos_ronda_orden  ON puntos_ronda(orden);

-- 4. Registros de marcación
CREATE TABLE IF NOT EXISTS rondas (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recorredor_id    UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    punto_id         UUID NOT NULL REFERENCES puntos_ronda(id) ON DELETE CASCADE,
    fecha            DATE NOT NULL DEFAULT CURRENT_DATE,
    hora_marcacion   TIME,
    codigo_escaneado TEXT,            -- auditoría: qué texto leyó el escáner
    estado           TEXT NOT NULL DEFAULT 'ok',  -- ok | novedad | omitido
    observacion      TEXT,
    fotografia       TEXT,            -- NULL si no hubo novedad
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rondas_recorredor ON rondas(recorredor_id);
CREATE INDEX IF NOT EXISTS idx_rondas_fecha      ON rondas(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_rondas_punto      ON rondas(punto_id);

-- 5. Novedades transversales
CREATE TABLE IF NOT EXISTS novedades (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id    UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    modulo_origen TEXT NOT NULL DEFAULT 'general',   -- flota|proveedores|acceso|visitantes|ronda|general
    categoria     TEXT NOT NULL DEFAULT 'otro',       -- seguridad|mantenimiento|logistica|otro
    descripcion   TEXT NOT NULL,
    fotografia    TEXT,
    fecha         DATE NOT NULL DEFAULT CURRENT_DATE,
    hora          TIME,
    estado        TEXT NOT NULL DEFAULT 'abierta',    -- abierta|en_revision|cerrada
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_novedades_usuario ON novedades(usuario_id);
CREATE INDEX IF NOT EXISTS idx_novedades_fecha   ON novedades(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_novedades_estado  ON novedades(estado);
