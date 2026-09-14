-- ================================================================
-- Control de Acceso y Operaciones CEDI R10
-- Migración: Pausa corta de ronda (baño, entrega de llaves, etc.)
-- ================================================================

ALTER TABLE rondas_ciclos ADD COLUMN IF NOT EXISTS pausa_motivo TEXT;
ALTER TABLE rondas_ciclos ADD COLUMN IF NOT EXISTS pausa_inicio TIMESTAMPTZ;
ALTER TABLE rondas_ciclos ADD COLUMN IF NOT EXISTS pausa_acumulada_min INT NOT NULL DEFAULT 0;

-- estado ahora también admite 'pausada' además de en_curso | completa | incompleta
