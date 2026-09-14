-- Agrega a visita_vehicular los mismos campos que ya tiene visitantes:
-- empresa a la que pertenece el conductor, y quien autoriza la visita.
-- motivo_visita ya existia y cubre el concepto de "actividad a desarrollar".

ALTER TABLE visita_vehicular
  ADD COLUMN IF NOT EXISTS empresa_pertenece    TEXT,
  ADD COLUMN IF NOT EXISTS dependencia_autoriza TEXT;
