-- ================================================================
-- Control de Acceso y Operaciones CEDI R10
-- Migración: Lógica de turnos para Recorredor Externo (Rondero)
-- 8 rondas obligatorias/turno, ciclos de ronda, apoyos operativos
-- ================================================================

-- 1. Marca el punto base (Tanques) en puntos_ronda
ALTER TABLE puntos_ronda ADD COLUMN IF NOT EXISTS es_base BOOLEAN DEFAULT FALSE;

-- 2. Sembrar los 9 puntos físicos de ronda (idempotente por nombre)
INSERT INTO puntos_ronda (nombre, codigo_qr, orden, es_base, activo) VALUES
  ('Tanques',                                   'CEDI-R10-RONDA-TANQUES',        1, TRUE,  TRUE),
  ('Parqueadero',                                'CEDI-R10-RONDA-PARQUEADERO',    2, FALSE, TRUE),
  ('Malla perimetral Barrio Porvenir',            'CEDI-R10-RONDA-MALLA-PORVENIR', 3, FALSE, TRUE),
  ('Oficina de Conductores',                      'CEDI-R10-RONDA-OF-CONDUCTORES', 4, FALSE, TRUE),
  ('Esquina parqueadero de flota propia',         'CEDI-R10-RONDA-ESQ-FLOTA',      5, FALSE, TRUE),
  ('Malla perimetral lado Este',                   'CEDI-R10-RONDA-MALLA-ESTE',     6, FALSE, TRUE),
  ('Malla perimetral Este (zona media)',          'CEDI-R10-RONDA-MALLA-ESTE-MEDIA',7, FALSE, TRUE),
  ('Malla perimetral Norte',                       'CEDI-R10-RONDA-MALLA-NORTE',    8, FALSE, TRUE),
  ('Control de Acceso',                            'CEDI-R10-RONDA-CONTROL-ACCESO', 9, FALSE, TRUE)
ON CONFLICT (codigo_qr) DO NOTHING;

-- Por si alguno de estos puntos ya existía con otro código QR (creado a mano antes),
-- asegura que Tanques quede marcado como base.
UPDATE puntos_ronda SET es_base = TRUE WHERE nombre = 'Tanques';

-- 3. Ciclos de ronda: una fila = un recorrido completo (1 de las 8 rondas/turno)
CREATE TABLE IF NOT EXISTS rondas_ciclos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recorredor_id   UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL DEFAULT CURRENT_DATE,
    turno           TEXT NOT NULL DEFAULT 'dia',   -- dia | noche
    numero_ronda    INT  NOT NULL,                  -- 1..8
    hora_inicio     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hora_fin        TIMESTAMPTZ,
    estado          TEXT NOT NULL DEFAULT 'en_curso', -- en_curso | completa | incompleta
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ciclos_recorredor ON rondas_ciclos(recorredor_id);
CREATE INDEX IF NOT EXISTS idx_ciclos_fecha      ON rondas_ciclos(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_ciclos_estado     ON rondas_ciclos(estado);

-- 4. rondas: cada marcación ahora pertenece a un ciclo, no solo a un día
ALTER TABLE rondas ADD COLUMN IF NOT EXISTS ciclo_id UUID REFERENCES rondas_ciclos(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_rondas_ciclo ON rondas(ciclo_id);

-- 5. Apoyos operativos (Control de Acceso) — independientes de las rondas
CREATE TABLE IF NOT EXISTS apoyos_operativos (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recorredor_id     UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha             DATE NOT NULL DEFAULT CURRENT_DATE,
    hora_llegada      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hora_salida       TIMESTAMPTZ,
    motivo            TEXT,
    tipo              TEXT NOT NULL DEFAULT 'automatico', -- automatico | manual
    codigo_escaneado  TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_apoyos_recorredor ON apoyos_operativos(recorredor_id);
CREATE INDEX IF NOT EXISTS idx_apoyos_fecha      ON apoyos_operativos(fecha DESC);

-- 6. QR único y exclusivo de Apoyo Operativo (no es un punto de ronda)
CREATE TABLE IF NOT EXISTS puntos_apoyo (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre      TEXT NOT NULL DEFAULT 'Control de Acceso - Apoyo Operativo',
    codigo_qr   TEXT NOT NULL UNIQUE,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO puntos_apoyo (nombre, codigo_qr) VALUES
  ('Control de Acceso - Apoyo Operativo', 'CEDI-R10-APOYO-OPERATIVO')
ON CONFLICT (codigo_qr) DO NOTHING;
