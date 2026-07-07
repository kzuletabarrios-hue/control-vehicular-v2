-- Separa "Empresa / Visita a" en dos conceptos distintos en visitantes:
-- empresa_pertenece = empresa a la que pertenece el visitante (su empleador)
-- empresa (ya existia) = a quien visita / dependencia interna

ALTER TABLE visitantes
  ADD COLUMN IF NOT EXISTS empresa_pertenece TEXT;
