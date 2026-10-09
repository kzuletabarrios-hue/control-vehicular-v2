-- ================================================================
-- DIAGNOSTICO SOLO LECTURA (SELECT) de cédulas en conductores.
-- Correr ANTES de la migración 2026-10-08_conductores_permisos_...
-- No modifica nada. Fecha: 2026-10-08
-- ================================================================

-- 1) Valores inválidos/basura (no participan del índice parcial)
SELECT id, codigo, conductor, n_cedula, activo
FROM conductores
WHERE regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') !~ '^[0-9]{6,10}$'
   OR regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') ~ '^([0-9])\1+$'
ORDER BY conductor;

-- 2) Duplicados entre cédulas válidas normalizadas (si devuelve filas,
--    NO se crea el índice único)
SELECT regexp_replace(n_cedula, '\D', '', 'g') AS cedula_norm,
       count(*) AS veces,
       array_agg(id ORDER BY created_at) AS ids,
       array_agg(conductor ORDER BY created_at) AS nombres
FROM conductores
WHERE regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g') ~ '^[0-9]{6,10}$'
GROUP BY 1 HAVING count(*) > 1;

-- 3) Propuesta de limpieza (NO EJECUTAR sin revisión humana):
--    * Basura: corregir la cédula real desde la pantalla de conductores
--      (guarda_peatonal/admin) o con
--      UPDATE conductores SET n_cedula = '<cedula real>' WHERE id = '<id>';
--      Si no se conoce, dejar como está: el índice parcial la ignora.
--    * Duplicados: fusionar a un registro "ganador" (activo/más antiguo):
--      repuntar flota_propia.conductor_id al ganador y desactivar
--      (activo=false) el perdedor; NO borrar, para conservar trazabilidad.
--      Luego re-correr la sección c) de la migración (idempotente).
