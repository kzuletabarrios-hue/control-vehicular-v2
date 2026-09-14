-- ================================================================
-- Recrea, vía CREATE TABLE / ALTER TABLE / CREATE INDEX, los objetos
-- que existen en producción (Supabase, proyecto control-vehicular-cedi)
-- pero que NUNCA tuvieron esa definición versionada en git -- ni en
-- database/ ni en backend/migrations_manual/: las 8 tablas originales
-- + 2 columnas de proveedores_ordenes (drift documentado en
-- 00000000000000_LEAME_metodologia_y_hallazgos.sql, sección 2a/2b),
-- más el índice `idx_proveedores_ordenes_cita_id` y la columna
-- `proveedores.origen`, agregados el 2026-09-14 tras el hallazgo de
-- María corriendo las 46 migraciones contra una base vacía real (ver
-- secciones 9-10 más abajo para el detalle de estos 2 últimos).
--
-- Autor: Jorge Peña (Arquitecto de BD). Investigado y propuesto
-- 2026-09-14; revisado y APROBADO por Alejandro el mismo día (las 3
-- partes de la propuesta original: este esquema, la alta de
-- `coordinador` -- ver 20260804110000_alta_formal_coordinador_retroactivo.sql,
-- archivo separado -- y la condición de gobierno de la sección
-- siguiente).
--
-- ── UBICACIÓN EN LA SECUENCIA (fecha deliberadamente ANTERIOR a la
--    fecha real de esta investigación) ───────────────────────────
-- Aunque el hallazgo y la redacción de este archivo son del
-- 2026-09-14, el timestamp de archivo es 2026-08-04 -- ANTES de
-- 2026-08-05, por instrucción explícita de Alejandro, porque 5
-- migraciones YA INCLUIDAS en supabase/migrations/ asumen que estas
-- tablas/columnas ya existen (hacen COMMENT ON / ALTER TABLE / CREATE
-- INDEX directo sobre ellas, sin crearlas):
--   - 20260805202430_documenta_citas_programadas_existente.sql
--   - 20260806105156_indice_proveedores_ordenes_cita_id.sql
--   - 20260806115339_citas_programadas_hora_editada_manualmente.sql
--   - 20260807183041_auditoria_fase51_unificacion_citas_qr.sql
--   - 20260911130929_indices_llaves_foraneas.sql (4 de sus ~22 índices)
-- Mismo criterio ya aplicado a
-- 20260601101440_roles_guarda_alta_formal_retroactivo.sql. Se
-- verificó (grep exhaustivo de \bmuelles\b, \bmuelle_eventos\b,
-- \bsustancias\b, \bherramientas\b, \bconfiguracion\b,
-- \bconductores_frecuentes\b, \bcitas_programadas\b, \barchivos_citas\b
-- en todo supabase/migrations/) que NINGUNA migración con fecha
-- ANTERIOR al 2026-08-04 hace referencia ejecutable (DDL/DML real) a
-- estos objetos -- las únicas coincidencias en archivos previos son
-- menciones en prosa (comentarios sobre la app hermana
-- "citas-muelles-cedi-r10", rutas de archivo como
-- "backend/routers/muelles.py", o claves de permisos jsonb como
-- "muelles":"liberar" dentro de roles.permisos, que NO requieren que
-- la tabla `muelles` exista para ejecutarse -- un jsonb no valida
-- contra el catálogo de tablas). No hace falta mover ninguna tabla
-- individual más temprano que las demás.
--
-- ── CONDICIÓN DE GOBIERNO (impuesta por Alejandro al aprobar) ────
-- Este repositorio (control-vehicular-v2) pasa a versionar el esquema
-- de `citas_programadas` y `archivos_citas` porque (a) las CONSUME de
-- forma real -- FK real vía `proveedores_ordenes.cita_id` -- y (b) ya
-- tenía comentarios versionados sobre ellas desde el 2026-08-05.
--
-- CORRECCIÓN (2026-09-14, mismo día): la condición de gobierno original
-- de este párrafo asumía que `citas-muelles-cedi-r10` seguía en uso
-- compartido activo con "otro mantenedor" a quien coordinar. Verificado
-- después con la API de Vercel: esa app NO tiene ningún deploy desde el
-- 2026-08-05 (más de un mes antes de esta migración), y siempre fue
-- desplegada por la misma persona dueña de este repo -- nunca hubo un
-- equipo separado. Los manuales de este mismo repo (docs/*.html,
-- commit 6bdb224, mismo día) ya documentan que esa app se dio de baja
-- formalmente en septiembre 2026 y que su funcionalidad quedó
-- absorbida aquí. Es decir: no hay ningún "otro mantenedor" con quien
-- coordinar -- este repositorio es hoy el único dueño real, no solo el
-- único registro versionado, del esquema de `citas_programadas` y
-- `archivos_citas`. Se deja este archivo y su historial de decisión
-- intactos (transparencia de auditoría), pero la condición de
-- "coordinar con quien mantenga esa app" queda sin efecto: no aplica
-- porque no hay tal persona/equipo. Si `citas-muelles-cedi-r10` se
-- reactivara alguna vez, esa condición volvería a tener sentido.
--
-- ── CÓMO SE OBTUVO ESTE DDL ──────────────────────────────────────
-- 100% por introspección de SOLO LECTURA contra Supabase producción
-- (information_schema.columns, pg_constraint, pg_indexes), el
-- 2026-09-14. No se infirió ni se completó nada por analogía -- cada
-- columna, tipo, default, CHECK, FK e índice de abajo está tomado
-- literalmente del esquema real.
--
-- Idempotente: CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS /
-- índices con IF NOT EXISTS en todo el archivo -- no-op seguro tanto
-- contra producción (donde ya existen) como contra un ambiente nuevo
-- reconstruido desde cero.
-- ================================================================


-- ── 1. muelles ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS muelles (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    numero               TEXT NOT NULL UNIQUE,
    zona                 TEXT,
    activo               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    tipo_carga_habitual  VARCHAR(30)
        CHECK (tipo_carga_habitual IS NULL
               OR tipo_carga_habitual IN ('Seca','Refrigerada','Mixta'))
);


-- ── 2. configuracion (clave-valor genérica) ─────────────────────
CREATE TABLE IF NOT EXISTS configuracion (
    clave        TEXT PRIMARY KEY,
    valor        TEXT NOT NULL,
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_por  UUID REFERENCES usuarios(id)
);

CREATE INDEX IF NOT EXISTS idx_configuracion_updated_por ON configuracion(updated_por);


-- ── 3. sustancias ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sustancias (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha          DATE NOT NULL DEFAULT CURRENT_DATE,
    descripcion    TEXT NOT NULL,
    cantidad       TEXT,
    responsable    TEXT,
    observaciones  TEXT,
    foto_url       TEXT,
    creado_por     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    hora_salida    VARCHAR,
    fecha_salida   DATE,
    es_consumible  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sust_fecha ON sustancias(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_sustancias_creado_por ON sustancias(creado_por);


-- ── 4. herramientas ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS herramientas (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha          DATE NOT NULL DEFAULT CURRENT_DATE,
    descripcion    TEXT NOT NULL,
    cantidad       TEXT,
    responsable    TEXT,
    observaciones  TEXT,
    foto_url       TEXT,
    creado_por     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    hora_salida    VARCHAR,
    fecha_salida   DATE,
    es_consumible  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_herr_fecha ON herramientas(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_herramientas_creado_por ON herramientas(creado_por);


-- ── 5. conductores_frecuentes ────────────────────────────────────
CREATE TABLE IF NOT EXISTS conductores_frecuentes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cedula              TEXT NOT NULL UNIQUE,
    nombre_conductor    TEXT NOT NULL,
    empresa_principal   TEXT,
    tipo_vehiculo       TEXT,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    ultima_visita       DATE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    telefono            TEXT
);

CREATE INDEX IF NOT EXISTS idx_cond_frec_cedula ON conductores_frecuentes(cedula);
CREATE INDEX IF NOT EXISTS idx_cond_frec_activo ON conductores_frecuentes(activo);


-- ── 6. archivos_citas (bitácora de lotes de importación WMS) ────
-- USO COMPARTIDO con citas-muelles-cedi-r10 -- ver condición de
-- gobierno en el encabezado de este archivo.
CREATE TABLE IF NOT EXISTS archivos_citas (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha             DATE,
    nombre_archivo    TEXT,
    subido_por        UUID REFERENCES usuarios(id),
    total_filas       INTEGER NOT NULL DEFAULT 0,
    filas_importadas  INTEGER NOT NULL DEFAULT 0,
    filas_error       INTEGER NOT NULL DEFAULT 0,
    detalle_errores   JSONB,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_archivos_citas_fecha ON archivos_citas(fecha);
CREATE INDEX IF NOT EXISTS idx_archivos_citas_subido_por ON archivos_citas(subido_por);


-- ── 7. citas_programadas ─────────────────────────────────────────
-- USO COMPARTIDO con citas-muelles-cedi-r10 -- ver condición de
-- gobierno en el encabezado de este archivo. El UNIQUE
-- (fecha, numero_orden_compra) y el CHECK de numero_orden_compra son
-- drift que "ayuda" (documentado en
-- 2026-08-07_auditoria_fase51_unificacion_citas_qr.sql): ya existían
-- en producción sin que ninguna migración de este repo los hubiera
-- creado.
CREATE TABLE IF NOT EXISTS citas_programadas (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    archivo_id               UUID REFERENCES archivos_citas(id) ON DELETE SET NULL,
    fecha                    DATE NOT NULL,
    numero_orden_compra      TEXT NOT NULL
        CHECK (numero_orden_compra ~ '^4[0-9]{9}$'),
    proveedor_codigo         TEXT,
    proveedor_nombre         TEXT,
    flujo                    TEXT,
    descripcion_carga        TEXT,
    fecha_documento_compra   DATE,
    cantidad_pallets         TEXT,
    hora_cita_inicio         TIME NOT NULL,
    hora_cita_fin            TIME NOT NULL,
    tolerancia_min           INTEGER NOT NULL DEFAULT 30,
    estado                   TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente','usada','vencida','cancelada')),
    proveedor_id              UUID REFERENCES proveedores(id) ON DELETE SET NULL,
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW(),
    hora_editada_manualmente  BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT citas_programadas_fecha_numero_orden_compra_key UNIQUE (fecha, numero_orden_compra)
);

CREATE INDEX IF NOT EXISTS idx_citas_programadas_fecha ON citas_programadas(fecha);
CREATE INDEX IF NOT EXISTS idx_citas_programadas_orden ON citas_programadas(numero_orden_compra);
CREATE INDEX IF NOT EXISTS idx_citas_programadas_archivo_id ON citas_programadas(archivo_id);
CREATE INDEX IF NOT EXISTS idx_citas_programadas_proveedor_id ON citas_programadas(proveedor_id);


-- ── 8. muelle_eventos ─────────────────────────────────────────────
-- 0 filas en producción, sin uso operativo real hoy (ver
-- 2026-08-08_proveedores_muelle_liberado_columns.sql: el flujo real de
-- "liberar muelle" pasa por columnas directas en `proveedores`, no por
-- esta tabla). Se recrea de todas formas por fidelidad al esquema
-- real -- no se decide aquí si debe seguir existiendo; eso es
-- decisión de Alejandro.
CREATE TABLE IF NOT EXISTS muelle_eventos (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    muelle_id      UUID NOT NULL REFERENCES muelles(id),
    proveedor_id   UUID NOT NULL REFERENCES proveedores(id),
    asignado_por   UUID REFERENCES usuarios(id),
    hora_asignado  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    liberado_por   UUID REFERENCES usuarios(id),
    hora_liberado  TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_muelle_eventos_activo_unico
    ON muelle_eventos(muelle_id) WHERE (hora_liberado IS NULL);
CREATE INDEX IF NOT EXISTS idx_muelle_eventos_proveedor ON muelle_eventos(proveedor_id);
CREATE INDEX IF NOT EXISTS idx_muelle_eventos_asignado_por ON muelle_eventos(asignado_por);
CREATE INDEX IF NOT EXISTS idx_muelle_eventos_liberado_por ON muelle_eventos(liberado_por);


-- ── 9. proveedores_ordenes: 2 columnas huérfanas ──────────────────
-- Drift documentado (COMMENT ON) en
-- 2026-08-06_indice_proveedores_ordenes_cita_id.sql, pero nunca
-- creadas por ningún ALTER TABLE versionado. Va DESPUÉS de
-- citas_programadas (arriba) porque cita_id la referencia por FK.
ALTER TABLE proveedores_ordenes
  ADD COLUMN IF NOT EXISTS numero_orden_compra TEXT,
  ADD COLUMN IF NOT EXISTS cita_id UUID REFERENCES citas_programadas(id) ON DELETE SET NULL;

-- NOTA: 20260806105156_indice_proveedores_ordenes_cita_id.sql (ya
-- incluido en supabase/migrations/, con fecha posterior a este
-- archivo) crea el índice UNIQUE PARCIAL sobre esta columna
-- (idx_proveedores_ordenes_cita_id_unico) -- no se duplica aquí.
--
-- AGREGADO 2026-09-14 (hallazgo de María corriendo las 46 migraciones
-- contra una base vacía real): además del índice único parcial de
-- arriba, producción tiene un SEGUNDO índice, simple (no único), sobre
-- la misma columna -- `idx_proveedores_ordenes_cita_id` -- que
-- tampoco tenía CREATE INDEX versionado en ningún script. Es el mismo
-- índice que la propia auditoría Fase 5.1
-- (20260807183041_auditoria_fase51_unificacion_citas_qr.sql) señaló
-- como "redundante" con el único parcial, sin eliminarlo por estar
-- fuera de alcance de esa auditoría de solo lectura -- pero sí lo
-- comenta con `COMMENT ON INDEX`, lo cual requiere que el índice ya
-- exista para cuando esa migración corra. Se crea aquí, junto a la
-- columna que indexa, por ser el lugar más simple de razonar (no se
-- elimina la redundancia -- esa es una decisión de limpieza aparte,
-- ya señalada como pendiente de bajo riesgo en la Fase 5.1, no de esta
-- migración).
CREATE INDEX IF NOT EXISTS idx_proveedores_ordenes_cita_id ON proveedores_ordenes(cita_id);

-- ── 10. proveedores.origen ────────────────────────────────────────
-- AGREGADO 2026-09-14 (mismo hallazgo de María): columna huérfana
-- adicional, sin ALTER TABLE versionado en ningún script -- necesaria
-- para que 20260807183041_auditoria_fase51_unificacion_citas_qr.sql
-- (que hace COMMENT ON COLUMN proveedores.origen) no falle contra una
-- base vacía. Definición confirmada por SELECT de solo lectura contra
-- producción el 2026-09-14 (information_schema.columns + pg_constraint):
-- TEXT NOT NULL DEFAULT 'guarda', CHECK (origen IN ('guarda',
-- 'autorregistro')) -- constraint real `proveedores_origen_check`.
-- Uso real confirmado en supabase/seed.sql (ya la usa) y en
-- backend/routers/proveedores_publico.py (autorregistro QR).
ALTER TABLE proveedores
  ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'guarda';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'proveedores_origen_check'
          AND conrelid = 'proveedores'::regclass
    ) THEN
        ALTER TABLE proveedores
            ADD CONSTRAINT proveedores_origen_check
            CHECK (origen IN ('guarda', 'autorregistro'));
    END IF;
END $$;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20260804100000_schema_tablas_huerfanas_drift.sql',
  'Recrea 8 tablas (muelles, configuracion, sustancias, herramientas, conductores_frecuentes, archivos_citas, citas_programadas, muelle_eventos) y 3 columnas huérfanas (proveedores_ordenes.numero_orden_compra, proveedores_ordenes.cita_id, proveedores.origen) + el índice idx_proveedores_ordenes_cita_id, que existían en producción sin CREATE TABLE/ALTER TABLE/CREATE INDEX versionado en ningún script de git. DDL obtenido por introspección de solo lectura contra producción el 2026-09-14. Las 8 tablas + 2 columnas originales fueron investigadas y propuestas por Jorge y aprobadas por Alejandro el 2026-09-14 (condición de gobierno: citas_programadas/archivos_citas son de uso compartido con citas-muelles-cedi-r10, este repo queda como único registro versionado de su esquema sin asumir autoridad exclusiva). El índice idx_proveedores_ordenes_cita_id y proveedores.origen se agregaron el mismo día tras el hallazgo de María corriendo las 46 migraciones contra una base vacía real. Fecha de archivo deliberadamente anterior al 2026-08-05 para satisfacer la dependencia de todas las migraciones ya versionadas que asumen que estos objetos existen.'
)
ON CONFLICT (filename) DO NOTHING;
-- ================================================================
