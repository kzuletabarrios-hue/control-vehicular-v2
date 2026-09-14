-- ================================================================
-- Permiso citas:export -- nueva acción para el reporte exportable
-- (Excel) de "citas sin llegar" del módulo Citas.
--
-- Contexto de negocio: Karen confirmó que tanto `admin` como
-- `coordinador` deben poder usar el reporte exportable. Hoy la acción
-- "export" NO existe en el arreglo permisos->'citas' de ningún rol
-- (verificado en vivo el 2026-08-07, ver estado ANTES abajo) -- es una
-- capacidad nueva, no una extensión de un permiso ya otorgado a varios
-- roles (a diferencia de 2026-08-06_permiso_editar_cita.sql, que usó
-- la condición `permisos -> 'proveedores' ? 'write'` para alcanzar a
-- los 6 roles que ya tenían ese permiso). Por eso aquí el alcance es
-- explícito por nombre, no heurístico:
--
--   WHERE nombre IN ('admin', 'coordinador')
--
-- Estado ANTES (verificado en vivo contra Supabase producción,
-- 2026-08-07, SELECT nombre, permisos->'citas' FROM roles WHERE
-- nombre IN ('admin','coordinador')):
--
--   admin       -> ["read","write"]
--   coordinador -> ["read","write"]
--
-- Ninguno de los dos tenía "export" antes de esta migración.
--
-- Merge seguro de arrays (jsonb_set + jsonb_array_elements_text, NUNCA
-- `permisos || '{"citas":[...]}'::jsonb`): "citas" YA existe con
-- arrays no vacíos en ambos roles ("read","write"); un `||` directo
-- sobre la clave "citas" REEMPLAZARÍA por completo ese array y
-- borraría "read"/"write" ya presentes, dejando solo ["export"]. Se
-- usa el mismo patrón exacto que 2026-08-06_permiso_editar_cita.sql:
-- jsonb_set(permisos, '{citas}', (SELECT jsonb_agg(DISTINCT elem)
-- FROM jsonb_array_elements_text(permisos->'citas' || '["export"]')))
-- para AGREGAR el valor nuevo preservando los existentes.
--
-- Idempotente: jsonb_agg(DISTINCT elem) evita duplicar "export" si
-- esta migración se corre más de una vez.
--
-- ADVERTENCIA -- tabla `roles` compartida con citas-muelles-cedi-r10:
-- esta fila (roles.nombre='coordinador', id=9, ver
-- 2026-08-07_verifica_rol_coordinador_solo_lectura.sql) se lee contra
-- la MISMA base Supabase desde la app hermana citas-muelles-cedi-r10.
-- Agregar "export" al arreglo permisos->'citas' de 'coordinador' aquí
-- también quedaría visible para esa otra app si en algún momento
-- implementa una acción "citas:export" propia -- hoy esa app no la usa
-- (no hay migraciones versionadas ahí ni código que la consuma, y no
-- corresponde a este repo tocarla), y el cambio es puramente ADITIVO
-- (no se quita ni se reemplaza ningún valor existente), por lo que no
-- debería romper nada de lo que citas-muelles-cedi-r10 ya hace hoy.
--
-- IMPORTANTE -- esta migración por sí sola NO habilita a coordinador a
-- exportar dentro de control-vehicular-v2: el clamp de solo-lectura
-- `ROLES_SOLO_LECTURA_EN_ESTA_APP = {"coordinador"}` (backend/routers/
-- auth.py) sigue bloqueando en esta app toda acción de ese rol salvo
-- excepciones puntuales explícitas en el backend -- la excepción para
-- "citas:export" (para que el clamp la deje pasar) la agrega María por
-- separado en el código de esta app. Este script únicamente deja la
-- acción "export" disponible en la fila compartida `roles.permisos`
-- para que ese código la pueda leer con `tiene_permiso(usuario_id,
-- 'citas', 'export')`; no otorga por sí solo la capacidad real dentro
-- de control-vehicular-v2.
--
-- Fecha: 2026-08-07
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{citas}',
    (
        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
        FROM jsonb_array_elements_text(
            (permisos -> 'citas') || '["export"]'::jsonb
        ) AS elem
    )
)
WHERE nombre IN ('admin', 'coordinador');

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-07_permiso_citas_export.sql')
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'citas' AS permisos_citas
-- FROM roles
-- WHERE nombre IN ('admin', 'coordinador')
-- ORDER BY nombre;
