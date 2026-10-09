-- ================================================================
-- BACKFILL MANUAL (NO se ejecuta con la migración). Opcional.
-- Rellena flota_propia.conductor_id cuando el texto `conductor`
-- (MAYÚSCULAS, sin espacios en los bordes) coincide con UN ÚNICO
-- nombre del maestro conductores. Si el nombre está repetido en el
-- maestro, no se toca (ambiguo). Solo filas con conductor_id NULL:
-- re-ejecutable. No modifica `conductor` ni codigo_conductor.
-- Requiere la migración 2026-10-08_conductores_permisos_... aplicada.
-- Fecha: 2026-10-08
-- ================================================================

-- Previsualización (SELECT), correr primero:
-- SELECT count(*) FROM flota_propia f JOIN (
--   SELECT upper(btrim(conductor)) AS nom, (array_agg(id))[1] AS id
--   FROM conductores GROUP BY 1 HAVING count(*) = 1) c
--   ON upper(btrim(f.conductor)) = c.nom
-- WHERE f.conductor_id IS NULL;

BEGIN;

UPDATE flota_propia f
SET conductor_id = c.id
FROM (
    SELECT upper(btrim(conductor)) AS nom, (array_agg(id))[1] AS id
    FROM conductores
    GROUP BY 1
    HAVING count(*) = 1
) c
WHERE f.conductor_id IS NULL
  AND f.conductor IS NOT NULL
  AND upper(btrim(f.conductor)) = c.nom;

-- Revisar el conteo reportado y luego ejecutar COMMIT; (o ROLLBACK;).
