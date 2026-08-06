-- ================================================================
-- Permiso proveedores:editar_cita -- edición manual de la hora de una
-- cita puntual en citas_programadas (PUT /proveedores/citas/{id}).
--
-- Contexto de negocio: cuando se autoriza un cambio de hora de cita
-- que no llega reflejado en el archivo del WMS (ajuste acordado por
-- teléfono/correo con el proveedor), el guarda necesita poder editar
-- a mano hora_cita_inicio/hora_cita_fin de esa fila puntual. Permiso
-- confirmado por Karen (usuaria final), 2026-08-06: cualquier guarda
-- con el permiso que ya tiene sobre Proveedores puede editar -- no se
-- restringe a supervisión. Se usa una acción separada
-- "editar_cita" (en vez de reutilizar "write") para que quede
-- explícito en el código qué acción es -- mismo patrón que ya existe
-- "control_acceso":"anular" (ver migration_anulacion_control_acceso.sql,
-- sección 6) -- aunque hoy se otorgue a los mismos roles que ya tienen
-- "write" en "proveedores".
--
-- Alcance (verificado leyendo la tabla roles real el 2026-08-06 antes
-- de escribir esta migración, SELECT nombre, permisos FROM roles WHERE
-- permisos -> 'proveedores' ? 'write'): la instrucción original asumía
-- solo guarda_bodega y guarda_vehicular, pero en producción real hoy
-- SEIS roles tienen "write" en "proveedores": admin, coordinador,
-- guarda_bodega, guarda_vehicular, operador y supervisor. Se sigue el
-- criterio explícito recibido ("los mismos roles que hoy tienen
-- proveedores:write"), no el ejemplo entre paréntesis que resultó
-- incompleto -- por eso el UPDATE de abajo usa la condición
-- `permisos -> 'proveedores' ? 'write'` (igual que la sección 6 de
-- migration_anulacion_control_acceso.sql) en vez de listar nombres de
-- rol a mano: así queda correcto también si la lista de roles cambia
-- más adelante, sin tener que tocar esta migración.
--
-- Merge seguro de arrays (jsonb_set + jsonb_array_elements_text, NUNCA
-- `permisos || '{"proveedores":[...]}'::jsonb`): "proveedores" YA
-- existe con arrays no vacíos en los 6 roles de arriba: un `||` directo
-- REEMPLAZARÍA por completo ese array y borraría "read"/"write"/
-- "delete"/"export" ya presentes, dejando solo ["editar_cita"].
--
-- Idempotente: jsonb_agg(DISTINCT elem) evita duplicar "editar_cita"
-- si esta migración se corre más de una vez.
-- Fecha: 2026-08-06
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{proveedores}',
    (
        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
        FROM jsonb_array_elements_text(
            (permisos -> 'proveedores') || '["editar_cita"]'::jsonb
        ) AS elem
    )
)
WHERE permisos -> 'proveedores' ? 'write';

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-06_permiso_editar_cita.sql')
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'proveedores' AS permisos_proveedores
-- FROM roles
-- WHERE permisos -> 'proveedores' ? 'write'
-- ORDER BY nombre;
