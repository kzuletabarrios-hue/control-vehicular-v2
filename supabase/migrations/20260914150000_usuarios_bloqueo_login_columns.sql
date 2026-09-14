-- ================================================================
-- Esquema mínimo para mitigar fuerza bruta en POST /login: contador
-- de intentos fallidos + bloqueo temporal por usuario.
--
-- Autor: Jorge Peña (Arquitecto de BD), a pedido de Alejandro/María,
-- 2026-09-14. Prioridad alta por decisión de Alejandro, dado el
-- hallazgo de acceso no autorizado ya cerrado hoy (permiso "asignar"
-- en guarda_vehicular).
--
-- *** PROPUESTA. NO APLICADA A PRODUCCIÓN. *** Solo el archivo de
-- migración -- pendiente de aprobación de Karen antes de ejecutarse,
-- igual que el resto de cambios de esquema de esta sesión. María
-- implementa la lógica en backend/routers/auth.py sobre este esquema
-- después de que esto se apruebe (o incluso antes, contra su entorno
-- local, corriendo esta migración ahí).
--
-- ── ESTADO REAL VERIFICADO (Jorge, solo lectura contra producción,
--    2026-09-14, ANTES de diseñar esto -- no se asume nada) ─────────
-- `usuarios`: id, nombre, email (UNIQUE), password_hash, rol_id,
--   activo, ultimo_acceso, creado_por, created_at, updated_at. Sin
--   ninguna columna de intentos/bloqueo hoy.
-- `sesiones`: id, usuario_id, refresh_token (UNIQUE), ip_address,
--   user_agent, expires_at, revocada, created_at -- ya guarda
--   ip_address/user_agent, pero solo se inserta en LOGIN EXITOSO
--   (backend/routers/auth.py línea 172-185); no sirve para trackear
--   intentos fallidos porque un intento fallido hoy nunca llega a esa
--   sentencia INSERT (el código corta antes con 401, línea 158-159).
--
-- ── DECISIÓN DE DISEÑO: columnas en `usuarios`, NO tabla dedicada ──
-- El endpoint /login ya hace `SELECT ... FROM usuarios WHERE email =
-- :email` como primer paso (backend/routers/auth.py línea 148-156) --
-- agregar 2 columnas a esa misma fila da el estado de bloqueo en el
-- mismo SELECT que ya se ejecuta, sin JOIN ni segunda consulta, y sin
-- tabla nueva que mantener. Una tabla dedicada (histórico de intentos)
-- tendría sentido si se necesitara auditoría forense de CADA intento
-- (fecha, IP, user agent) o rate-limiting por IP independiente del
-- email probado (para mitigar además el "email spraying" contra
-- cuentas que no existen) -- eso queda deliberadamente FUERA de este
-- cambio mínimo:
--   - Si más adelante se quiere ese histórico, `audit_log` (ya existe,
--     usuario_id NULLABLE + usuario_email TEXT + accion + ip_address +
--     datos_despues JSONB) ya tiene las columnas necesarias para
--     registrar un intento fallido con accion='LOGIN_FALLIDO' SIN
--     necesidad de otra tabla ni otra migración -- es una decisión de
--     código de María, no de esquema, si decide usarla.
--   - Rate-limiting por IP (para emails inexistentes, que nunca tocan
--     una fila de `usuarios` y por lo tanto nunca activan este
--     bloqueo) es una preocupación de capa de aplicación/infraestructura
--     (middleware, API gateway), no de modelo de datos -- fuera de mi
--     alcance como Arquitecto de BD, se lo dejo señalado a
--     Alejandro/María si lo quieren para una fase posterior.
--
-- ── DISEÑO DE LAS 2 COLUMNAS ──────────────────────────────────────
--   intentos_fallidos   INTEGER NOT NULL DEFAULT 0, CHECK (>= 0)
--   bloqueado_hasta      TIMESTAMPTZ, NULLABLE (NULL = no bloqueado)
--
-- Contrato esperado para la lógica de María en auth.py (no se
-- implementa aquí, es código, no esquema):
--   1) Antes de verificar password: si bloqueado_hasta IS NOT NULL Y
--      bloqueado_hasta > NOW(), rechazar de inmediato (sugerido: 423
--      Locked o 429 Too Many Requests, con Retry-After) SIN llamar a
--      verify_password() -- evita gastar ciclos de bcrypt en una
--      cuenta ya bloqueada. Si bloqueado_hasta ya pasó, tratar como
--      no-bloqueada (el bloqueo expira solo, no necesita un job de
--      limpieza).
--   2) Login exitoso: UPDATE usuarios SET intentos_fallidos = 0,
--      bloqueado_hasta = NULL, ultimo_acceso = NOW() WHERE id = :id
--      (se puede fusionar con el UPDATE ultimo_acceso que ya existe en
--      la línea 186-189 de auth.py, un solo UPDATE en vez de dos).
--   3) Login fallido (password incorrecta, usuario SÍ existe):
--      incrementar intentos_fallidos; si el nuevo valor alcanza el
--      umbral N, setear bloqueado_hasta = NOW() + duración. Sugerido
--      (criterio de Jorge, ajustable por María/Alejandro sin tocar
--      esquema -- son constantes de aplicación, no columnas):
--        N = 5 intentos
--        duración del bloqueo = 15 minutos
--      Ambos valores caben en una sola sentencia UPDATE con CASE, sin
--      necesidad de leer-modificar-escribir en dos pasos:
--        UPDATE usuarios
--        SET intentos_fallidos = intentos_fallidos + 1,
--            bloqueado_hasta = CASE
--              WHEN intentos_fallidos + 1 >= 5
--                THEN NOW() + INTERVAL '15 minutes'
--              ELSE bloqueado_hasta
--            END
--        WHERE id = :id;
--   4) Email que NO existe en `usuarios`: no hay fila que tocar -- se
--      sigue respondiendo el mismo 401 genérico "Credenciales
--      incorrectas" que ya usa el código hoy (línea 158-159), sin
--      revelar si el email existe o no. Este esquema no protege contra
--      un atacante probando muchos emails distintos que no existen
--      (ver nota de rate-limiting por IP arriba) -- protege la cuenta
--      real contra fuerza bruta de contraseña.
--
-- ── POR QUÉ NO SE AGREGA UN ÍNDICE ────────────────────────────────
-- El login ya busca por `email` (UNIQUE + índice existente,
-- usuarios_email_key / idx_usuarios_email) -- `intentos_fallidos` y
-- `bloqueado_hasta` se leen siempre como parte de esa misma fila, no
-- se buscan por su valor en ningún flujo previsto. Un índice aquí
-- sería costo de escritura puro (se actualiza en cada login) sin
-- beneficio de lectura real -- mismo criterio que ya usó el equipo en
-- 2026-08-25_proveedores_tiempo_autorregistro_column.sql.
--
-- Riesgo: BAJO. 2 columnas nuevas en una tabla con ~10-20 filas reales
-- (usuarios del sistema, no datos operativos de alto volumen) -- ADD
-- COLUMN con DEFAULT constante en Postgres moderno no reescribe la
-- tabla de forma bloqueante. No cambia el comportamiento de ningún
-- SELECT/INSERT/UPDATE existente hasta que María conecte la lógica en
-- auth.py -- mientras tanto, `intentos_fallidos` nace en 0 y
-- `bloqueado_hasta` en NULL para todos los usuarios reales, sin
-- ningún efecto (nadie queda bloqueado por aplicar esta migración).
--
-- Idempotente: ADD COLUMN IF NOT EXISTS; el CHECK se agrega solo si no
-- existe (pg_constraint).
-- ================================================================

ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS intentos_fallidos INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS bloqueado_hasta    TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'usuarios_intentos_fallidos_check'
          AND conrelid = 'usuarios'::regclass
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT usuarios_intentos_fallidos_check
            CHECK (intentos_fallidos >= 0);
    END IF;
END $$;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20260914150000_usuarios_bloqueo_login_columns.sql',
  'Agrega usuarios.intentos_fallidos (INTEGER NOT NULL DEFAULT 0, CHECK >= 0) y usuarios.bloqueado_hasta (TIMESTAMPTZ nullable) para mitigar fuerza bruta en POST /login -- prioridad de Alejandro tras el hallazgo de acceso no autorizado de hoy. PROPUESTA -- no aplicada a producción, pendiente de aprobación de Karen. Contrato de uso (umbral sugerido 5 intentos / 15 min de bloqueo, ajustable en código sin tocar esquema) documentado en el encabezado de este archivo para que María implemente la lógica en backend/routers/auth.py. No se crea tabla dedicada de histórico -- audit_log ya tiene las columnas necesarias si se decide agregar ese registro más adelante, y rate-limiting por IP queda fuera de alcance de un cambio de esquema (capa de aplicación/infraestructura).'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'usuarios' AND column_name IN ('intentos_fallidos','bloqueado_hasta');
--
-- SELECT count(*) AS total,
--        count(*) FILTER (WHERE intentos_fallidos <> 0) AS con_intentos,
--        count(*) FILTER (WHERE bloqueado_hasta IS NOT NULL) AS bloqueados
-- FROM usuarios;  -- ambos deben dar 0 justo después de aplicar
-- ================================================================
