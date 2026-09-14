-- Agrega fecha_salida y fecha_llegada a flota_propia
-- y fecha_salida a proveedores, para registrar correctamente
-- cuando el evento ocurre un día distinto al de creación del registro.

ALTER TABLE flota_propia
  ADD COLUMN IF NOT EXISTS fecha_salida DATE,
  ADD COLUMN IF NOT EXISTS fecha_llegada DATE;

ALTER TABLE proveedores
  ADD COLUMN IF NOT EXISTS fecha_salida DATE;
