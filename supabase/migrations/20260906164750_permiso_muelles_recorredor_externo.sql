-- ================================================================
-- Permiso de lectura y liberación ("read","liberar") en el módulo
-- "muelles" para el rol `recorredor_externo` de control-vehicular-v2.
--
-- Contexto de negocio: Alejandro validó ampliar quién puede liberar
-- muelles (tablero de Muelles) a dos roles adicionales además de
-- guarda_bodega. Este archivo cubre el segundo: recorredor_externo.
-- Los endpoints involucrados son GET /api/muelles
-- (backend/routers/muelles.py, función tablero(), exige
-- require_permiso("muelles", "read")) y PUT
-- /proveedores/{id}/liberar-muelle* (backend/routers/proveedores.py,
-- líneas 1380/1433/1505, exige require_permiso("muelles", "liberar")).
-- Sin la clave "muelles" en su jsonb de permisos, recorredor_externo
-- recibiría 403 al intentar ver el tablero o liberar un muelle.
--
-- Estado ANTES (verificado contra el historial de migraciones y el
-- origen del rol): recorredor_externo se dio de alta en
-- database/migration_rondas_novedades.sql con permisos
-- {"rondas":["read","write"],"novedades":["read","write"]}. Ninguna
-- migración posterior (revisadas todas en orden en
-- backend/migrations_manual/) agrega la clave "muelles" a este rol --
-- a diferencia de guarda_vehicular, que ya la tenía parcialmente
-- desde 2026-08-25. Por lo tanto, la clave "muelles" NO existe hoy en
-- el jsonb de permisos de recorredor_externo:
--
--   recorredor_externo -> {"rondas": ["read","write"],
--                           "novedades": ["read","write"]}
--
-- (más cualquier ampliación posterior a "novedades"/"rondas" que no
-- afecta a "muelles" y es irrelevante para esta migración).
--
-- Valor escrito: literal ["read","liberar"] completo -- a diferencia
-- de guarda_vehicular (que ya tenía "read" y solo necesitaba fusionar
-- "liberar"), recorredor_externo no tiene ninguno de los dos hoy, así
-- que se insertan ambos de una vez: "read" porque el tablero de
-- Muelles lo exige para poder verlo, y "liberar" porque es el alcance
-- de negocio validado por Alejandro para este rol.
--
-- Patrón usado: jsonb_set(permisos, '{muelles}', '["read","liberar"]'
-- ::jsonb, true) -- mismo patrón que
-- 2026-08-25_permiso_muelles_read_guarda_vehicular.sql para claves
-- que no existen previamente en el jsonb (no hay array previo que
-- perder ni que mezclar con jsonb_agg DISTINCT). Reemplaza con un
-- literal, no concatena. Idempotente: re-ejecutar produce el mismo
-- resultado exacto.
--
-- ADVERTENCIA -- tabla `roles` compartida con citas-muelles-cedi-r10
-- (misma base Supabase, confirmado en
-- 2026-08-07_verifica_rol_coordinador_solo_lectura.sql y
-- 2026-08-25_permiso_muelles_read_guarda_vehicular.sql): esta
-- migración solo toca la fila roles.nombre='recorredor_externo' y
-- agrega una clave jsonb nueva sin tocar las claves existentes
-- ("rondas", "novedades") ni ninguna otra fila de `roles`. Es
-- aditivo, no afecta ninguna autorización que la otra app evalúe hoy
-- sobre las claves que recorredor_externo ya tenía.
--
-- Riesgo: BAJO. UPDATE de una sola fila (roles.nombre=
-- 'recorredor_externo'), agrega 1 clave jsonb nueva. No hay ALTER de
-- esquema, no hay backfill sobre otras tablas ni cambio de
-- comportamiento en endpoints existentes distintos de Muelles.
--
-- Fecha: 2026-09-04
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{muelles}',
    '["read","liberar"]'::jsonb,
    true
)
WHERE nombre = 'recorredor_externo';

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-09-04_permiso_muelles_recorredor_externo.sql',
  'Agrega permisos->''muelles'' = ["read","liberar"] al rol recorredor_externo. La clave no existía antes (verificado contra el alta original en database/migration_rondas_novedades.sql y el historial completo de migrations_manual). Necesario para que recorredor_externo pueda ver el tablero de Muelles (GET /api/muelles) y liberar muelles (PUT /proveedores/{id}/liberar-muelle*) sin recibir 403.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'muelles' AS muelles, permisos
-- FROM roles
-- WHERE nombre = 'recorredor_externo';
-- -- Esperado: muelles = ["read","liberar"], y el resto de claves del
-- -- jsonb ("rondas", "novedades") debe seguir intacto tal como en el
-- -- estado ANTES documentado arriba.
