-- ================================================================
-- Bootstrap de public.schema_migrations (fix de orden/dependencia
-- encontrado al validar las 46 migraciones de punta a punta contra
-- una base vacía real, con `supabase db reset`; nadie lo había
-- corrido así hasta ahora -- ver sección 5 de
-- 00000000000000_LEAME_metodologia_y_hallazgos.sql, que ya avisaba
-- que esto podía pasar).
--
-- Problema real encontrado (2026-09-14, María, validación de punta a
-- punta pedida por Alejandro): 3 migraciones se autorregistran con
-- INSERT INTO schema_migrations (...) ANTES de que esa tabla exista
-- en una reconstrucción desde cero:
--   - 20260601101440_roles_guarda_alta_formal_retroactivo.sql
--   - 20260804100000_schema_tablas_huerfanas_drift.sql
--   - 20260804110000_alta_formal_coordinador_retroactivo.sql
-- La tabla schema_migrations se crea recién en
-- 20260805161509_schema_migrations_bitacora.sql. En producción real
-- esto nunca falló porque la tabla ya existía de antes de que esos 3
-- scripts corrieran (se crearon fuera de orden cronológico respecto a
-- su timestamp de archivo -- ver la "única excepción" documentada en
-- la sección 3 del LEAME para el primero de los tres). Contra una base
-- vacía sí revienta: `ERROR: no existe la relación «schema_migrations»`
-- (SQLSTATE 42P01) al aplicar 20260601101440.
--
-- Fix: adelantar SOLO la definición de la tabla (idéntica a la que
-- trae 20260805161509_schema_migrations_bitacora.sql, con
-- CREATE TABLE IF NOT EXISTS) a un punto anterior a la primera
-- migración que la necesita. No se toca el contenido de ninguno de
-- los archivos existentes -- se preserva la copia textual fiel que
-- dejó Jorge. Cuando la ejecución llegue más adelante a
-- 20260805161509, su propio CREATE TABLE IF NOT EXISTS es un no-op
-- (la tabla ya existe) y su backfill retroactivo (ON CONFLICT DO
-- NOTHING) sigue funcionando exactamente igual que antes.
--
-- Riesgo: NULO. Es la misma definición de tabla, solo se crea antes.
-- No se inventa ni se cambia ninguna columna ni dato.
--
-- Fecha: 2026-09-14
-- ================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by  TEXT,
    nota        TEXT
);

COMMENT ON TABLE schema_migrations IS
  'Bitácora de qué archivos de backend/migrations_manual/ ya se aplicaron en este ambiente. Cada migración se autorregistra al final con INSERT ... ON CONFLICT (filename) DO NOTHING. Definición completa (comentario y backfill retroactivo) en 20260805161509_schema_migrations_bitacora.sql -- este archivo solo adelanta la creación de la tabla para que las migraciones anteriores a esa fecha puedan autorregistrarse sin error en una reconstrucción desde cero.';
