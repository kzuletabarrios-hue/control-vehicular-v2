-- ================================================================
-- Control de versiones de esquema (schema_migrations)
-- Paso 2 del plan de Alejandro (2026-08-01): consolidar
-- backend/migrations_manual/ como fuente de verdad del esquema y
-- dejar de depender de la memoria/orden de ejecución manual.
--
-- database/*.sql queda congelado como archivo histórico de cómo
-- nació el esquema original; a partir de 0000 en adelante, todo
-- cambio de esquema (nuevo o retroactivo) se documenta como un
-- archivo en migrations_manual/ con convención de nombre
-- AAAA-MM-DD_descripcion.sql, y se registra aquí al aplicarse.
--
-- Este archivo NO reemplaza una herramienta de migraciones (Alembic,
-- Flyway, etc.) -- es deliberadamente mínimo: una tabla de bitácora
-- que cada script de migración actualiza al final de su propio
-- archivo con un INSERT ... ON CONFLICT DO NOTHING. La ejecución
-- sigue siendo manual (psql / script), pero queda auditable: se
-- puede preguntar "¿qué corrió y cuándo?" con una sola query en vez
-- de inspeccionar información_schema a mano.
--
-- Idempotente: se puede correr más de una vez sin efectos
-- secundarios (CREATE TABLE IF NOT EXISTS).
-- Ejecutar PRIMERO, antes de cualquier otro archivo en
-- migrations_manual/ (de ahí el prefijo 0000).
-- Fecha: 2026-08-01
-- ================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL UNIQUE,
    -- Fecha real de aplicación en ESTE ambiente. Para las 6 filas de
    -- backfill de abajo es una estimación basada en el nombre del
    -- archivo (fecha de creación del script), no la fecha exacta de
    -- ejecución en producción, que no quedó registrada en ningún
    -- lado -- se deja explícito en `nota` para no fingir precisión
    -- que no existe.
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by  TEXT,
    nota        TEXT
);

COMMENT ON TABLE schema_migrations IS
  'Bitácora de qué archivos de backend/migrations_manual/ ya se aplicaron en este ambiente. Cada migración se autorregistra al final con INSERT ... ON CONFLICT (filename) DO NOTHING.';

-- ── Backfill retroactivo ────────────────────────────────────────
-- Estas 6 migraciones (incluida esta misma) ya estaban aplicadas en
-- producción antes de crearse esta tabla de control -- confirmado por
-- lectura directa de information_schema.columns contra Supabase
-- producción el 2026-08-01 (existen actividad_a_desarrollar,
-- dependencia_autoriza, empresa_pertenece en visitantes; anulado en
-- control_acceso; lat/lng en rondas; etc.). Se registran aquí para
-- que la bitácora arranque consistente con la realidad, no en blanco.
INSERT INTO schema_migrations (filename, applied_at, nota) VALUES
  ('0000_schema_migrations.sql',                         NOW(), 'Este archivo. Backfill inicial de la bitácora, 2026-08-01.'),
  ('2026-07-06_proveedores_campos_google_form.sql',      '2026-07-06T00:00:00Z', 'Backfill retroactivo: fecha estimada por nombre de archivo, no por log real de ejecución.'),
  ('2026-07-07_rondas_gps.sql',                          '2026-07-07T00:00:00Z', 'Backfill retroactivo: fecha estimada por nombre de archivo, no por log real de ejecución.'),
  ('2026-07-07_visita_vehicular_empresa_autoriza.sql',   '2026-07-07T00:00:00Z', 'Backfill retroactivo: fecha estimada por nombre de archivo, no por log real de ejecución.'),
  ('2026-07-07_visitantes_campos.sql',                   '2026-07-07T00:00:00Z', 'Backfill retroactivo: fecha estimada por nombre de archivo, no por log real de ejecución.'),
  ('2026-07-07_visitantes_empresa_pertenece.sql',        '2026-07-07T00:00:00Z', 'Backfill retroactivo: fecha estimada por nombre de archivo, no por log real de ejecución.')
ON CONFLICT (filename) DO NOTHING;

-- ── Convención para migraciones nuevas (a partir de ahora) ─────────
-- Al final de cada archivo AAAA-MM-DD_descripcion.sql nuevo, agregar:
--
--   INSERT INTO schema_migrations (filename)
--   VALUES ('AAAA-MM-DD_descripcion.sql')
--   ON CONFLICT (filename) DO NOTHING;
--
-- (ver 2026-08-01_proveedores_estado_confirmacion_columns.sql y
--  2026-08-01_roles_guarda_alta_formal.sql para el patrón aplicado)
