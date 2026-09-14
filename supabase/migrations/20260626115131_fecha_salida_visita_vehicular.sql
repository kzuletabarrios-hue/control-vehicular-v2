-- Agrega fecha_salida a visita_vehicular para registrar correctamente
-- cuando el vehículo sale un día distinto al de ingreso.

ALTER TABLE visita_vehicular ADD COLUMN IF NOT EXISTS fecha_salida DATE;
