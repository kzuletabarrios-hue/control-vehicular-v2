-- ================================================================
-- Documenta (drift retroactivo) proveedores.estado_confirmacion y
-- proveedores.hora_ingreso_confirmado.
--
-- Estas dos columnas ya existen en producción (Supabase) y las usa
-- el backend en:
--   - backend/routers/proveedores.py (líneas 249, 363, 366, 373)
--   - backend/routers/proveedores_publico.py (línea 151, autorregistro QR)
--   - backend/routers/dashboard.py
-- pero no había ningún ALTER TABLE versionado en git que las creara
-- (ni en database/ ni en backend/migrations_manual/) -- drift
-- detectado en auditoría 2026-07-xx y confirmado por lectura directa
-- de information_schema.columns / pg_constraint contra producción el
-- 2026-08-01 (NO se infiere ni se supone nada de lo que sigue):
--
--   estado_confirmacion     TEXT NOT NULL DEFAULT 'confirmado'
--                            CHECK (estado_confirmacion IN ('pendiente','confirmado'))
--   hora_ingreso_confirmado TIME WITHOUT TIME ZONE, NULL, sin default
--
-- Uso real de datos en producción al momento del diagnóstico
-- (1408 filas en proveedores): estado_confirmacion = 'confirmado' en
-- 1407 filas y 'pendiente' en 1 fila -- consistente con el flujo de
-- autorregistro QR (llega 'pendiente', el guarda confirma el ingreso
-- y pasa a 'confirmado' con hora_ingreso_confirmado poblada).
--
-- Este script es documentación-como-código de un estado que YA
-- existe en producción: aplicarlo ahí es un no-op seguro (las
-- columnas y el CHECK ya están). Su valor real es para cualquier otro
-- ambiente (staging, restauración de backup, entorno nuevo de un
-- desarrollador) que hoy NO tendría estas columnas si solo corriera
-- lo que está en git.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS no falla si ya existen; el
-- CHECK se agrega solo si no existe todavía (pg_constraint).
-- Fecha: 2026-08-01
-- ================================================================

ALTER TABLE proveedores
  ADD COLUMN IF NOT EXISTS estado_confirmacion     TEXT NOT NULL DEFAULT 'confirmado',
  ADD COLUMN IF NOT EXISTS hora_ingreso_confirmado  TIME WITHOUT TIME ZONE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'proveedores_estado_confirmacion_check'
          AND conrelid = 'proveedores'::regclass
    ) THEN
        ALTER TABLE proveedores
            ADD CONSTRAINT proveedores_estado_confirmacion_check
            CHECK (estado_confirmacion IN ('pendiente', 'confirmado'));
    END IF;
END $$;

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-01_proveedores_estado_confirmacion_columns.sql')
ON CONFLICT (filename) DO NOTHING;
