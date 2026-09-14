-- ================================================================
-- Seed mínimo de datos FICTICIOS para entornos local/test.
-- Autor: Jorge Peña (Arquitecto de BD), 2026-09-14.
--
-- Ningún dato de este archivo proviene de producción -- nombres,
-- cédulas, placas, empresas y correos son inventados a propósito
-- (dominio @ejemplo.test, placas TST-xxx, cédulas que empiezan en
-- 900000...). No copiar nunca datos reales del CEDI aquí.
--
-- Contraseña de TODOS los usuarios de seed: Test1234!
-- (hash bcrypt rounds=12 generado con el mismo algoritmo que usa el
-- backend real -- ver backend/routers/auth.py, _hash_password).
--
-- Aplicado automáticamente por `supabase db reset` / `supabase start`
-- después de correr todo supabase/migrations/ en orden. Pensado para
-- ejecutarse SOLO contra el stack local (nunca apuntar este archivo a
-- producción).
--
-- Idempotente: todos los INSERT usan ON CONFLICT DO NOTHING sobre una
-- clave natural (email, placa, codigo, nombre, etc.) -- correr este
-- archivo más de una vez no duplica filas.
--
-- Cobertura: un usuario por cada uno de los 9 roles reales (incluye
-- guarda_bodega/guarda_peatonal/guarda_vehicular/recorredor_externo/
-- coordinador -- los 9 roles ya quedan de alta con solo
-- supabase/migrations/, incluido 'coordinador' vía
-- 20260804110000_alta_formal_coordinador_retroactivo.sql), 2 tiendas,
-- 2 conductores, 2 vehículos, 2 filas de flota propia, 2 proveedores
-- (con sus órdenes), 2 registros de control de acceso peatonal/
-- vehicular, 2 visitantes, 1 visita vehicular, 1 fila de configuracion
-- y 2 muelles de catálogo (tablas creadas por
-- 20260804100000_schema_tablas_huerfanas_drift.sql). El guard
-- `to_regclass(...) IS NOT NULL` sobre estas últimas se deja de todas
-- formas por defensividad -- no rompe el seed si alguien corre esta
-- carpeta parcialmente o reordena algo en el futuro.
-- ================================================================


-- ── USUARIOS (uno por rol) ───────────────────────────────────────
-- Hash real de 'Test1234!' (bcrypt, rounds=12):
--   $2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Ana Admin Prueba', 'admin@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'admin'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'admin@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Sara Supervisor Prueba', 'supervisor@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'supervisor'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'supervisor@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Oscar Operador Prueba', 'operador@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'operador'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'operador@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Carla Consulta Prueba', 'consulta@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'consulta'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'consulta@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Beto Guarda Bodega Prueba', 'guarda.bodega@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'guarda_bodega'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'guarda.bodega@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Pedro Guarda Peatonal Prueba', 'guarda.peatonal@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'guarda_peatonal'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'guarda.peatonal@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Vicky Guarda Vehicular Prueba', 'guarda.vehicular@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'guarda_vehicular'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'guarda.vehicular@ejemplo.test');

INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Rita Recorredora Externa Prueba', 'recorredor.externo@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       (SELECT id FROM roles WHERE nombre = 'recorredor_externo'), TRUE
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'recorredor.externo@ejemplo.test');

-- coordinador: el rol solo existe si se aplicó también la propuesta de
-- alta retroactiva (ver PROPUESTA_recrea_tablas_columnas_huerfanas.sql,
-- sección 10) -- guard defensivo para que este seed no falle si esa
-- propuesta todavía no fue revisada/adoptada.
INSERT INTO usuarios (nombre, email, password_hash, rol_id, activo)
SELECT 'Coco Coordinador Prueba', 'coordinador@ejemplo.test',
       '$2b$12$HET3Ewt.NZKOvX9f7jkNG.v.VrSwkOg73fUVQ7lSoort7ZYD7UNO6',
       r.id, TRUE
FROM roles r
WHERE r.nombre = 'coordinador'
  AND NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'coordinador@ejemplo.test');


-- ── DISTRIBUCIÓN (tiendas, maestro) ──────────────────────────────
INSERT INTO distribucion (codigo, name, direccion) VALUES
  (9001, 'Tienda Prueba Norte', 'Calle Ficticia 1, Bogotá'),
  (9002, 'Tienda Prueba Sur',   'Calle Ficticia 2, Bogotá')
ON CONFLICT (name) DO NOTHING;


-- ── CONDUCTORES (maestro) ────────────────────────────────────────
INSERT INTO conductores (codigo, conductor, n_cedula, celular, tipo, activo) VALUES
  (9001, 'Luis Conductor Prueba',  '900000001', '3000000001', 'planta', TRUE),
  (9002, 'Marta Conductora Prueba','900000002', '3000000002', 'contratista', TRUE)
ON CONFLICT (codigo) DO NOTHING;


-- ── VEHÍCULOS (maestro) ──────────────────────────────────────────
INSERT INTO vehiculos (placa, marca, modelo, color, anio, tipo, capacidad, activo) VALUES
  ('TST-001', 'Chevrolet', 'NHR',    'Blanco', 2020, 'furgon',  '3.5 ton', TRUE),
  ('TST-002', 'Ford',      'Cargo',  'Gris',   2019, 'camion',  '8 ton',   TRUE)
ON CONFLICT (placa) DO NOTHING;


-- ── FLOTA PROPIA (registros diarios) ─────────────────────────────
INSERT INTO flota_propia (fecha, placa, codigo_conductor, conductor, n_pallets, muelle_cargue, tienda_1, observacion)
SELECT CURRENT_DATE, 'TST-001', 9001, 'Luis Conductor Prueba', 12, '3',
       (SELECT id FROM distribucion WHERE name = 'Tienda Prueba Norte'),
       'Carga de prueba -- seed local'
WHERE NOT EXISTS (
  SELECT 1 FROM flota_propia WHERE placa = 'TST-001' AND fecha = CURRENT_DATE
);

INSERT INTO flota_propia (fecha, placa, codigo_conductor, conductor, n_pallets, muelle_cargue, tienda_1, observacion)
SELECT CURRENT_DATE, 'TST-002', 9002, 'Marta Conductora Prueba', 8, '5',
       (SELECT id FROM distribucion WHERE name = 'Tienda Prueba Sur'),
       'Carga de prueba -- seed local'
WHERE NOT EXISTS (
  SELECT 1 FROM flota_propia WHERE placa = 'TST-002' AND fecha = CURRENT_DATE
);


-- ── BD_PROVEEDORES (maestro) + PROVEEDORES (registros diarios) ──
-- bd_proveedores no tiene UNIQUE sobre `nit`/`nombre` en el esquema
-- real (solo PK sobre id) -- se usa NOT EXISTS por nit en vez de
-- ON CONFLICT para que el seed sea idempotente igual.
INSERT INTO bd_proveedores (nombre, nit, contacto, celular, activo)
SELECT 'Proveedor Prueba Uno S.A.S.', '900111111-1', 'Contacto Uno', '3001111111', TRUE
WHERE NOT EXISTS (SELECT 1 FROM bd_proveedores WHERE nit = '900111111-1');

INSERT INTO bd_proveedores (nombre, nit, contacto, celular, activo)
SELECT 'Proveedor Prueba Dos Ltda.', '900222222-2', 'Contacto Dos', '3002222222', TRUE
WHERE NOT EXISTS (SELECT 1 FROM bd_proveedores WHERE nit = '900222222-2');

INSERT INTO proveedores (fecha, placa_vehiculo, nombre_conductor, tipo_vehiculo, empresa,
                          muelle_descargue, hora_ingreso, actividad_a_desarrollar,
                          dependencia_autoriza, observaciones, origen)
SELECT CURRENT_DATE, 'TST-101', 'Conductor Externo Uno', 'camion',
       'Proveedor Prueba Uno S.A.S.', '7', CURRENT_TIME, 'Descargue de mercancía',
       'Bodega', 'Registro de prueba -- seed local', 'guarda'
WHERE NOT EXISTS (
  SELECT 1 FROM proveedores WHERE placa_vehiculo = 'TST-101' AND fecha = CURRENT_DATE
);

INSERT INTO proveedores (fecha, placa_vehiculo, nombre_conductor, tipo_vehiculo, empresa,
                          muelle_descargue, hora_ingreso, actividad_a_desarrollar,
                          dependencia_autoriza, observaciones, origen)
SELECT CURRENT_DATE, 'TST-102', 'Conductor Externo Dos', 'tractomula',
       'Proveedor Prueba Dos Ltda.', '9', CURRENT_TIME, 'Descargue de mercancía',
       'Bodega', 'Registro de prueba -- seed local', 'autorregistro'
WHERE NOT EXISTS (
  SELECT 1 FROM proveedores WHERE placa_vehiculo = 'TST-102' AND fecha = CURRENT_DATE
);

INSERT INTO proveedores_ordenes (proveedor_id, empresa, muelle_descargue, actividad_a_desarrollar, dependencia_autoriza)
SELECT p.id, p.empresa, p.muelle_descargue, p.actividad_a_desarrollar, p.dependencia_autoriza
FROM proveedores p
WHERE p.placa_vehiculo IN ('TST-101', 'TST-102')
  AND p.fecha = CURRENT_DATE
  AND NOT EXISTS (SELECT 1 FROM proveedores_ordenes o WHERE o.proveedor_id = p.id);


-- ── BD_CONTROL_ACCESO (maestro contratistas) + CONTROL_ACCESO ───
INSERT INTO bd_control_acceso (cedula, nombre, contratista, estado) VALUES
  (900333333, 'Contratista Prueba Uno', 'Empresa Contratista Prueba', 'ACTIVO'),
  (900444444, 'Contratista Prueba Dos', 'Empresa Contratista Prueba', 'ACTIVO')
ON CONFLICT (cedula) DO NOTHING;

INSERT INTO control_acceso (fecha, cedula, nombre, contratista, hora_ingreso, observaciones)
SELECT CURRENT_DATE, 900333333, 'Contratista Prueba Uno', 'Empresa Contratista Prueba',
       CURRENT_TIME, 'Ingreso de prueba -- seed local'
WHERE NOT EXISTS (
  SELECT 1 FROM control_acceso WHERE cedula = 900333333 AND fecha = CURRENT_DATE
);


-- ── VISITANTES ───────────────────────────────────────────────────
INSERT INTO visitantes (fecha, nombre, cedula, empresa, hora_ingreso, observaciones)
SELECT CURRENT_DATE, 'Visitante Prueba Uno', '900555555', 'Empresa Visitante Prueba',
       CURRENT_TIME, 'Visita de prueba -- seed local'
WHERE NOT EXISTS (
  SELECT 1 FROM visitantes WHERE cedula = '900555555' AND fecha = CURRENT_DATE
);

INSERT INTO visitantes (fecha, nombre, cedula, empresa, hora_ingreso, observaciones)
SELECT CURRENT_DATE, 'Visitante Prueba Dos', '900666666', 'Empresa Visitante Prueba',
       CURRENT_TIME, 'Visita de prueba -- seed local'
WHERE NOT EXISTS (
  SELECT 1 FROM visitantes WHERE cedula = '900666666' AND fecha = CURRENT_DATE
);


-- ── VISITA VEHICULAR ─────────────────────────────────────────────
-- CORRECCIÓN (Jorge, 2026-09-14): `to_char(CURRENT_TIME, 'HH24:MI:SS')`
-- fallaba con "no existe la función to_char(time with time zone,
-- unknown)" -- Postgres no tiene ninguna sobrecarga de to_char() para
-- el tipo time (ni with ni without time zone), solo para
-- timestamp/timestamptz/interval/numeric. Hallazgo de María corriendo
-- el seed completo contra una base nueva, 2026-09-14 -- reproducible
-- siempre, no depende de datos.
-- visita_vehicular.hora_ingreso es TEXT (no TIME -- distinto del resto
-- de tablas del seed, que sí tienen columnas TIME reales donde
-- CURRENT_TIME funciona directo), así que sigue haciendo falta
-- convertir a texto -- se usa to_char(now(), 'HH24:MI:SS') en vez de
-- CURRENT_TIME::text para evitar el offset de zona horaria que un
-- cast directo de CURRENT_TIME (time with time zone) agregaría al
-- texto (ej. "14:23:05-05"), y para quedar consistente con el
-- formato "HH:MM:SS" limpio que usa el propio backend real
-- (datetime.now(_BOG).strftime("%H:%M:%S"), ver backend/routers/*.py)
-- para las columnas TEXT de hora en esta tabla.
INSERT INTO visita_vehicular (fecha, placa, conductor, motivo_visita, hora_ingreso, empresa_pertenece)
SELECT CURRENT_DATE, 'TST-201', 'Conductor Visita Prueba', 'Visita administrativa de prueba',
       to_char(now(), 'HH24:MI:SS'), 'Empresa Visita Prueba'
WHERE NOT EXISTS (
  SELECT 1 FROM visita_vehicular WHERE placa = 'TST-201' AND fecha = CURRENT_DATE
);


-- ── OBJETOS DE LAS TABLAS RECONSTRUIDAS POR DRIFT ────────────────
-- `configuracion` y `muelles` ya se crean siempre con solo
-- supabase/migrations/ (20260804100000_schema_tablas_huerfanas_drift.sql).
-- Se deja el guard `to_regclass` por defensividad -- no-op seguro si
-- algún día se corre este seed sin esa migración aplicada.
DO $$
BEGIN
    IF to_regclass('public.configuracion') IS NOT NULL THEN
        INSERT INTO configuracion (clave, valor)
        VALUES ('tolerancia_min_default', '60')
        ON CONFLICT (clave) DO NOTHING;
    END IF;

    IF to_regclass('public.muelles') IS NOT NULL THEN
        INSERT INTO muelles (numero, zona, activo, tipo_carga_habitual) VALUES
          ('1', 'Zona A', TRUE, 'Seca'),
          ('2', 'Zona A', TRUE, 'Refrigerada')
        ON CONFLICT (numero) DO NOTHING;
    END IF;
END $$;
-- ================================================================
