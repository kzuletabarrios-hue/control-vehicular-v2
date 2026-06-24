-- Modulo "Visita Vehicular": vehiculos que ingresan por una visita puntual
-- (no son flota propia ni proveedores/TGN). Ej: vehiculos de empleados,
-- contratistas ocasionales, entidades de gobierno, etc.

CREATE TABLE IF NOT EXISTS visita_vehicular (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha         DATE NOT NULL DEFAULT CURRENT_DATE,
    placa         TEXT NOT NULL,
    conductor     TEXT NOT NULL,
    motivo_visita TEXT,
    hora_ingreso  TEXT,
    hora_salida   TEXT,
    observaciones TEXT,
    foto_url      TEXT,
    creado_por    UUID REFERENCES usuarios(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_visita_vehicular_fecha ON visita_vehicular(fecha);
CREATE INDEX IF NOT EXISTS idx_visita_vehicular_placa ON visita_vehicular(placa);

-- Permisos: igual alcance que Flota Propia (admin, supervisor, operador,
-- guarda_bodega, guarda_vehicular), guardas sin delete.
UPDATE roles SET permisos = permisos || '{"visita_vehicular":["read","write","delete","export"]}'::jsonb
WHERE nombre = 'admin';

UPDATE roles SET permisos = permisos || '{"visita_vehicular":["read","write","export"]}'::jsonb
WHERE nombre = 'supervisor';

UPDATE roles SET permisos = permisos || '{"visita_vehicular":["read","write"]}'::jsonb
WHERE nombre IN ('operador','guarda_bodega','guarda_vehicular');
