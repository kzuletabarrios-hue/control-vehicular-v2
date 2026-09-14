-- ================================================================
-- Permiso de liberación ("liberar") en el módulo "muelles" para el
-- rol `guarda_vehicular` de control-vehicular-v2 -- SIN perder el
-- "read" que ya tiene.
--
-- Contexto de negocio: Alejandro validó ampliar quién puede liberar
-- muelles (tablero de Muelles) a dos roles adicionales además de
-- guarda_bodega, que ya tenía "liberar" desde su alta formal
-- (2026-08-01_roles_guarda_alta_formal.sql). Este archivo cubre el
-- primero de los dos: guarda_vehicular. El endpoint que exige este
-- permiso es PUT /proveedores/{id}/liberar-muelle*
-- (backend/routers/proveedores.py, líneas 1380/1433/1505), que llama
-- require_permiso("muelles", "liberar").
--
-- Estado ANTES (verificado contra el historial de migraciones ya
-- aplicadas en orden -- no asumido): guarda_vehicular NO tenía la
-- clave "muelles" en absoluto hasta
-- 2026-08-25_permiso_muelles_read_guarda_vehicular.sql, que la
-- insertó con el literal ["read"] (deliberadamente sin "liberar",
-- fuera de alcance en esa fecha). Ninguna migración posterior a esa
-- fecha vuelve a tocar la clave "muelles" de guarda_vehicular. Por lo
-- tanto, el estado ANTES de este archivo es:
--
--   guarda_vehicular -> {"flota": ["read","write"],
--                         "muelles": ["read"],
--                         "maestros": ["read"],
--                         "dashboard": ["read"],
--                         "novedades": ["read","write"],
--                         "visitantes": ["read","write"],
--                         "proveedores": ["read","write","editar_cita"],
--                         "visita_vehicular": ["read","write"]}
--
-- (a diferencia de guarda_bodega, que ya tiene {"muelles":
-- ["read","liberar"]} desde su alta formal -- NO se toca esa fila en
-- este archivo, el alcance es únicamente guarda_vehicular).
--
-- Patrón usado: MERGE seguro de array jsonb EXISTENTE, igual que
-- 2026-08-06_permiso_editar_cita.sql (jsonb_set + COALESCE +
-- jsonb_array_elements_text + jsonb_agg(DISTINCT ...)) -- NUNCA
-- jsonb_set(permisos, '{muelles}', '["liberar"]'::jsonb, true), que
-- REEMPLAZARÍA el array completo y BORRARÍA el "read" que
-- guarda_vehicular ya tiene desde el 2026-08-25 (ese es el patrón
-- correcto solo para claves que no existen aún, como en
-- 2026-08-25_permiso_muelles_read_guarda_vehicular.sql). Resultado
-- final: ["liberar","read"] (orden no garantizado por jsonb_agg, sin
-- duplicados). Se usa COALESCE(permisos -> 'muelles', '[]'::jsonb)
-- de forma defensiva por si este archivo llegara a correr en un
-- ambiente donde 2026-08-25 aún no se aplicó -- en ese caso el
-- resultado sería ["liberar"] en vez de perder la migración por un
-- NULL || jsonb.
--
-- Idempotente: jsonb_agg(DISTINCT elem) evita duplicar "liberar" si
-- este archivo se corre más de una vez.
--
-- ADVERTENCIA -- tabla `roles` compartida con citas-muelles-cedi-r10
-- (misma base Supabase, confirmado en
-- 2026-08-07_verifica_rol_coordinador_solo_lectura.sql y
-- 2026-08-25_permiso_muelles_read_guarda_vehicular.sql): esta
-- migración solo toca la fila roles.nombre='guarda_vehicular' y
-- agrega un valor a un array jsonb existente sin quitar ni reemplazar
-- ninguno de los permisos actuales de esa fila. Es aditivo, por lo
-- que no afecta ninguna autorización que la otra app evalúe hoy sobre
-- las acciones que guarda_vehicular ya tenía.
--
-- Riesgo: BAJO. UPDATE de una sola fila, agrega 1 valor a un array
-- jsonb existente. No hay ALTER de esquema ni backfill sobre otras
-- tablas. Amplía la superficie de quién puede liberar un muelle -- es
-- una decisión de negocio ya validada por Alejandro, no una decisión
-- de esta migración.
--
-- Fecha: 2026-09-04
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{muelles}',
    (
        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
        FROM jsonb_array_elements_text(
            COALESCE(permisos -> 'muelles', '[]'::jsonb) || '["liberar"]'::jsonb
        ) AS elem
    ),
    true
)
WHERE nombre = 'guarda_vehicular';

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-09-04_permiso_muelles_liberar_guarda_vehicular.sql',
  'Agrega "liberar" a permisos->''muelles'' del rol guarda_vehicular mediante merge de array jsonb (jsonb_agg DISTINCT), preservando el "read" que ya tenía desde 2026-08-25_permiso_muelles_read_guarda_vehicular.sql. Resultado esperado: ["liberar","read"] (orden no garantizado). No toca guarda_bodega (ya tenía "liberar" desde su alta formal) ni ninguna otra fila de roles.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'muelles' AS muelles, permisos
-- FROM roles
-- WHERE nombre = 'guarda_vehicular';
-- -- Esperado: muelles debe contener EXACTAMENTE "read" y "liberar"
-- -- (2 elementos, sin duplicados), y el resto de claves del jsonb
-- -- (flota, maestros, dashboard, novedades, visitantes, proveedores,
-- -- visita_vehicular) debe seguir intacto tal como en el estado ANTES
-- -- documentado arriba.
