-- ================================================================
-- Permiso de solo lectura para `coordinador` en los módulos
-- "Visitantes" y "Control Acceso" de control-vehicular-v2.
--
-- Contexto de negocio: Karen pidió que el rol `coordinador` pueda VER
-- (solo lectura) los módulos Visitantes y Control Acceso. El clamp
-- genérico `ROLES_SOLO_LECTURA_EN_ESTA_APP = {"coordinador"}`
-- (backend/routers/auth.py, función _clamp_permisos_solo_lectura) ya
-- reduce en runtime CUALQUIER acción de ese rol a solo "read" -- pero
-- solo opera sobre las claves de módulo que YA existen en
-- `roles.permisos`. Si la clave del módulo no existe en el jsonb, el
-- clamp no tiene nada que reducir y el endpoint sigue negando el
-- acceso (require_permiso("visitantes", "read") /
-- require_permiso("control_acceso", "read"), ver
-- backend/routers/visitantes.py y backend/routers/control_acceso.py).
-- Por eso hace falta esta migración: agrega las dos claves que faltan.
--
-- Nombres de módulo verificados contra el código real (no asumidos):
--   - backend/routers/visitantes.py      -> require_permiso("visitantes", ...)
--   - backend/routers/control_acceso.py  -> require_permiso("control_acceso", ...)
-- (Nota: novedades.py usa el string "acceso" en su propio
-- MODULOS_VALIDOS, pero es un catálogo interno de ese módulo -- no
-- tiene relación con el nombre de módulo de autorización RBAC que usa
-- require_permiso() para Control Acceso, que es "control_acceso".)
--
-- Estado ANTES (verificado en vivo contra Supabase producción,
-- 2026-08-11, conexión directa vía DATABASE_URL, no asumido):
--
--   SELECT nombre, permisos->'visitantes' AS visitantes,
--          permisos->'control_acceso' AS control_acceso, permisos
--   FROM roles WHERE nombre = 'coordinador';
--
--   nombre = 'coordinador'
--   visitantes      = NULL   -- la clave no existe en el jsonb
--   control_acceso  = NULL   -- la clave no existe en el jsonb
--   permisos completo = {
--     "citas":       ["export","read","write"],
--     "flota":       ["read"],
--     "muelles":     ["read","asignar"],
--     "maestros":    ["read"],
--     "dashboard":   ["read"],
--     "proveedores": ["editar_cita","read","write"]
--   }
--
-- Ninguna de las dos claves existía antes de esta migración -- a
-- diferencia de 2026-08-07_permiso_citas_export.sql (donde "citas" ya
-- tenía ["read","write"] y había que preservarlos con merge), aquí no
-- hay ningún array previo que perder. Por eso NO se usa el patrón de
-- merge (jsonb_agg(DISTINCT elem)) de esa migración: no aplica cuando
-- no hay nada que preservar, y forzarlo sería complejidad innecesaria.
--
-- Valor escrito: literal ["read"] para ambas claves (no ["read","write"]
-- reducido después por el clamp de auth.py). Decisión de Alejandro: a
-- diferencia de citas:export (que sí requería preservar la capacidad
-- real de escritura para la app hermana citas-muelles-cedi-r10),
-- "visitantes" y "control_acceso" NO son módulos del dominio de esa
-- app -- no hay escritura legítima que clampear después ni capacidad
-- previa que conservar. Escribir ["read"] directo es más simple y
-- autoexplicativo para quien lea la fila en Supabase, sin depender de
-- que el clamp de runtime lo reduzca.
--
-- Patrón usado: jsonb_set(permisos, '{modulo}', '["read"]'::jsonb) --
-- NO se usa `permisos || '{"visitantes":["read"]}'::jsonb` como
-- atajo porque, aunque aquí no hay pérdida de datos (la clave no
-- existe), jsonb_set es explícito sobre qué clave se toca y es
-- consistente con el patrón de las migraciones anteriores de este
-- archivo. Se envuelve el valor previo en
-- COALESCE(permisos->'visitantes', '[]'::jsonb) únicamente como nota
-- de precaución general documentada por Alejandro (NULL || jsonb da
-- NULL) -- no se necesita en la práctica porque jsonb_set con literal
-- ["read"] REEMPLAZA la clave sin depender de su valor anterior, pero
-- se deja constancia de por qué este script es inmune a esa trampa:
-- no concatena, sobreescribe con un literal.
--
-- ADVERTENCIA -- tabla `roles` compartida con citas-muelles-cedi-r10:
-- esta fila (roles.nombre='coordinador', id=9, ver
-- 2026-08-07_verifica_rol_coordinador_solo_lectura.sql) se lee contra
-- la MISMA base Supabase desde la app hermana citas-muelles-cedi-r10.
-- Verificado el 2026-08-11 (búsqueda de "visitantes"/"control_acceso"
-- en C:\citas-muelles-cedi-r10\backend): sin resultados -- esa app no
-- tiene ningún router, tabla de negocio ni referencia a esos dos
-- módulos. Agregar estas dos claves nuevas al jsonb es puramente
-- ADITIVO (no se quita ni se reemplaza ningún valor existente de
-- otras claves) y no puede afectar ninguna autorización que
-- citas-muelles-cedi-r10 ya evalúe hoy.
--
-- Riesgo: BAJO. UPDATE de una sola fila (roles.nombre='coordinador'),
-- agrega 2 claves jsonb nuevas sin tocar las 6 claves existentes ni
-- ninguna otra fila de `roles`. No hay ALTER de esquema, no hay
-- backfill sobre otras tablas. Idempotente: jsonb_set con literal
-- ["read"] produce el mismo resultado si se re-ejecuta.
--
-- Queda pendiente de aplicar hasta que Karen confirme -- según las
-- reglas del equipo, cualquier cambio sobre la fila compartida
-- `roles.permisos` se reporta explícitamente antes de ejecutarse.
--
-- Fecha: 2026-08-11
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    jsonb_set(
        permisos,
        '{visitantes}',
        '["read"]'::jsonb,
        true
    ),
    '{control_acceso}',
    '["read"]'::jsonb,
    true
)
WHERE nombre = 'coordinador';

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-08-11_permiso_visitantes_acceso_coordinador.sql',
  'Agrega permisos->''visitantes'' = ["read"] y permisos->''control_acceso'' = ["read"] al rol coordinador (id=9). Ambas claves no existían antes (verificado en vivo 2026-08-11). Valor literal ["read"], no depende del clamp ROLES_SOLO_LECTURA_EN_ESTA_APP de auth.py. Aditivo, no afecta a citas-muelles-cedi-r10 (esos dos módulos no existen en su dominio, verificado).'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'visitantes' AS visitantes,
--        permisos -> 'control_acceso' AS control_acceso, permisos
-- FROM roles
-- WHERE nombre = 'coordinador';
