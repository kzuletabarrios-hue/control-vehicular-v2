-- ================================================================
-- Regulariza drift en flota_propia: 8 columnas que existen en
-- PRODUCCIÓN (verificado hoy, 2026-09-26, con lectura de solo
-- lectura de information_schema.columns contra Supabase producción)
-- pero que NINGUNA migración de este repo crea:
--
--   obs_salida text, foto_salida text, obs_llegada text,
--   foto_llegada text, fecha_salida date, fecha_llegada date,
--   tipo_sello text, tipo_sello_entrada text
--
-- Aparecen en producción justo después de creado_por_fk (columna a
-- su vez regularizada en 20260911130900_creado_por_fk_columnas_huerfanas.sql),
-- todas nullable, sin default -- mismo patrón de "columna creada a
-- mano contra producción, nunca versionada" que ese caso.
--
-- ── CORRECCIÓN AL DIAGNÓSTICO INICIAL (verificado con grep antes de
--    escribir esta migración) ──────────────────────────────────────
-- De las 8 columnas reportadas, 2 SÍ tienen migración existente:
-- `fecha_salida` y `fecha_llegada` ya se agregan en
-- 20260626114921_fecha_salida_llegada.sql. No son drift real -- se
-- incluyen aquí solo con ADD COLUMN IF NOT EXISTS (no-op en cualquier
-- ambiente donde esa migración ya corrió) por dos razones: (1) esta
-- migración debe dejar el esquema completo de flota_propia en un solo
-- lugar y ser aplicable de forma independiente/idempotente sin asumir
-- que 20260626114921 ya corrió en el ambiente de destino, y (2) evita
-- que quien lea el drift original (que sí las reportó como faltantes)
-- vuelva a investigarlas por separado. Las 6 columnas restantes
-- (`obs_salida`, `foto_salida`, `obs_llegada`, `foto_llegada`,
-- `tipo_sello`, `tipo_sello_entrada`) son drift real: no aparecen en
-- ninguna migración de supabase/migrations/ ni en supabase/seed.sql.
--
-- ── USO CONFIRMADO EN BACKEND ────────────────────────────────────
-- backend/routers/flota.py (POST / y PUT /{id}, listas `campos`)
-- ya lee y escribe las 8 columnas como texto/fecha libre, en el mismo
-- patrón que las columnas gemelas que sí existen desde el esquema
-- base (20260601101420_schema_base.sql):
--   tipo_sello / tipo_sello_entrada   -> par de `sello` / `sello_entrada` (TEXT)
--   obs_salida / obs_llegada         -> par de `observacion`          (TEXT)
--   foto_salida / foto_llegada       -> par de `foto_url`             (TEXT)
--   fecha_salida / fecha_llegada     -> DATE (ya migradas, ver arriba)
-- El backend no impone NOT NULL, default ni formato particular sobre
-- ninguna de las 8 -- son opcionales y se guardan tal cual llega el
-- body del request. No se detectó uso en busqueda.py, dashboard.py ni
-- export.py. Por lo tanto esta migración NO agrega defaults ni
-- constraints que producción no tenga: solo columnas TEXT/DATE
-- nullable, igual que en prod.
--
-- Riesgo: NULO en producción (ADD COLUMN IF NOT EXISTS sobre columnas
-- que ya existen ahí es no-op). En cualquier otro ambiente (local,
-- CI) donde no existan, deja el esquema igual a producción sin
-- reescribir la tabla de forma bloqueante (Postgres moderno con
-- columnas nullable sin default no reescribe filas existentes). No
-- rompe ningún SELECT/INSERT/UPDATE existente: solo agrega columnas,
-- no modifica ni elimina ninguna.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS en las 8; bitácora con
-- INSERT ... ON CONFLICT DO NOTHING.
-- ================================================================

ALTER TABLE flota_propia
  ADD COLUMN IF NOT EXISTS obs_salida        TEXT,
  ADD COLUMN IF NOT EXISTS foto_salida       TEXT,
  ADD COLUMN IF NOT EXISTS obs_llegada       TEXT,
  ADD COLUMN IF NOT EXISTS foto_llegada      TEXT,
  ADD COLUMN IF NOT EXISTS fecha_salida      DATE,
  ADD COLUMN IF NOT EXISTS fecha_llegada     DATE,
  ADD COLUMN IF NOT EXISTS tipo_sello        TEXT,
  ADD COLUMN IF NOT EXISTS tipo_sello_entrada TEXT;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20260926120000_flota_propia_columnas_huerfanas_salida_llegada.sql',
  'Regulariza drift en flota_propia: agrega (si faltan) obs_salida, foto_salida, obs_llegada, foto_llegada, tipo_sello, tipo_sello_entrada (TEXT, nullable, sin default) -- existían en producción sin migración versionada, creadas a mano. Incluye también fecha_salida/fecha_llegada (DATE) con ADD COLUMN IF NOT EXISTS por completitud/idempotencia, aunque esas 2 ya tenían migración propia en 20260626114921_fecha_salida_llegada.sql y por tanto son no-op en cualquier ambiente donde esa migración ya corrió. Confirmado con grep exhaustivo (supabase/migrations/ y supabase/seed.sql) que las otras 6 no existían en ningún archivo versionado, y con lectura de backend/routers/flota.py que las 8 ya se usan en INSERT/UPDATE de POST / y PUT /{id} como campos de texto/fecha libres, sin default ni constraint esperado. Verificado por Jorge (Arquitecto de BD) el 2026-09-26 contra el estado real de producción reportado por Alejandro/usuario.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'flota_propia'
--   AND column_name IN (
--     'obs_salida','foto_salida','obs_llegada','foto_llegada',
--     'fecha_salida','fecha_llegada','tipo_sello','tipo_sello_entrada'
--   )
-- ORDER BY column_name;
-- ================================================================
