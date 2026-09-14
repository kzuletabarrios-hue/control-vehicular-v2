-- ================================================================
-- Alta formal (drift retroactivo) de los roles guarda_bodega,
-- guarda_peatonal y guarda_vehicular.
--
-- Estos 3 roles ya existen en producción y están en uso activo
-- (4 / 5 / 10 usuarios asignados respectivamente al momento del
-- diagnóstico, 2026-08-01), y varias migraciones existentes ya
-- los tocan con UPDATE roles ... WHERE nombre IN (...) --
-- migration_guarda_bodega_proveedores.sql,
-- migration_maestros_read_guardas.sql, migration_rondas_novedades.sql,
-- migration_anulacion_control_acceso.sql -- pero el INSERT INTO roles
-- original que los dio de alta nunca quedó versionado en git (se
-- creía que se habían creado directo en la BD; ver nota final del
-- propio migration_anulacion_control_acceso.sql). Sin este archivo,
-- restaurar el esquema desde cero con lo que hay en git deja esos 3
-- roles inexistentes y todos los UPDATE posteriores serían no-ops
-- silenciosos (0 filas afectadas, sin error).
--
-- descripcion y permisos son el estado REAL leído de producción el
-- 2026-08-01 vía SELECT nombre, descripcion, permisos FROM roles
-- (no se inventó ni se completó nada por analogía con otros roles):
--
--   guarda_bodega    -> {"flota":["read","write"],"muelles":["read","liberar"],
--                        "maestros":["read"],"dashboard":["read"],
--                        "novedades":["read","write"],"proveedores":["read","write"],
--                        "visita_vehicular":["read","write"]}
--
--   guarda_peatonal  -> {"dashboard":["read"],"novedades":["read","write"],
--                        "visitantes":["read","write"],
--                        "control_acceso":["anular","read","write"]}
--
--   guarda_vehicular -> {"flota":["read","write"],"maestros":["read"],
--                        "dashboard":["read"],"novedades":["read","write"],
--                        "visitantes":["read","write"],"proveedores":["read","write"],
--                        "visita_vehicular":["read","write"]}
--
-- ADVERTENCIA de alcance encontrada en el diagnóstico (relevante para
-- quien lea migration_anulacion_control_acceso.sql): ese script
-- asumía que "guarda_vehicular está confirmado" con permiso "write"
-- en control_acceso, pero en producción real guarda_vehicular NO
-- tiene la clave "control_acceso" en absoluto -- por eso nunca recibió
-- "anular", lo cual es coherente con la condición defensiva de ese
-- mismo script (WHERE permisos -> 'control_acceso' ? 'write'), solo
-- que el supuesto de partida en el comentario era incorrecto. Se deja
-- esta nota para que no se repita el supuesto en el futuro; no se
-- corrige aquí el permiso de guarda_vehicular porque no fue pedido y
-- cambiaría su superficie de acceso -- si guarda_vehicular debe poder
-- operar control_acceso, es una decisión de negocio de Alejandro/Karen,
-- no algo que esta migración de alta deba decidir.
--
-- ON CONFLICT (nombre) DO NOTHING: si el rol ya existe (caso de
-- producción), este script es un no-op seguro y NO pisa los permisos
-- actuales (evita revertir cambios posteriores hechos directo en BD
-- o por otras migraciones). Su valor real es para cualquier ambiente
-- que hoy no tenga estos 3 roles si solo corriera lo que está en git.
--
-- Idempotente. Requiere roles.nombre UNIQUE (confirmado: constraint
-- roles_nombre_key ya existe en producción).
-- Ejecutar DESPUÉS de auth_schema.sql (roles base: admin, supervisor,
-- operador, coordinador, consulta, recorredor_externo) y ANTES de
-- cualquier migración que haga UPDATE roles ... WHERE nombre IN
-- ('guarda_bodega','guarda_peatonal','guarda_vehicular', ...).
-- Fecha: 2026-08-01
-- ================================================================

INSERT INTO roles (nombre, descripcion, permisos) VALUES
  ('guarda_bodega', 'Guarda - Control Bodega (Flota Propia)',
   '{"flota": ["read","write"],
     "muelles": ["read","liberar"],
     "maestros": ["read"],
     "dashboard": ["read"],
     "novedades": ["read","write"],
     "proveedores": ["read","write"],
     "visita_vehicular": ["read","write"]}'::jsonb),

  ('guarda_peatonal', 'Guarda - Control Acceso Peatonal',
   '{"dashboard": ["read"],
     "novedades": ["read","write"],
     "visitantes": ["read","write"],
     "control_acceso": ["anular","read","write"]}'::jsonb),

  ('guarda_vehicular', 'Guarda - Control Acceso Vehicular',
   '{"flota": ["read","write"],
     "maestros": ["read"],
     "dashboard": ["read"],
     "novedades": ["read","write"],
     "visitantes": ["read","write"],
     "proveedores": ["read","write"],
     "visita_vehicular": ["read","write"]}'::jsonb)

ON CONFLICT (nombre) DO NOTHING;

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-01_roles_guarda_alta_formal.sql')
ON CONFLICT (filename) DO NOTHING;
