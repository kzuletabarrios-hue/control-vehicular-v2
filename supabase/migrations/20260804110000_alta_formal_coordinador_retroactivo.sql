-- ================================================================
-- Alta formal (drift retroactivo) del rol `coordinador` -- mismo
-- patrón que 20260601101440_roles_guarda_alta_formal_retroactivo.sql
-- para guarda_bodega/guarda_peatonal/guarda_vehicular, pero nunca
-- aplicado a este rol hasta ahora.
--
-- Autor: Jorge Peña (Arquitecto de BD). Investigado y propuesto
-- 2026-09-14; revisado y APROBADO por Alejandro el mismo día (ver
-- 20260804100000_schema_tablas_huerfanas_drift.sql para el resto de
-- la propuesta -- este archivo va SEPARADO a propósito, siguiendo el
-- mismo patrón que ya usa el repo de un archivo dedicado por alta de
-- rol).
--
-- ── EL HALLAZGO ──────────────────────────────────────────────────
-- roles.nombre='coordinador' (id=9 en producción) es usado y
-- modificado por al menos 3 migraciones ya incluidas en
-- supabase/migrations/:
--   - 20260807134610_verifica_rol_coordinador_solo_lectura.sql
--   - 20260807225940_permiso_citas_export.sql
--   - 20260812114638_permiso_visitantes_acceso_coordinador.sql
-- las tres ASUMEN que el rol ya existe (hacen UPDATE / COMMENT, nunca
-- INSERT). Se buscó "INSERT INTO roles" en TODO el repositorio
-- (database/, backend/migrations_manual/): el INSERT que da de alta a
-- 'coordinador' no existe en ningún lado -- a diferencia de
-- guarda_bodega/guarda_peatonal/guarda_vehicular, que sí recibieron su
-- "alta formal retroactiva" el 2026-08-01, a 'coordinador' nunca se le
-- hizo ese mismo tratamiento. Mismo patrón de drift, nunca cerrado
-- hasta esta migración.
--
-- descripcion y permisos = estado REAL leído de producción el
-- 2026-09-14 (SELECT id, nombre, descripcion, permisos FROM roles
-- WHERE nombre = 'coordinador') -- no se completa nada por analogía.
-- descripcion es NULL en producción (a diferencia de los demás roles,
-- nunca se le puso una) -- se respeta tal cual, no se inventa una.
-- Incluye permisos de escritura (citas:write, muelles:asignar,
-- proveedores:write/editar_cita) ya confirmados como legítimos y
-- necesarios para la app hermana citas-muelles-cedi-r10 por una
-- auditoría previa de este mismo rol -- ver
-- 20260807134610_verifica_rol_coordinador_solo_lectura.sql.
--
-- ── UBICACIÓN EN LA SECUENCIA ─────────────────────────────────────
-- Timestamp deliberadamente anterior al 2026-08-05 (igual criterio que
-- 20260804100000_schema_tablas_huerfanas_drift.sql y que
-- 20260601101440_roles_guarda_alta_formal_retroactivo.sql), para que
-- el rol ya exista antes de la primera migración versionada que lo
-- referencia (20260807134610, 07-ago). Verificado que ninguna
-- migración con fecha anterior a esta hace UPDATE/INSERT sobre
-- roles.nombre='coordinador' -- las 3 migraciones que lo tocan son
-- todas de agosto, después de este archivo.
--
-- ON CONFLICT (nombre) DO NOTHING: si el rol ya existe (caso de
-- producción), no-op seguro, no pisa permisos ya modificados por
-- migraciones posteriores (mismo patrón que la alta formal de los
-- roles guarda_*).
--
-- Idempotente. Requiere roles.nombre UNIQUE (constraint
-- roles_nombre_key, creado en 20260601101430_auth_schema.sql).
-- ================================================================

INSERT INTO roles (nombre, descripcion, permisos) VALUES
  ('coordinador', NULL,
   '{"citas": ["read","write","export"],
     "flota": ["read"],
     "muelles": ["read","asignar"],
     "maestros": ["read"],
     "dashboard": ["read"],
     "visitantes": ["read"],
     "proveedores": ["read","write","editar_cita"],
     "control_acceso": ["read"]}'::jsonb)
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20260804110000_alta_formal_coordinador_retroactivo.sql',
  'Alta formal retroactiva del rol coordinador (id=9 en producción), nunca versionada en git pese a que 3 migraciones ya incluidas en supabase/migrations/ lo referencian por UPDATE/COMMENT. Permisos = estado real leído de producción el 2026-09-14. Investigado y propuesto por Jorge, aprobado por Alejandro el 2026-09-14. Mismo patrón que 20260601101440_roles_guarda_alta_formal_retroactivo.sql.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT id, nombre, descripcion, permisos FROM roles WHERE nombre = 'coordinador';
-- ================================================================
