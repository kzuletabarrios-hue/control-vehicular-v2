-- Tabla maestra de vehículos (carga masiva)
CREATE TABLE IF NOT EXISTS vehiculos (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    placa       TEXT NOT NULL UNIQUE,
    marca       TEXT,
    modelo      TEXT,
    color       TEXT,
    anio        INT,
    tipo        TEXT,
    capacidad   TEXT,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vehiculos_placa  ON vehiculos(placa);
CREATE INDEX IF NOT EXISTS idx_vehiculos_activo ON vehiculos(activo);

CREATE TRIGGER trg_updated_at_vehiculos
    BEFORE UPDATE ON vehiculos
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
