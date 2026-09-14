-- ================================================================
-- Permiso de solo lectura ("read") en el módulo "muelles" para el
-- rol `guarda_vehicular` de control-vehicular-v2.
--
-- Contexto de negocio: Alejandro detectó este bloqueante durante el
-- diseño de una función nueva (tablero de muelles al confirmar
-- ingreso en Proveedores, todavía no construida -- la construye
-- María después de esta migración). El endpoint GET /api/muelles
-- (backend/routers/muelles.py, función tablero(), líneas 120-123)
-- exige require_permiso("muelles", "read"). Sin la clave "muelles"
-- en su jsonb de permisos, cualquier guarda_vehicular que use ese
-- flujo nuevo recibiría 403 al intentar ver el tablero para elegir
-- un muelle.
--
-- Estado ANTES (verificado contra el historial de migraciones ya
-- aplicadas en orden, no asumido -- ninguna migración en git desde
-- 2026-08-01_roles_guarda_alta_formal.sql hasta hoy agrega ni toca
-- la clave "muelles" del rol guarda_vehicular):
--
--   guarda_vehicular -> {"flota": ["read","write"],
--                         "maestros": ["read"],
--                         "dashboard": ["read"],
--                         "novedades": ["read","write"],
--                         "visitantes": ["read","write"],
--                         "proveedores": ["read","write","editar_cita"],
--                         "visita_vehicular": ["read","write"]}
--
-- (permisos->'proveedores' incluye "editar_cita" desde
-- 2026-08-06_permiso_editar_cita.sql, que agrega ese valor a todo
-- rol con "write" en "proveedores" -- guarda_vehicular calificaba.
-- Irrelevante para esta migración, se documenta solo para que el
-- estado ANTES sea exacto). La clave "muelles" NO existe en el jsonb
-- de guarda_vehicular -- a diferencia de guarda_bodega, que sí la
-- tiene desde su alta formal: {"muelles": ["read","liberar"]}.
--
-- Valor escrito: literal ["read"] únicamente. NO se agrega "liberar"
-- -- ese permiso ya lo tiene guarda_bodega para liberar el muelle de
-- descargue (ver PUT /proveedores/{id}/liberar-muelle* en
-- backend/routers/proveedores.py, líneas 1380/1433/1505, que exige
-- require_permiso("muelles", "liberar")) y NO es parte de este
-- alcance. La escritura real del flujo nuevo (confirmar ingreso y
-- asignar muelle) sigue pasando por PUT /proveedores/{id}/confirmar
-- (backend/routers/proveedores.py, línea 1313), que exige
-- require_permiso("proveedores", "write") -- permiso que
-- guarda_vehicular YA tiene hoy (verificado arriba). Esta migración
-- es puramente de LECTURA del tablero, no habilita ninguna escritura
-- nueva sobre "muelles".
--
-- Patrón usado: jsonb_set(permisos, '{muelles}', '["read"]'::jsonb,
-- true) -- mismo patrón que
-- 2026-08-11_permiso_visitantes_acceso_coordinador.sql para claves
-- que no existen previamente en el jsonb (no hay array previo que
-- perder ni que mezclar con jsonb_agg DISTINCT). Reemplaza con un
-- literal, no concatena -- inmune a la trampa de NULL || jsonb.
-- Idempotente: re-ejecutar produce el mismo resultado exacto.
--
-- ADVERTENCIA -- tabla `roles` compartida con citas-muelles-cedi-r10:
-- esta migración solo toca la fila roles.nombre='guarda_vehicular' y
-- agrega una clave jsonb nueva sin tocar las 7 claves existentes ni
-- ninguna otra fila de `roles`. Es aditivo (no quita ni reemplaza
-- ningún permiso actual de guarda_vehicular) y no afecta ninguna
-- autorización que otra app evalúe hoy sobre las claves que ya tenía.
--
-- Riesgo: BAJO. UPDATE de una sola fila (roles.nombre='guarda_vehicular'),
-- agrega 1 clave jsonb nueva. No hay ALTER de esquema, no hay backfill
-- sobre otras tablas ni cambio de comportamiento en endpoints que no
-- sean el nuevo GET /api/muelles (que hoy ya funciona para
-- guarda_bodega, admin, coordinador y supervisor con este mismo
-- permiso -- solo se extiende a guarda_vehicular).
--
-- Solo agrega permiso de lectura sobre el tablero de muelles -- no
-- implementa el flujo de confirmación en backend ni frontend (eso lo
-- construye María en una tarea posterior).
--
-- Fecha: 2026-08-25
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{muelles}',
    '["read"]'::jsonb,
    true
)
WHERE nombre = 'guarda_vehicular';

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-08-25_permiso_muelles_read_guarda_vehicular.sql',
  'Agrega permisos->''muelles'' = ["read"] al rol guarda_vehicular. La clave no existía antes (verificado contra historial de migraciones aplicadas, 2026-08-25). Solo lectura -- NO agrega "liberar". Necesario para que GET /api/muelles no devuelva 403 al guarda_vehicular en el flujo nuevo de confirmación de ingreso (pendiente de construir en backend/frontend). La escritura de ese flujo sigue usando el permiso proveedores:write que guarda_vehicular ya tenía.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'muelles' AS muelles, permisos
-- FROM roles
-- WHERE nombre = 'guarda_vehicular';
