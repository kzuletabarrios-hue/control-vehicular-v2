-- Ubicacion GPS capturada al marcar cada punto de ronda, para poder
-- calcular la distancia recorrida (linea recta entre puntos consecutivos).
-- Opcional: si el navegador no da permiso o falla la lectura, queda NULL
-- y ese punto simplemente no participa en el calculo de distancia.

ALTER TABLE rondas
  ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;
