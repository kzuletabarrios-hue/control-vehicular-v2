-- ================================================================
-- Recrea la columna `creado_por_fk` (UUID, FK -> usuarios(id) ON
-- DELETE SET NULL) en control_acceso, flota_propia, proveedores y
-- visitantes -- existe en producción en las 4 tablas, sin ningún
-- ALTER TABLE versionado en git.
--
-- Autor: Jorge Peña (Arquitecto de BD), 2026-09-14. Hallazgo de María
-- corriendo las 46 migraciones de supabase/migrations/ contra una base
-- vacía real: 20260911130929_indices_llaves_foraneas.sql (líneas
-- 41/43/53/58 de ese archivo) crea índices sobre `creado_por_fk` en
-- estas 4 tablas, pero ninguna migración anterior agrega la columna.
-- Karen autorizó el cierre el 2026-09-14 (investigación de solo
-- lectura contra producción, sin escribir nada ahí).
--
-- ── ORIGEN DEL HALLAZGO ───────────────────────────────────────────
-- Esta columna YA estaba señalada -- pero solo en un COMMENTARIO, no
-- con un ALTER TABLE real -- en
-- 20260807220625_proveedores_estado_ingresado_wps.sql (líneas 36-49 de
-- ese archivo), que la describe así, verificado en producción en su
-- momento (2026-08-07): "columna muerta" -- tiene la FK real
-- (`FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET
-- NULL`), pero NINGÚN archivo del backend la referencia; el código de
-- la aplicación usa `creado_por` (UUID SIN foreign key, deuda técnica
-- distinta y separada) para trazabilidad real de quién creó cada
-- registro. `creado_por_fk` parece haber sido un intento -- en algún
-- momento no documentado -- de agregar la FK que le falta a
-- `creado_por`, sin terminar de migrar el código para usarla, y sin
-- que el ALTER TABLE que la creó quedara nunca versionado.
--
-- ── DEFINICIÓN REAL (verificada por SELECT de solo lectura contra
--    producción, 2026-09-14, information_schema.columns +
--    pg_constraint en las 4 tablas) ─────────────────────────────────
-- Idéntica en las 4 tablas, no se asumió -- se confirmó una por una:
--   creado_por_fk   UUID, NULLABLE, sin default
--   FK: FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET NULL
--   (nombres reales de constraint: control_acceso_creado_por_fk_fkey,
--   flota_propia_creado_por_fk_fkey, proveedores_creado_por_fk_fkey,
--   visitantes_creado_por_fk_fkey)
--
-- ── UBICACIÓN EN LA SECUENCIA ─────────────────────────────────────
-- Timestamp justo antes de 20260911130929_indices_llaves_foraneas.sql
-- (único archivo versionado que depende de que esta columna exista --
-- verificado con grep exhaustivo de "creado_por_fk" en todo
-- supabase/migrations/: la única otra coincidencia es un comentario en
-- 20260807220625_proveedores_estado_ingresado_wps.sql que NO requiere
-- que la columna exista para ejecutarse, solo la menciona en prosa).
--
-- Riesgo: NINGUNO -- columna sin uso en código (confirmado, "columna
-- muerta"), agregarla no cambia el comportamiento de ningún endpoint.
-- No se decide aquí si debe limpiarse/eliminarse -- señalado como
-- deuda técnica pendiente en 20260807220625, no se toca en esta
-- migración.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS + FK dentro de un DO $$ IF NOT
-- EXISTS $$ (mismo patrón que el resto del repo).
-- ================================================================

ALTER TABLE control_acceso ADD COLUMN IF NOT EXISTS creado_por_fk UUID;
ALTER TABLE flota_propia   ADD COLUMN IF NOT EXISTS creado_por_fk UUID;
ALTER TABLE proveedores    ADD COLUMN IF NOT EXISTS creado_por_fk UUID;
ALTER TABLE visitantes     ADD COLUMN IF NOT EXISTS creado_por_fk UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'control_acceso_creado_por_fk_fkey' AND conrelid = 'control_acceso'::regclass
    ) THEN
        ALTER TABLE control_acceso
            ADD CONSTRAINT control_acceso_creado_por_fk_fkey
            FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'flota_propia_creado_por_fk_fkey' AND conrelid = 'flota_propia'::regclass
    ) THEN
        ALTER TABLE flota_propia
            ADD CONSTRAINT flota_propia_creado_por_fk_fkey
            FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'proveedores_creado_por_fk_fkey' AND conrelid = 'proveedores'::regclass
    ) THEN
        ALTER TABLE proveedores
            ADD CONSTRAINT proveedores_creado_por_fk_fkey
            FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'visitantes_creado_por_fk_fkey' AND conrelid = 'visitantes'::regclass
    ) THEN
        ALTER TABLE visitantes
            ADD CONSTRAINT visitantes_creado_por_fk_fkey
            FOREIGN KEY (creado_por_fk) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;
END $$;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20260911130900_creado_por_fk_columnas_huerfanas.sql',
  'Recrea la columna creado_por_fk (UUID, FK -> usuarios(id) ON DELETE SET NULL) en control_acceso, flota_propia, proveedores y visitantes -- existía en producción en las 4 tablas sin ALTER TABLE versionado en git. Columna sin uso en código (ver 20260807220625_proveedores_estado_ingresado_wps.sql, que ya la documentaba como "columna muerta"). Necesaria para que 20260911130929_indices_llaves_foraneas.sql no falle contra una base vacía. Hallazgo de María corriendo las 46 migraciones contra una base vacía real, 2026-09-14; verificado por Jorge con SELECT de solo lectura, autorizado por Karen.'
)
ON CONFLICT (filename) DO NOTHING;
-- ================================================================
