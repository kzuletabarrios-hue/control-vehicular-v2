-- Nuevos campos en visitantes: actividad a desarrollar y quien autoriza la visita
-- (a pedido del usuario, mismo concepto que ya existia en proveedores_ordenes)

ALTER TABLE visitantes
  ADD COLUMN IF NOT EXISTS actividad_a_desarrollar TEXT,
  ADD COLUMN IF NOT EXISTS dependencia_autoriza    TEXT;
