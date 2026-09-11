-- ================================================================
-- Revoca el permiso "liberar" en el módulo "muelles" para el rol
-- `guarda_bodega` de control-vehicular-v2 -- SIN perder el "read"
-- que también tiene.
--
-- Contexto de negocio / hallazgo de seguridad: auditoría externa
-- (matriz ISO 31000, hallazgo ALTO). guarda_bodega conserva hoy el
-- permiso técnico "muelles":"liberar" (endpoints PUT
-- /proveedores/{id}/liberar-muelle* -- backend/routers/proveedores.py,
-- líneas 1449-1453 / 1506 / 1574-1578, gateados con
-- require_permiso("muelles", "liberar")) aunque operativamente esa
-- función ya se trasladó a portería/recorredor externo (ver
-- 2026-09-04_permiso_muelles_liberar_guarda_vehicular.sql y
-- 2026-09-04_permiso_muelles_recorredor_externo.sql, que amplían el
-- alcance a esos dos roles precisamente para cubrir esa función). El
-- permiso de guarda_bodega nunca se revocó -- exceso de privilegio
-- respecto a la función real del rol. Alejandro validó el enfoque:
-- revocar solo "liberar", el "read" del tablero de Muelles se
-- mantiene intacto (guarda_bodega sigue necesitando ver el tablero).
--
-- Alcance de la corrección: esta migración es puramente de datos
-- (jsonb en `roles`). No hace falta tocar código -- tanto el backend
-- (require_permiso en backend/routers/auth.py, líneas 121-132, que
-- lee current_user["permisos"][modulo] sin ningún check hardcodeado
-- por nombre de rol) como el frontend (puede(user,'muelles','liberar')
-- en frontend/index.html, líneas 4254/4259/4265/6558/6658, mismo
-- patrón: gatea el botón "Liberar muelle" por el permiso jsonb, no por
-- rol literal) evalúan exclusivamente permisos->'muelles' del usuario
-- autenticado. Al quitar "liberar" del jsonb de guarda_bodega, el
-- botón deja de renderizarse para ese rol y el endpoint responde 403
-- si de todos modos se invoca directo -- sin ningún deploy adicional.
--
-- Estado ANTES (verificado contra el historial completo de
-- migraciones aplicadas en orden, no asumido): guarda_bodega recibió
-- permisos->'muelles' = ["read","liberar"] en su alta formal
-- (2026-08-01_roles_guarda_alta_formal.sql, línea 69 -- valor leído
-- directo de producción el 2026-08-01, no inventado). Se revisó todo
-- migrations_manual/ posterior a esa fecha en orden cronológico y
-- ninguna migración vuelve a tocar la clave "muelles" de
-- guarda_bodega (2026-08-25 y 2026-09-04 solo tocan guarda_vehicular
-- y recorredor_externo respectivamente, y ambas documentan
-- explícitamente "no toca guarda_bodega"). Tampoco hay ningún UPDATE
-- sobre guarda_bodega en database/*.sql que toque la clave "muelles"
-- (los que existen tocan "proveedores", "maestros", "novedades" y
-- "visita_vehicular" -- ver migration_guarda_bodega_proveedores.sql,
-- migration_maestros_read_guardas.sql, migration_rondas_novedades.sql,
-- migration_visita_vehicular.sql). Por lo tanto, el estado ANTES de
-- este archivo es:
--
--   guarda_bodega -> {"flota": ["read","write"],
--                      "muelles": ["read","liberar"],
--                      "maestros": ["read"],
--                      "dashboard": ["read"],
--                      "novedades": ["read","write"],
--                      "proveedores": ["read","write"],
--                      "visita_vehicular": ["read","write"]}
--
-- Estado DESPUÉS esperado: idéntico, salvo permisos->'muelles' =
-- ["read"] (se quita únicamente "liberar"; ninguna otra clave del
-- jsonb se toca).
--
-- Patrón usado: filtrado seguro de array jsonb EXISTENTE con
-- jsonb_array_elements + jsonb_agg(...) FILTER (WHERE ...) dentro de
-- jsonb_set -- el mismo espíritu defensivo que el MERGE aditivo de
-- 2026-09-04_permiso_muelles_liberar_guarda_vehicular.sql, pero en
-- sentido inverso (resta un elemento en vez de sumarlo). Se usa
-- jsonb_array_elements (no _text) para poder comparar cada elemento
-- contra el literal jsonb '"liberar"'::jsonb sin depender de casteos
-- de texto. NUNCA se reemplaza el array completo a mano
-- (jsonb_set(permisos, '{muelles}', '["read"]'::jsonb, true)) porque
-- aunque hoy el resultado sería el mismo, ese patrón asume el
-- contenido exacto del array en vez de derivarlo -- si guarda_bodega
-- tuviera algún día un tercer valor en "muelles" que no sea "read" ni
-- "liberar", un reemplazo a mano lo borraría en silencio; el filtro
-- FILTER (WHERE elem <> '"liberar"') lo conserva porque solo remueve
-- el elemento explícitamente objetado por el hallazgo. Tampoco se
-- toca ninguna otra clave del jsonb (flota, maestros, dashboard,
-- novedades, proveedores, visita_vehicular) ni ninguna otra fila de
-- `roles`.
--
-- Idempotente: la primera ejecución filtra "liberar" y deja
-- ["read"]; una segunda ejecución sobre ["read"] no encuentra nada
-- que filtrar y produce el mismo ["read"] -- correr este archivo más
-- de una vez no falla ni cambia el resultado. Se usa
-- COALESCE(permisos -> 'muelles', '[]'::jsonb) de forma defensiva por
-- si la clave llegara a faltar en algún ambiente (no debería, según
-- el estado ANTES verificado), y COALESCE(jsonb_agg(...), '[]'::jsonb)
-- por si el filtro dejara el array vacío (tampoco debería ocurrir
-- aquí, "read" siempre sobrevive al filtro) -- ambos evitan que la
-- migración deje NULL en vez de un array jsonb válido.
--
-- ADVERTENCIA -- tabla `roles` compartida con citas-muelles-cedi-r10
-- (misma base Supabase, confirmado en
-- 2026-08-07_verifica_rol_coordinador_solo_lectura.sql y
-- 2026-08-25_permiso_muelles_read_guarda_vehicular.sql): esta
-- migración solo toca la fila roles.nombre='guarda_bodega' y remueve
-- un único valor de un array jsonb existente sin tocar ninguna otra
-- clave de esa fila ni ninguna otra fila de `roles`. Si esa otra app
-- evalúa permisos->'muelles' de guarda_bodega con la misma semántica
-- (¿tiene "liberar"?), el efecto es el buscado por el hallazgo:
-- guarda_bodega deja de poder liberar muelles ahí también. Si la
-- otra app tuviera alguna lógica que dependiera de que guarda_bodega
-- SÍ tenga "liberar" hoy, sería en sí misma una superficie de riesgo
-- equivalente al hallazgo que se está cerrando aquí -- no se encontró
-- evidencia de eso en este repositorio, pero se deja la nota porque
-- no se tiene visibilidad del código de esa otra app.
--
-- Riesgo: BAJO técnicamente (UPDATE de una sola fila, remueve 1 valor
-- de un array jsonb existente; no hay ALTER de esquema ni backfill
-- sobre otras tablas), aunque es un cambio de seguridad con efecto
-- funcional real: cualquier usuario con rol guarda_bodega pierde la
-- capacidad de liberar muelles desde este momento (backend y
-- frontend, sin necesidad de otro deploy). Confirmar con Alejandro/
-- negocio que no queda ningún flujo operativo activo hoy que dependa
-- de que un guarda_bodega libere muelles directamente antes de correr
-- esto en producción -- el propio hallazgo indica que esa función ya
-- se trasladó a portería/recorredor externo, pero es una validación
-- de negocio, no algo que esta migración pueda confirmar por sí sola.
--
-- Fecha: 2026-09-07
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{muelles}',
    (
        SELECT COALESCE(
            jsonb_agg(elem) FILTER (WHERE elem <> '"liberar"'::jsonb),
            '[]'::jsonb
        )
        FROM jsonb_array_elements(
            COALESCE(permisos -> 'muelles', '[]'::jsonb)
        ) AS elem
    ),
    true
)
WHERE nombre = 'guarda_bodega';

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-09-07_revoca_muelles_liberar_guarda_bodega.sql',
  'Cierra hallazgo de seguridad ALTO (auditoría externa, ISO 31000): remueve "liberar" de permisos->''muelles'' del rol guarda_bodega mediante filtrado de array jsonb (jsonb_agg(...) FILTER), preservando el "read" que ya tenía desde su alta formal (2026-08-01_roles_guarda_alta_formal.sql). Resultado esperado: ["read"] (orden preservado). No toca guarda_vehicular ni recorredor_externo (que sí conservan "liberar" desde 2026-09-04, alcance de negocio ya validado) ni ninguna otra clave/fila de roles.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'muelles' AS muelles, permisos
-- FROM roles
-- WHERE nombre = 'guarda_bodega';
-- -- Esperado: muelles debe contener EXACTAMENTE ["read"] (1 elemento,
-- -- sin "liberar"), y el resto de claves del jsonb (flota, maestros,
-- -- dashboard, novedades, proveedores, visita_vehicular) debe seguir
-- -- intacto tal como en el estado ANTES documentado arriba.
--
-- SELECT nombre, permisos -> 'muelles' AS muelles
-- FROM roles
-- WHERE nombre IN ('guarda_vehicular','recorredor_externo');
-- -- Esperado (control, no debe cambiar por esta migración): ambos
-- -- deben seguir con "liberar" -- ["liberar","read"] (orden no
-- -- garantizado) y ["read","liberar"] respectivamente.
