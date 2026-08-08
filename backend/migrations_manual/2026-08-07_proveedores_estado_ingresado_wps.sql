-- ================================================================
-- Agrega el estado intermedio obligatorio "Ingresado WPS" al ciclo
-- de proveedores.estado_confirmacion.
--
-- Contexto de negocio (decidido por Alejandro, aprobado por Karen,
-- 2026-08-07): hoy el ciclo es pendiente -> confirmado. Se necesita
-- un paso intermedio obligatorio: cuando llega la hora de la cita,
-- Karen ingresa manualmente el vehículo al sistema externo WPS y
-- debe marcarlo en esta app ANTES de poder confirmar la entrada a
-- muelle. Ciclo estricto sin excepción a partir de ahora:
--   pendiente -> ingresado_wps -> confirmado
--
-- No se toca citas-muelles-cedi-r10 (app hermana): confirmado que
-- nadie usa ya su endpoint equivalente, fuera de alcance.
--
-- Estado real verificado en producción (Supabase) el 2026-08-07 por
-- lectura directa de information_schema.columns / pg_constraint
-- ANTES de escribir este script (no se asume nada de lo que sigue):
--
--   estado_confirmacion       TEXT NOT NULL DEFAULT 'confirmado'
--                              CHECK constraint "proveedores_estado_confirmacion_check"
--                              CHECK (estado_confirmacion IN ('pendiente','confirmado'))
--   hora_ingreso_confirmado   TIME WITHOUT TIME ZONE, NULL, sin default
--
-- DEFAULT 'confirmado' en estado_confirmacion es un artefacto de
-- drift (igual naturaleza que el documentado en
-- 2026-08-01_proveedores_estado_confirmacion_columns.sql): NINGÚN
-- insert real de la aplicación depende de él -- tanto
-- backend/routers/proveedores.py (línea 935) como
-- backend/routers/proveedores_publico.py (línea 268) fijan
-- explícitamente vals["estado_confirmacion"] = "pendiente" al crear
-- un registro. Corregirlo a DEFAULT 'pendiente' es de bajo riesgo
-- (no cambia el comportamiento de ningún insert existente) y deja el
-- esquema consistente con el punto de partida real del ciclo.
--
-- HALLAZGO / DESACUERDO PUNTUAL con el patrón propuesto para la FK:
-- la instrucción original pedía calcar "el mismo patrón exacto que
-- creado_por". Verificado en producción: proveedores.creado_por es
-- un UUID SIN foreign key (deuda técnica preexistente, fuera de
-- alcance de esta migración) y es la columna que sí usa el código de
-- la aplicación (proveedores.py líneas 930/1118). Existe una segunda
-- columna, proveedores.creado_por_fk, que SÍ tiene
-- "FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET NULL"
-- pero no la referencia ningún archivo del repo (columna muerta, otro
-- artefacto de drift). Para marcado_wps_por se usa el patrón con FK
-- explícita que pidió la instrucción (íntegro y correcto en sí
-- mismo, y coincide con creado_por_fk), no el patrón real y más
-- débil de creado_por. Se deja constancia por si el equipo quiere
-- limpiar creado_por/creado_por_fk más adelante (no se toca aquí).
--
-- Sin backfill de datos: los registros existentes en 'pendiente'
-- avanzan por el nuevo endpoint que implementa María después. No hay
-- ningún UPDATE sobre filas de proveedores en este script.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS no falla si ya existen; la FK
-- se agrega dentro de un DO $$ IF NOT EXISTS $$ (pg_constraint); el
-- CHECK se reemplaza con DROP CONSTRAINT IF EXISTS + ADD CONSTRAINT
-- (seguro de re-ejecutar: tras el primer DROP, el ADD siempre parte
-- de "no existe"); el ALTER COLUMN SET DEFAULT es idempotente por
-- naturaleza.
-- Fecha: 2026-08-07
-- ================================================================

ALTER TABLE proveedores
  ADD COLUMN IF NOT EXISTS hora_wps        TIME WITHOUT TIME ZONE,
  ADD COLUMN IF NOT EXISTS marcado_wps_por UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'proveedores_marcado_wps_por_fkey'
          AND conrelid = 'proveedores'::regclass
    ) THEN
        ALTER TABLE proveedores
            ADD CONSTRAINT proveedores_marcado_wps_por_fkey
            FOREIGN KEY (marcado_wps_por) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Reemplaza el CHECK existente (nombre real verificado en pg_constraint:
-- proveedores_estado_confirmacion_check) por uno de 3 valores.
ALTER TABLE proveedores
    DROP CONSTRAINT IF EXISTS proveedores_estado_confirmacion_check;

ALTER TABLE proveedores
    ADD CONSTRAINT proveedores_estado_confirmacion_check
    CHECK (estado_confirmacion IN ('pendiente', 'ingresado_wps', 'confirmado'));

-- Corrige el DEFAULT drift 'confirmado' -> 'pendiente' (bajo riesgo,
-- ver justificación arriba).
ALTER TABLE proveedores
    ALTER COLUMN estado_confirmacion SET DEFAULT 'pendiente';

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-07_proveedores_estado_ingresado_wps.sql')
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'proveedores' AND column_name IN ('hora_wps','marcado_wps_por','estado_confirmacion');
--
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'proveedores'::regclass
--   AND conname IN ('proveedores_marcado_wps_por_fkey','proveedores_estado_confirmacion_check');
