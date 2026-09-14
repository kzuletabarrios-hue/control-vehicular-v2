-- ================================================================
-- CONTROL VEHICULAR CEDI R10 · v2
-- Módulo de autenticación y roles
-- Ejecutar DESPUÉS del schema.sql original
-- ================================================================

-- ── ROLES ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    permisos    JSONB DEFAULT '{}'::jsonb
);

INSERT INTO roles (nombre, descripcion, permisos) VALUES
  ('admin',    'Acceso total al sistema',
   '{"flota":["read","write","delete","export"],
     "proveedores":["read","write","delete","export"],
     "control_acceso":["read","write","delete","export"],
     "visitantes":["read","write","delete","export"],
     "maestros":["read","write","delete"],
     "usuarios":["read","write","delete"],
     "dashboard":["read"]}'::jsonb),
  ('supervisor','Lectura + escritura, sin eliminar ni gestionar usuarios',
   '{"flota":["read","write","export"],
     "proveedores":["read","write","export"],
     "control_acceso":["read","write","export"],
     "visitantes":["read","write","export"],
     "maestros":["read"],
     "dashboard":["read"]}'::jsonb),
  ('operador', 'Solo registro de datos propios del turno',
   '{"flota":["read","write"],
     "proveedores":["read","write"],
     "control_acceso":["read","write"],
     "visitantes":["read","write"],
     "dashboard":["read"]}'::jsonb),
  ('consulta', 'Solo lectura y exportación',
   '{"flota":["read","export"],
     "proveedores":["read","export"],
     "control_acceso":["read","export"],
     "visitantes":["read","export"],
     "dashboard":["read"]}'::jsonb)
ON CONFLICT (nombre) DO NOTHING;

-- ── USUARIOS ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre          TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    rol_id          INT NOT NULL REFERENCES roles(id) ON UPDATE CASCADE,
    activo          BOOLEAN DEFAULT TRUE,
    ultimo_acceso   TIMESTAMPTZ,
    creado_por      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email  ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_usuarios_activo ON usuarios(activo);
CREATE INDEX IF NOT EXISTS idx_usuarios_rol    ON usuarios(rol_id);

-- ── SESIONES (refresh tokens) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS sesiones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id      UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    refresh_token   TEXT NOT NULL UNIQUE,
    ip_address      TEXT,
    user_agent      TEXT,
    expires_at      TIMESTAMPTZ NOT NULL,
    revocada        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sesiones_usuario  ON sesiones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_token    ON sesiones(refresh_token);
CREATE INDEX IF NOT EXISTS idx_sesiones_expires  ON sesiones(expires_at);

-- ── AUDIT LOG ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_email   TEXT,
    accion          TEXT NOT NULL,       -- INSERT, UPDATE, DELETE
    tabla           TEXT NOT NULL,
    registro_id     TEXT,
    datos_antes     JSONB,
    datos_despues   JSONB,
    ip_address      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_usuario  ON audit_log(usuario_id);
CREATE INDEX IF NOT EXISTS idx_audit_tabla    ON audit_log(tabla);
CREATE INDEX IF NOT EXISTS idx_audit_fecha    ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_accion   ON audit_log(accion);

-- ── TRIGGER updated_at para usuarios ─────────────────────────────
CREATE TRIGGER trg_updated_at_usuarios
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ── COLUMNA usuario_id en tablas operativas ───────────────────────
-- Agrega trazabilidad de quién creó cada registro
ALTER TABLE flota_propia    ADD COLUMN IF NOT EXISTS creado_por UUID REFERENCES usuarios(id) ON DELETE SET NULL;
ALTER TABLE proveedores     ADD COLUMN IF NOT EXISTS creado_por UUID REFERENCES usuarios(id) ON DELETE SET NULL;
ALTER TABLE control_acceso  ADD COLUMN IF NOT EXISTS creado_por UUID REFERENCES usuarios(id) ON DELETE SET NULL;
ALTER TABLE visitantes      ADD COLUMN IF NOT EXISTS creado_por UUID REFERENCES usuarios(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_fp_creado_por ON flota_propia(creado_por);

-- ── FUNCIÓN: verificar permiso ────────────────────────────────────
CREATE OR REPLACE FUNCTION tiene_permiso(
    p_usuario_id UUID,
    p_modulo     TEXT,
    p_accion     TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_permisos JSONB;
    v_activo   BOOLEAN;
BEGIN
    SELECT r.permisos, u.activo
    INTO v_permisos, v_activo
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    WHERE u.id = p_usuario_id;

    IF NOT FOUND OR NOT v_activo THEN
        RETURN FALSE;
    END IF;

    RETURN v_permisos -> p_modulo ? p_accion;
END;
$$ LANGUAGE plpgsql STABLE;

-- ── USUARIO ADMIN INICIAL ─────────────────────────────────────────
-- Contraseña: Admin2024! (CAMBIAR INMEDIATAMENTE al primer login)
-- Hash generado con bcrypt rounds=12
INSERT INTO usuarios (nombre, email, password_hash, rol_id)
SELECT
    'Administrador',
    'admin@cedirex.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMaB3HXKJPjRRPRCKlhRbBEvPm',
    (SELECT id FROM roles WHERE nombre = 'admin')
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'admin@cedirex.com');
