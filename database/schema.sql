-- ================================================================
-- CONTROL VEHICULAR CEDI R10 · v2
-- Schema principal — tablas operativas
-- Ejecutar ANTES de auth_schema.sql
-- ================================================================

-- Extensión UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── TRIGGER updated_at ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ── CONDUCTORES (maestro) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conductores (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo      INT UNIQUE,
    conductor   TEXT NOT NULL,
    n_cedula    TEXT,
    celular     TEXT,
    tipo        TEXT,
    activo      BOOLEAN DEFAULT TRUE,
    foto_url    TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conductores_codigo ON conductores(codigo);
CREATE INDEX IF NOT EXISTS idx_conductores_activo ON conductores(activo);

CREATE TRIGGER trg_updated_at_conductores
    BEFORE UPDATE ON conductores
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── DISTRIBUCIÓN / TIENDAS (maestro) ────────────────────────────
CREATE TABLE IF NOT EXISTS distribucion (
    id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name    TEXT NOT NULL UNIQUE
);


-- ── FLOTA PROPIA ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS flota_propia (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha                   DATE NOT NULL DEFAULT CURRENT_DATE,
    placa                   TEXT NOT NULL,
    codigo_conductor        INT REFERENCES conductores(codigo) ON DELETE SET NULL,
    conductor               TEXT,
    n_pallets               INT,
    n_contenedores          INT,
    cant_volumen_externo    TEXT,
    muelle_cargue           TEXT,
    tienda_1                UUID REFERENCES distribucion(id) ON DELETE SET NULL,
    tienda_2                UUID REFERENCES distribucion(id) ON DELETE SET NULL,
    tienda_3                UUID REFERENCES distribucion(id) ON DELETE SET NULL,
    tienda_4                UUID REFERENCES distribucion(id) ON DELETE SET NULL,
    tienda_5                UUID REFERENCES distribucion(id) ON DELETE SET NULL,
    ultima_tienda           UUID REFERENCES distribucion(id) ON DELETE SET NULL,
    ultima_tienda_visitada  TEXT,
    protocolo               TEXT,
    sello                   TEXT,
    sello_entrada           TEXT,
    hora_salida_muelle      TIME,
    temperatura             TEXT,
    hora_salida_cedi        TIME,
    hora_llegada            TIME,
    observacion             TEXT,
    foto_url                TEXT,
    creado_por              UUID,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fp_fecha  ON flota_propia(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_fp_placa  ON flota_propia(placa);

CREATE TRIGGER trg_updated_at_flota
    BEFORE UPDATE ON flota_propia
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── BD PROVEEDORES (maestro) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS bd_proveedores (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre      TEXT NOT NULL,
    nit         TEXT,
    contacto    TEXT,
    celular     TEXT,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trg_updated_at_bd_proveedores
    BEFORE UPDATE ON bd_proveedores
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── PROVEEDORES TGN (registros diarios) ─────────────────────────
CREATE TABLE IF NOT EXISTS proveedores (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha                   DATE NOT NULL DEFAULT CURRENT_DATE,
    placa_vehiculo          TEXT,
    nombre_conductor        TEXT,
    tipo_vehiculo           TEXT,
    empresa                 TEXT,
    muelle_descargue        TEXT,
    carga_compartida        TEXT,
    hora_ingreso            TIME,
    hora_salida             TIME,
    actividad_a_desarrollar TEXT,
    dependencia_autoriza    TEXT,
    fecha_pago_arl          DATE,
    observaciones           TEXT,
    foto_url                TEXT,
    creado_por              UUID,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prov_fecha   ON proveedores(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_prov_empresa ON proveedores(empresa);

CREATE TRIGGER trg_updated_at_proveedores
    BEFORE UPDATE ON proveedores
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── BD CONTROL ACCESO (maestro contratistas) ─────────────────────
CREATE TABLE IF NOT EXISTS bd_control_acceso (
    cedula      BIGINT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    contratista TEXT,
    estado      TEXT DEFAULT 'ACTIVO',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trg_updated_at_bd_ca
    BEFORE UPDATE ON bd_control_acceso
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── CONTROL ACCESO (registros diarios) ──────────────────────────
CREATE TABLE IF NOT EXISTS control_acceso (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha           DATE NOT NULL DEFAULT CURRENT_DATE,
    cedula          BIGINT REFERENCES bd_control_acceso(cedula) ON DELETE SET NULL,
    nombre          TEXT,
    contratista     TEXT,
    hora_ingreso    TIME,
    hora_salida     TIME,
    observaciones   TEXT,
    foto_url        TEXT,
    creado_por      UUID,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ca_fecha  ON control_acceso(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_ca_cedula ON control_acceso(cedula);

CREATE TRIGGER trg_updated_at_ca
    BEFORE UPDATE ON control_acceso
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── VISITANTES ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS visitantes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha           DATE NOT NULL DEFAULT CURRENT_DATE,
    nombre          TEXT NOT NULL,
    cedula          TEXT,
    empresa         TEXT,
    hora_ingreso    TIME,
    hora_salida     TIME,
    observaciones   TEXT,
    foto_url        TEXT,
    creado_por      UUID,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vis_fecha ON visitantes(fecha DESC);

CREATE TRIGGER trg_updated_at_visitantes
    BEFORE UPDATE ON visitantes
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- ── REGISTROS (tabla genérica AppSheet legado) ───────────────────
CREATE TABLE IF NOT EXISTS registros (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha       DATE,
    tipo        TEXT,
    datos       JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
