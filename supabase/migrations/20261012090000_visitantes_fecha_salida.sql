-- ================================================================
-- visitantes.fecha_salida: registrar en migraciones una columna
-- que ya existe en producción.
--
-- Drift detectado por QA (Diego): el router (POST/PUT /visitantes)
-- y el botón "Salida" usan visitantes.fecha_salida, pero ninguna
-- migración la creaba. En producción existe (DATE, verificado, creada
-- a mano); en una BD levantada solo con migraciones el alta y la
-- salida daban 500.
--
-- En PRODUCCIÓN esta migración NO HACE NADA (la columna ya existe;
-- ADD COLUMN IF NOT EXISTS es no-op). Solo alinea las BD nuevas/locales.
--
-- Idempotente. Riesgo: NULO en producción.
-- ================================================================

SET lock_timeout = '5s';

ALTER TABLE public.visitantes ADD COLUMN IF NOT EXISTS fecha_salida DATE;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20261012090000_visitantes_fecha_salida.sql',
  'Registra visitantes.fecha_salida (DATE) en migraciones: ya existía en producción (creada a mano), no-op allí; corrige el drift para BD nuevas/locales.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo) ──────────────────────────────────
-- SELECT data_type FROM information_schema.columns
--  WHERE table_name = 'visitantes' AND column_name = 'fecha_salida';  -- date
