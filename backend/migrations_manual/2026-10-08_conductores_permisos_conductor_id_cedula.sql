-- ================================================================
-- Alta peatonal de conductores: permisos, flota_propia.conductor_id
-- e índice único de cédula (condicional).
--
-- Decisión de negocio (usuaria + Alejandro): solo guarda_peatonal y
-- admin crean/editan conductores del maestro; bodega y vehicular
-- solo eligen de la lista; coordinador solo lectura.
--
-- a) Nuevo recurso de permisos "conductores" (MERGE aditivo de array
--    jsonb: no reemplaza ni quita nada, ni en esta clave ni en otros
--    recursos). Tabla roles compartida con citas-muelles-cedi-r10:
--    solo se agrega una clave nueva, no cambia autorizaciones que
--    esa app evalúe hoy.
-- b) flota_propia.conductor_id UUID NULL -> conductores(id)
--    ON DELETE SET NULL + índice parcial. Aditivo; no rompe queries
--    ni inserts existentes (columna nullable sin default).
--    flota_propia.codigo_conductor (INT, casi siempre NULL) y
--    flota_propia.conductor (texto) NO se tocan.
-- c) Índice único de cédula normalizada (solo dígitos), PARCIAL:
--    excluye valores inválidos (vacíos/basura como 'CC', menos de 6
--    o más de 10 dígitos, o un solo dígito repetido). Se crea
--    ÚNICAMENTE si entre los valores válidos no hay duplicados; si
--    los hay, emite NOTICE y NO lo crea (ver listado de duplicados
--    en 2026-10-08_conductores_cedula_diagnostico.sql).
--    El índice parcial no limpia ni modifica datos: la fila basura
--    sigue existiendo, simplemente no participa de la unicidad.
-- d) El backfill de conductor_id NO va aquí:
--    2026-10-08_conductores_backfill_flota_conductor_id.sql (manual).
--
-- Idempotente. Riesgo: BAJO (ADD COLUMN nullable = cambio de
-- catálogo, sin reescritura de tabla; lock breve).
-- Rollback: rollback/2026-10-08_conductores_permisos_conductor_id_cedula_ROLLBACK.sql
-- Fecha: 2026-10-08
-- ================================================================

-- ── a) Permisos del recurso "conductores" ───────────────────────
WITH nuevos(rol, acciones) AS (
    VALUES
        ('admin',            '["read","write","delete"]'::jsonb),
        ('guarda_peatonal',  '["read","write"]'::jsonb),
        ('coordinador',      '["read"]'::jsonb),
        ('guarda_bodega',    '["read"]'::jsonb),
        ('guarda_vehicular', '["read"]'::jsonb),
        ('consulta',         '["read"]'::jsonb)
)
UPDATE roles r
SET permisos = jsonb_set(
    COALESCE(r.permisos, '{}'::jsonb),
    '{conductores}',
    (
        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
        FROM jsonb_array_elements_text(
            COALESCE(r.permisos -> 'conductores', '[]'::jsonb) || n.acciones
        ) AS elem
    ),
    true
)
FROM nuevos n
WHERE r.nombre = n.rol;

-- ── b) flota_propia.conductor_id ────────────────────────────────
ALTER TABLE flota_propia
    ADD COLUMN IF NOT EXISTS conductor_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'flota_propia_conductor_id_fkey'
          AND conrelid = 'public.flota_propia'::regclass
    ) THEN
        ALTER TABLE flota_propia
            ADD CONSTRAINT flota_propia_conductor_id_fkey
            FOREIGN KEY (conductor_id) REFERENCES conductores(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_flota_propia_conductor_id
    ON flota_propia (conductor_id)
    WHERE conductor_id IS NOT NULL;

-- ── c) Índice único parcial de cédula normalizada ───────────────
DO $$
DECLARE
    n_dup INT;
BEGIN
    SELECT count(*) INTO n_dup FROM (
        SELECT regexp_replace(n_cedula, '\D', '', 'g') AS ced
        FROM conductores
        WHERE regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') ~ '^[0-9]{6,10}$'
          AND regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') !~ '^([0-9])\1+$'
        GROUP BY 1 HAVING count(*) > 1
    ) d;

    IF n_dup > 0 THEN
        RAISE NOTICE 'uq_conductores_cedula_norm NO creado: % cedula(s) normalizada(s) duplicada(s). Ver 2026-10-08_conductores_cedula_diagnostico.sql', n_dup;
    ELSE
        CREATE UNIQUE INDEX IF NOT EXISTS uq_conductores_cedula_norm
            ON conductores ((regexp_replace(n_cedula, '\D', '', 'g')))
            WHERE regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') ~ '^[0-9]{6,10}$'
              AND regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') !~ '^([0-9])\1+$';
    END IF;
END $$;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-10-08_conductores_permisos_conductor_id_cedula.sql',
  'Recurso de permisos "conductores" (admin read/write/delete; guarda_peatonal read/write; coordinador, guarda_bodega, guarda_vehicular, consulta read) por merge aditivo; flota_propia.conductor_id UUID NULL FK conductores(id) ON DELETE SET NULL + índice parcial; índice único parcial uq_conductores_cedula_norm (cédula solo dígitos, 6-10 dígitos) solo si no hay duplicados válidos. Sin backfill (archivo manual aparte).'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo) ──────────────────────────────────
-- SELECT nombre, permisos->'conductores' FROM roles ORDER BY nombre;
-- SELECT indexname FROM pg_indexes WHERE indexname IN
--   ('uq_conductores_cedula_norm','idx_flota_propia_conductor_id');
