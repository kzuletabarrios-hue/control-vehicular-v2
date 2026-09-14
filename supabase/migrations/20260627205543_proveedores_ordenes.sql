-- migration_proveedores_ordenes.sql
-- Un vehículo puede tener múltiples órdenes/empresas.
-- proveedores = registro del vehículo (placa, conductor, horarios)
-- proveedores_ordenes = una fila por empresa/orden asociada al vehículo
--
-- CORRECCIÓN (Jorge, 2026-09-14): línea 28 original tenía
-- `COALESCE(carga_compartida, FALSE)` -- `proveedores.carga_compartida`
-- es TEXT desde el schema base (database/schema.sql /
-- 20260601101420_schema_base.sql, sin cambios desde 2026-06-01,
-- confirmado con SELECT data_type contra producción el 2026-09-14:
-- sigue siendo `text` hoy), mientras que
-- `proveedores_ordenes.carga_compartida` (definida abajo, en este
-- mismo archivo) es BOOLEAN. `COALESCE(text, boolean)` no es un tipo
-- válido en Postgres -- falla con "COALESCE types text and boolean
-- cannot be matched", confirmado reproduciendo el error con una
-- consulta de solo lectura contra producción (la tabla real, con
-- datos reales, da el mismo error). Valores reales de
-- proveedores.carga_compartida hoy (verificado 2026-09-14):
-- NULL=3602, 'false'=8, 'true'=2 -- son literales booleanos válidos
-- como texto, así que el cast explícito es seguro y no pierde ni
-- distorsiona ningún dato real. Se corrige con `::boolean` explícito
-- en el SELECT (línea de abajo) -- el CREATE TABLE de
-- proveedores_ordenes.carga_compartida (BOOLEAN) y el schema base de
-- proveedores.carga_compartida (TEXT) son ambos correctos y reflejan
-- el esquema real; el error estaba únicamente en este COALESCE.
-- Hallazgo de María corriendo las 46 migraciones contra una base
-- vacía real (nunca se manifestó en producción porque ahí las tablas
-- ya existían de antes -- este INSERT de backfill nunca se re-ejecutó
-- contra un `proveedores_ordenes` recién creado desde 2026-06-27).

CREATE TABLE IF NOT EXISTS proveedores_ordenes (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proveedor_id          UUID NOT NULL REFERENCES proveedores(id) ON DELETE CASCADE,
  empresa               TEXT,
  muelle_descargue      TEXT,
  carga_compartida      BOOLEAN DEFAULT FALSE,
  actividad_a_desarrollar TEXT,
  dependencia_autoriza  TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proveedores_ordenes_proveedor ON proveedores_ordenes(proveedor_id);

-- Migrar datos existentes: cada fila de proveedores genera una orden
INSERT INTO proveedores_ordenes (
  proveedor_id, empresa, muelle_descargue, carga_compartida,
  actividad_a_desarrollar, dependencia_autoriza
)
SELECT
  id,
  empresa,
  muelle_descargue,
  COALESCE(carga_compartida::boolean, FALSE),
  actividad_a_desarrollar,
  dependencia_autoriza
FROM proveedores
WHERE empresa IS NOT NULL
   OR muelle_descargue IS NOT NULL
   OR actividad_a_desarrollar IS NOT NULL
   OR dependencia_autoriza IS NOT NULL;
