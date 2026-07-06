-- Campos nuevos en proveedores para igualar el Google Form
-- "Registro de Llegada de Proveedores" (autorregistro QR + formulario del guarda)

ALTER TABLE proveedores
  ADD COLUMN IF NOT EXISTS tipo_documento    TEXT,
  ADD COLUMN IF NOT EXISTS arl_proveedor     TEXT,
  ADD COLUMN IF NOT EXISTS epp_cumple        BOOLEAN,
  ADD COLUMN IF NOT EXISTS tipo_carga        TEXT,
  ADD COLUMN IF NOT EXISTS formato_carga     TEXT,
  ADD COLUMN IF NOT EXISTS cantidad_pallets  TEXT,
  ADD COLUMN IF NOT EXISTS manejo_carga      TEXT;

ALTER TABLE proveedores
  ADD CONSTRAINT proveedores_tipo_documento_check
    CHECK (tipo_documento IS NULL OR tipo_documento IN ('CC','NIT','Otro')),
  ADD CONSTRAINT proveedores_tipo_carga_check
    CHECK (tipo_carga IS NULL OR tipo_carga IN ('Seca','Refrigerada','Mixta')),
  ADD CONSTRAINT proveedores_formato_carga_check
    CHECK (formato_carga IS NULL OR formato_carga IN ('Paletizada','Granel','Mixta')),
  ADD CONSTRAINT proveedores_manejo_carga_check
    CHECK (manejo_carga IS NULL OR manejo_carga IN (
      'Conductor con certificado de montacargas','Reciservicios','Ercol','Operador logístico externo'
    ));
