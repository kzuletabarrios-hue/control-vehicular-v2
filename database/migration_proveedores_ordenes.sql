-- migration_proveedores_ordenes.sql
-- Un vehículo puede tener múltiples órdenes/empresas.
-- proveedores = registro del vehículo (placa, conductor, horarios)
-- proveedores_ordenes = una fila por empresa/orden asociada al vehículo

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
  COALESCE(carga_compartida, FALSE),
  actividad_a_desarrollar,
  dependencia_autoriza
FROM proveedores
WHERE empresa IS NOT NULL
   OR muelle_descargue IS NOT NULL
   OR actividad_a_desarrollar IS NOT NULL
   OR dependencia_autoriza IS NOT NULL;
