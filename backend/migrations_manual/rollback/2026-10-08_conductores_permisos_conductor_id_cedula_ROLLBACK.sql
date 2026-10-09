-- ROLLBACK de 2026-10-08_conductores_permisos_conductor_id_cedula.sql
-- ADVERTENCIA: DROP COLUMN conductor_id borra los vínculos (incluido
-- el backfill si se corrió). `conductor` (texto) queda intacto, así
-- que no se pierde información de negocio. Antes: confirmar que el
-- backend ya no usa conductor_id ni el recurso "conductores".

DROP INDEX IF EXISTS uq_conductores_cedula_norm;
DROP INDEX IF EXISTS idx_flota_propia_conductor_id;
ALTER TABLE flota_propia DROP CONSTRAINT IF EXISTS flota_propia_conductor_id_fkey;
ALTER TABLE flota_propia DROP COLUMN IF EXISTS conductor_id;

UPDATE roles SET permisos = permisos - 'conductores'
WHERE permisos ? 'conductores';

DELETE FROM schema_migrations
WHERE filename = '2026-10-08_conductores_permisos_conductor_id_cedula.sql';
