-- ================================================================
-- Control de Acceso · Anulación (soft-delete) con auditoría
-- Reemplaza el DELETE físico para guarda_vehicular/guarda_bodega
-- por una ANULACIÓN trazable: motivo obligatorio, ventana de
-- tiempo y registro en audit_log.
-- Sigue el patrón de permisos incrementales de
-- migration_visita_vehicular.sql (UPDATE roles ... permisos || ...)
-- pero con merge seguro de arrays (ver advertencia más abajo).
-- Fecha: 2026-07-22 (actualizado el mismo día: control de propiedad
-- del registro + permiso "anular_todo" para admin/supervisor, a
-- pedido de Alejandro tras revisión de seguridad).
-- Ejecutar DESPUÉS de schema.sql y auth_schema.sql
-- Idempotente: se puede correr más de una vez sin efectos secundarios.
-- ================================================================


-- ── 1. COLUMNAS DE ANULACIÓN EN control_acceso ────────────────────
-- ADD COLUMN ... DEFAULT en PG 11+ no reescribe la tabla (solo agrega
-- metadata), así que esto es seguro sobre una tabla con datos.
ALTER TABLE control_acceso
    ADD COLUMN IF NOT EXISTS anulado         BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS anulado_por     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS anulado_motivo  TEXT,
    ADD COLUMN IF NOT EXISTS anulado_at      TIMESTAMPTZ;


-- ── 2. INTEGRIDAD: motivo y auditoría obligatorios si está anulado ─
-- Todas las filas existentes tienen anulado = FALSE (recién agregado),
-- por lo que el CHECK se satisface trivialmente al validarse contra
-- los datos actuales; no hay riesgo de romper filas existentes.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_ca_anulacion_completa'
          AND conrelid = 'control_acceso'::regclass
    ) THEN
        ALTER TABLE control_acceso
            ADD CONSTRAINT chk_ca_anulacion_completa
            CHECK (
                (anulado = FALSE AND anulado_por IS NULL AND anulado_motivo IS NULL AND anulado_at IS NULL)
                OR
                (anulado = TRUE  AND anulado_por IS NOT NULL AND anulado_motivo IS NOT NULL AND anulado_at IS NOT NULL)
            );
    END IF;
END $$;


-- ── 3. INTEGRIDAD: no permitir "des-anular" (protege el rastro) ───
-- Si se necesita revertir un error de anulación, se crea un registro
-- nuevo; no se reabre uno anulado (mismo espíritu que un log inmutable).
CREATE OR REPLACE FUNCTION fn_ca_bloquear_reversion_anulacion()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.anulado = TRUE AND NEW.anulado = FALSE THEN
        RAISE EXCEPTION 'No se puede revertir la anulación del registro % de control_acceso', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ca_bloquear_reversion_anulacion ON control_acceso;
CREATE TRIGGER trg_ca_bloquear_reversion_anulacion
    BEFORE UPDATE ON control_acceso
    FOR EACH ROW
    WHEN (OLD.anulado IS DISTINCT FROM NEW.anulado)
    EXECUTE FUNCTION fn_ca_bloquear_reversion_anulacion();


-- ── 4. ÍNDICES ──────────────────────────────────────────────────
-- listar() en control_acceso.py hace un UNION ALL sobre una CTE
-- "base" filtrada por where_sql, y ordena/pagina la rama de
-- "cerrados" (hora_salida IS NOT NULL) por fecha DESC, hora_ingreso DESC.
-- Cuando María agregue "AND ca.anulado = FALSE" a where_sql (ver
-- advertencia #2 más abajo), este índice parcial cubre exactamente
-- ese filtro + ese ORDER BY, evitando seq scan + sort en la tabla
-- completa a medida que crece el histórico.
CREATE INDEX IF NOT EXISTS idx_ca_activos_fecha
    ON control_acceso (fecha DESC, hora_ingreso DESC)
    WHERE anulado = FALSE;

-- Soporte para una futura pantalla de "historial de anulaciones"
-- (admin/supervisor). Los anulados son una minoría de las filas,
-- así que el índice parcial es liviano.
CREATE INDEX IF NOT EXISTS idx_ca_anulados_fecha
    ON control_acceso (anulado_at DESC)
    WHERE anulado = TRUE;

-- Índice para reportes "qué anuló cada usuario".
CREATE INDEX IF NOT EXISTS idx_ca_anulado_por
    ON control_acceso (anulado_por)
    WHERE anulado = TRUE;


-- ── 5. FUNCIÓN AUXILIAR: anular con validación + auditoría atómica ─
-- Encapsula la regla de negocio completa (permiso, motivo obligatorio,
-- ventana de tiempo, no doble anulación) y cierra el hueco de
-- auditoría de control_acceso.py (que hoy no llama a ningún equivalente
-- de _audit(), a diferencia de flota.py) insertando en audit_log
-- desde la propia función, así que la auditoría queda garantizada
-- aunque el endpoint FastAPI no la invoque explícitamente.
--
-- p_ventana_horas: la ventana de tiempo la pidió Alejandro pero no
-- llegó un valor de negocio definido; 24h es un placeholder razonable
-- (cubre un turno + margen). Confirmado por Karen (usuario final):
-- se queda en 24h, no cambia.
--
-- PROPIEDAD DEL REGISTRO (agregado tras revisión de Alejandro):
-- "anular" por sí solo ya NO alcanza para anular cualquier registro.
-- Además de "anular", el solicitante debe ser el creado_por del
-- registro, salvo que tenga el permiso "anular_todo" en control_acceso
-- (reservado a admin/supervisor, ver sección 6b). Esto aplica igual
-- a guarda_vehicular, guarda_bodega y guarda_peatonal: cada guarda
-- anula únicamente lo que él mismo creó.
CREATE OR REPLACE FUNCTION fn_control_acceso_anular(
    p_id            UUID,
    p_usuario_id    UUID,
    p_motivo        TEXT,
    p_ventana_horas INT DEFAULT 24
) RETURNS control_acceso AS $$
DECLARE
    v_antes   control_acceso;
    v_despues control_acceso;
    v_email   TEXT;
BEGIN
    IF p_motivo IS NULL OR btrim(p_motivo) = '' THEN
        RAISE EXCEPTION 'El motivo de anulación es obligatorio';
    END IF;

    IF NOT tiene_permiso(p_usuario_id, 'control_acceso', 'anular') THEN
        RAISE EXCEPTION 'El usuario % no tiene el permiso "anular" en control_acceso', p_usuario_id;
    END IF;

    SELECT * INTO v_antes FROM control_acceso WHERE id = p_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Registro % no encontrado en control_acceso', p_id;
    END IF;

    IF v_antes.anulado THEN
        RAISE EXCEPTION 'El registro % ya está anulado', p_id;
    END IF;

    -- Propiedad del registro: sin "anular_todo", solo el creador anula.
    -- IS DISTINCT FROM trata NULL correctamente: un registro con
    -- creado_por NULL (dato legado insertado antes de que existiera
    -- esta columna, o cargado fuera de la app) queda protegido igual
    -- que uno de otro usuario -- nadie sin "anular_todo" puede tocarlo.
    -- Esto es intencional (más seguro por defecto) pero puede sorprender
    -- a un guarda que intente anular un registro viejo suyo sin
    -- creado_por poblado; si eso ocurre en producción es una decisión
    -- de negocio de Alejandro/Karen, no algo que esta función deba
    -- adivinar.
    IF NOT tiene_permiso(p_usuario_id, 'control_acceso', 'anular_todo')
       AND v_antes.creado_por IS DISTINCT FROM p_usuario_id THEN
        RAISE EXCEPTION 'Solo puede anular registros que usted mismo creó';
    END IF;

    IF v_antes.created_at < NOW() - (p_ventana_horas::text || ' hours')::interval THEN
        RAISE EXCEPTION 'Fuera de la ventana de % horas permitida para anular (creado el %)',
            p_ventana_horas, v_antes.created_at;
    END IF;

    UPDATE control_acceso
    SET anulado        = TRUE,
        anulado_por    = p_usuario_id,
        anulado_motivo = p_motivo,
        anulado_at     = NOW(),
        updated_at     = NOW()
    WHERE id = p_id
    RETURNING * INTO v_despues;

    SELECT email INTO v_email FROM usuarios WHERE id = p_usuario_id;

    INSERT INTO audit_log (usuario_id, usuario_email, accion, tabla, registro_id, datos_antes, datos_despues)
    VALUES (p_usuario_id, v_email, 'ANULAR', 'control_acceso', p_id::text, to_jsonb(v_antes), to_jsonb(v_despues));

    RETURN v_despues;
END;
$$ LANGUAGE plpgsql;


-- ── 6. PERMISOS: nuevo permiso "anular" en el módulo control_acceso ─
-- ADVERTENCIA IMPORTANTE (ver sección de riesgos en la respuesta):
-- NO se usa el patrón `permisos || '{"control_acceso":[...]}'::jsonb`
-- de migration_visita_vehicular.sql / migration_guarda_bodega_proveedores.sql
-- porque ese operador REEMPLAZA por completo el valor de la clave
-- "control_acceso" en el JSON. Esos scripts eran seguros porque
-- introducían una clave NUEVA; acá "control_acceso" YA existe con
-- arrays no vacíos en admin/supervisor/operador (ver auth_schema.sql),
-- así que un `||` directo habría BORRADO "read","write","delete","export"
-- y dejado solo ["anular"]. Se usa jsonb_set + merge de arrays para
-- agregar "anular" sin tocar los permisos existentes.
--
-- Alcance: se aplica a todo rol que YA tenga "write" en control_acceso
-- (admin, supervisor, operador, y cualquier guarda_* que ya opere en
-- este módulo en la base real). guarda_vehicular está confirmado por
-- el hallazgo de Alejandro. guarda_bodega y guarda_peatonal NO tienen
-- su alta de rol ni sus permisos base versionados en database/ (los
-- roles guarda_* se crean directo en la BD, fuera de git — ver nota
-- final), así que en vez de adivinar sus nombres se usa esta condición:
-- solo toca roles con "write" real sobre control_acceso, lo cual
-- automáticamente incluye a guarda_bodega/guarda_peatonal si y solo
-- si de verdad operan hoy en este módulo, y no crea la clave
-- "control_acceso" en roles que no la tenían (evitaría exponerles un
-- módulo que no usan).
UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{control_acceso}',
    (
        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
        FROM jsonb_array_elements_text(
            (permisos -> 'control_acceso') || '["anular"]'::jsonb
        ) AS elem
    )
)
WHERE permisos -> 'control_acceso' ? 'write';


-- ── 6b. PERMISOS: "anular_todo" para admin y supervisor ────────────
-- Decisión de Alejandro: admin y supervisor deben poder corregir/anular
-- registros ajenos (no solo los propios), por eso reciben un permiso
-- aparte -- "anular_todo" -- en vez de aflojar la regla general de
-- propiedad para todos. Mismo merge seguro por array que en el punto 6
-- (jsonb_set + jsonb_array_elements_text, NUNCA `||` directo: ese
-- operador reemplaza el array completo de "control_acceso" y borraría
-- "read"/"write"/"delete"/"export"/"anular" ya presentes en admin y
-- supervisor).
--
-- Alcance: nombre IN ('admin','supervisor'), Y ADEMÁS se exige que el
-- rol ya tenga "write" en control_acceso (verificado arriba: admin y
-- supervisor lo tienen ambos en auth_schema.sql). Ese segundo filtro
-- es puramente defensivo -- evita crear la clave "control_acceso" con
-- un array vacío si algún día ese seed cambia y alguno de los dos roles
-- deja de tener el módulo, en vez de otorgar un permiso "fantasma"
-- sobre un módulo al que ya no tendrían acceso base.
UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{control_acceso}',
    (
        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
        FROM jsonb_array_elements_text(
            (permisos -> 'control_acceso') || '["anular_todo"]'::jsonb
        ) AS elem
    )
)
WHERE nombre IN ('admin', 'supervisor')
  AND permisos -> 'control_acceso' ? 'write';


-- ── 7. VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- Confirmar qué roles quedaron con "anular" / "anular_todo" antes de
-- dar por cerrada la migración en el ambiente real. Presta atención
-- especial a guarda_bodega y guarda_peatonal: sus roles NO están
-- versionados en database/ (se crean directo en la BD, fuera de git),
-- así que esta consulta es la única forma real de confirmar si hoy
-- tienen "write" en control_acceso -- y por lo tanto si recibieron
-- "anular" -- o no.
-- SELECT nombre, permisos -> 'control_acceso' AS permisos_control_acceso
-- FROM roles
-- ORDER BY nombre;
