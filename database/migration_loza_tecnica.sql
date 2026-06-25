-- ================================================================
-- Control de Acceso y Operaciones CEDI R10
-- Migración: Agregar punto "Loza Técnica" al recorrido de rondas
-- Posición 2 (cerca de Tanques, punto base)
-- ================================================================

-- 1. Desplazar puntos existentes en orden >= 2 para hacer espacio
UPDATE puntos_ronda SET orden = orden + 1 WHERE orden >= 2;

-- 2. Insertar nuevo punto en posición 2
INSERT INTO puntos_ronda (nombre, codigo_qr, orden, es_base, activo)
VALUES ('Loza Técnica', 'CEDI-R10-RONDA-LOZA-TECNICA', 2, FALSE, TRUE)
ON CONFLICT (codigo_qr) DO NOTHING;
