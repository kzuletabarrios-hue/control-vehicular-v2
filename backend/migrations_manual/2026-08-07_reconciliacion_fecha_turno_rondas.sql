-- ================================================================
-- Reconciliación de fecha_turno en rondas_ciclos / rondas /
-- apoyos_operativos + UNIQUE constraint anti-carrera en
-- rondas_ciclos.
--
-- *** PROPUESTA. NO APLICADA. PENDIENTE DE APROBACIÓN DE KAREN. ***
-- Toca datos de auditoría de seguridad ya guardados en producción
-- (histórico de rondas del recorredor externo). No se ejecuta hasta
-- que Karen lo autorice explícitamente, y se recomienda aplicarla
-- en el mismo despliegue que el fix de código de María (ver nota de
-- riesgo de timing más abajo) -- no antes.
--
-- Diagnóstico (Jorge, 2026-08-07, solo lectura contra Supabase
-- producción, mismas credenciales de backend/.env):
--
-- Causa raíz (confirmada por Alejandro): el turno "noche" va de
-- 18:00 a 06:00 hora Bogotá y cruza medianoche. El código actual
-- (backend/routers/rondas.py, _hoy_bog(), línea 8) usa la fecha
-- calendario del INSTANTE exacto para poner `fecha` en las 3 tablas,
-- en vez de anclarla al inicio real del turno. Regla correcta que
-- usa esta migración para recalcular fecha_turno:
--   - turno = 'dia'   -> fecha calendario del timestamp en Bogotá, tal cual.
--   - turno = 'noche' y hora Bogotá < 06:00 -> día calendario ANTERIOR.
--   - turno = 'noche' y hora Bogotá >= 18:00 (o cualquier otro caso) -> mismo día calendario.
-- Conversión de zona horaria: `timestamptz AT TIME ZONE 'America/Bogota'`
-- (Colombia no tiene horario de verano, offset fijo -05:00).
--
-- Números encontrados (consulta de solo lectura, 2026-08-07):
--   rondas_ciclos: 326 filas totales, rango 2026-06-24..2026-08-07,
--     6 recorredores distintos en la tabla.
--     -> 80 filas con `fecha` != fecha_turno correcta (78 'completa',
--        2 'cancelada'), rango 2026-07-04..2026-08-07, 5 recorredores
--        afectados.
--     -> 44 grupos (recorredor_id, fecha_turno_correcta, turno,
--        numero_ronda) con más de 1 fila = 113 filas involucradas,
--        6 recorredores, rango 2026-07-03..2026-08-06. Es el efecto
--        directo del bug: al agrupar por la fecha_turno CORRECTA,
--        ciclos que hoy viven repartidos en 2 fechas calendario
--        (porque el contador se reinició a medianoche) chocan en el
--        mismo numero_ronda. Excluyendo 'cancelada' (que hoy puede
--        compartir numero_ronda con la siguiente 'completa' por
--        diseño -- numero_ronda = COUNT(completadas)+1 -- y no es
--        síntoma de este bug) quedan igual 36 grupos / 87 filas / 5
--        recorredores de colisión real entre ciclos activos
--        (completa/en_curso/pausada): la mayoría del problema no es
--        el reciclaje de cancelada+completa, es el reinicio por
--        cruce de medianoche.
--     -> 1 ciclo en estado 'en_curso' ahora mismo (id
--        210c3e69-9e80-427a-8627-cb48b934e866, recorredor
--        04750352-4adf-438e-83cd-27a28182aebc, hora_inicio
--        2026-08-06 10:13 UTC = 05:13 Bogotá) -- ronda diurna del
--        06/08 abierta hace más de 24h, aparentemente abandonada.
--        No es objeto de esta migración (no se cierra ni cancela
--        aquí), se deja como nota operativa para Alejandro/soporte.
--   rondas (puntos marcados): 3031 filas totales, rango
--     2026-06-24..2026-08-07.
--     -> 927 filas con `fecha` != fecha_turno correcta calculada
--        desde created_at + turno del ciclo padre, rango
--        2026-06-24..2026-08-07, 6 recorredores. La gran mayoría son
--        marcaciones nocturnas hechas después de medianoche Bogotá
--        (el patrón real de trabajo del turno noche en este dataset).
--     -> 247 filas (30 ciclos, 5 recorredores, rango
--        2026-07-07..2026-08-07) donde `rondas.fecha` YA quedó
--        distinta de `rondas_ciclos.fecha` de su propio ciclo padre:
--        es el "split" real, filas de UN MISMO ciclo con fecha
--        repartida en 2 días calendario porque marcar_punto() (línea
--        701) recalcula _hoy_bog() en cada INSERT en vez de heredar
--        ciclo.fecha.
--   apoyos_operativos: 19 filas totales.
--     -> 0 filas con `fecha` != fecha_turno correcta (vía created_at):
--        hoy no hay apoyos registrados en la ventana medianoche-6am
--        que dispare el bug en esta tabla en particular.
--     -> 0 filas con hora_salida NULL de cualquier antigüedad (ni
--        siquiera hay un apoyo abierto ahora mismo). El síntoma del
--        candado de cierre que no encuentra el apoyo abierto por
--        cruce de fecha SIGUE siendo posible con el código actual,
--        simplemente no se ha materializado todavía en los datos
--        reales -- por eso esta migración igual reconcilia
--        apoyos_operativos.fecha (idempotente, sin efecto hoy ya que
--        son 0 filas, mitiga hacia adelante si se acumulan más datos
--        antes de que se despliegue el fix de código).
--
-- *** RIESGO DE TIMING (leer antes de aplicar) ***
-- Esta migración NO cambia backend/routers/rondas.py (eso lo hace
-- María en paralelo). Si se aplica el UNIQUE constraint del Paso 5
-- ANTES de que el código deje de usar _hoy_bog() para fecha/turno,
-- el bug de cruce de medianoche seguirá generando el mismo patrón de
-- reinicio -- y con el constraint ya puesto, el próximo INSERT que
-- choque con una fila histórica ya reconciliada (mismo recorredor +
-- fecha_turno + turno + numero_ronda) fallará con un error 500 en
-- vez de crear el duplicado silencioso de hoy. Es preferible (fail
-- loud > corrupción silenciosa) pero puede bloquear a un recorredor
-- a mitad de un turno nocturno real. Recomendación: aplicar esta
-- migración en el mismo despliegue que el fix de rondas.py, no antes.
--
-- Idempotente: los 3 UPDATE de reconciliación de fecha solo tocan
-- filas donde `fecha` difiere del valor recalculado (no-op en una
-- segunda corrida); el UPDATE de renumeración solo toca filas donde
-- numero_ronda difiere del recalculado; el UNIQUE constraint se
-- agrega dentro de un DO $$ IF NOT EXISTS $$ contra pg_constraint
-- (mismo patrón que 2026-08-07_proveedores_estado_ingresado_wps.sql).
-- Fecha: 2026-08-07
-- ================================================================


-- ── PASO 1: reconciliar rondas_ciclos.fecha a la fecha_turno real ──
-- Ancla la fecha al INICIO del turno (hora_inicio), no al instante
-- de cada evento. Ver regla completa en el encabezado.
UPDATE rondas_ciclos rc
SET fecha = calc.fecha_turno_correcta
FROM (
    SELECT
        id,
        CASE
            WHEN turno = 'noche'
                 AND (hora_inicio AT TIME ZONE 'America/Bogota')::time < TIME '06:00'
            THEN ((hora_inicio AT TIME ZONE 'America/Bogota')::date - 1)
            ELSE (hora_inicio AT TIME ZONE 'America/Bogota')::date
        END AS fecha_turno_correcta
    FROM rondas_ciclos
) calc
WHERE calc.id = rc.id
  AND rc.fecha IS DISTINCT FROM calc.fecha_turno_correcta;


-- ── PASO 2: rondas.fecha hereda de su ciclo padre (ya corregido) ──
-- Corrige de raíz el "split" (punto 4b del diagnóstico): en vez de
-- recalcular la fecha de cada marcación individual desde su propio
-- created_at (lo que puede volver a partir un ciclo si dos puntos se
-- marcan a lados distintos de la medianoche), TODAS las marcaciones
-- de un mismo ciclo comparten SIEMPRE la fecha del ciclo. Es el mismo
-- criterio que ya usa _analizar_ciclo()/ciclo_recorrido() para
-- duración/distancia (usan created_at completo, no fecha+hora_marcacion
-- por separado, precisamente para no romperse en el cruce de
-- medianoche) -- aquí se aplica el mismo principio a la columna fecha.
-- Si backend/routers/rondas.py dejara de recalcular _hoy_bog() en
-- marcar_punto() y en su lugar heredara ciclo.fecha directamente (fix
-- de María), este UPDATE queda de todas formas correcto y sin efecto
-- en filas nuevas.
--
-- Nota: hay 4 filas de `rondas` con ciclo_id NULL (2026-06-22, previas
-- a la existencia de la columna/tabla de ciclos -- dato legacy fuera
-- del rango de fechas afectado por este bug). El JOIN de abajo no las
-- toca (no hay ciclo del que heredar), quedan tal cual.
UPDATE rondas r
SET fecha = rc.fecha
FROM rondas_ciclos rc
WHERE rc.id = r.ciclo_id
  AND r.fecha IS DISTINCT FROM rc.fecha;


-- ── PASO 3: reconciliar apoyos_operativos.fecha ─────────────────
-- apoyos_operativos no tiene columna `turno` propia. La tabla no
-- necesita distinguir turno para aplicar la regla: para hora Bogotá
-- >= 06:00 (turno día completo + primera mitad del turno noche del
-- MISMO día calendario) la fecha_turno es el día tal cual; solo la
-- franja 00:00-05:59 Bogotá (segunda mitad del turno noche, después
-- de medianoche) se ancla al día calendario ANTERIOR. Se usa
-- created_at por instrucción explícita (aunque hora_llegada --
-- también NOT NULL, ver 0 filas mal reportadas en el diagnóstico --
-- es en la práctica el mismo instante salvo latencia de red mínima).
UPDATE apoyos_operativos ap
SET fecha = calc.fecha_turno_correcta
FROM (
    SELECT
        id,
        CASE
            WHEN (created_at AT TIME ZONE 'America/Bogota')::time < TIME '06:00'
            THEN ((created_at AT TIME ZONE 'America/Bogota')::date - 1)
            ELSE (created_at AT TIME ZONE 'America/Bogota')::date
        END AS fecha_turno_correcta
    FROM apoyos_operativos
) calc
WHERE calc.id = ap.id
  AND ap.fecha IS DISTINCT FROM calc.fecha_turno_correcta;


-- ── PASO 4: renumerar numero_ronda duplicado tras la reconciliación ──
-- Criterio: dentro de cada (recorredor_id, fecha [ya corregida],
-- turno), renumerar TODOS los ciclos (cualquier estado: completa,
-- cancelada, en_curso, pausada) por orden cronológico de hora_inicio,
-- empezando en 1. Se incluye 'cancelada' en la numeración (no se
-- excluye) porque el UNIQUE constraint del Paso 5 se aplica sobre
-- TODAS las filas sin importar estado -- es la misma tabla donde
-- Alejandro identificó la carrera de dos INSERT casi simultáneos, y
-- el candado que la resuelve (constraint + reintento en la app) tiene
-- que ser consistente con TODOS los estados posibles, no solo
-- 'completa'.
--
-- *** AVISO DE CAMBIO SEMÁNTICO: *** hoy numero_ronda de una fila
-- 'completa' representa su posición entre SOLO las completadas de ese
-- turno (así lo calcula ciclo_iniciar(), línea 514-519: COUNT(*)
-- WHERE estado='completa'). Después de este renumeramiento,
-- numero_ronda pasa a representar la posición cronológica entre TODOS
-- los intentos (incluidos los cancelados) de ese turno -- si hubo una
-- ronda cancelada entre la 1 y la 3, la que antes era "ronda
-- completada #2" puede pasar a numerarse como 3. Es un cambio de
-- significado en datos históricos de auditoría, no solo un
-- renumerado cosmético: se deja explícito para que Karen lo apruebe
-- con ese alcance claro, no solo como "arreglo de duplicados".
UPDATE rondas_ciclos rc
SET numero_ronda = calc.numero_correcto
FROM (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY recorredor_id, fecha, turno
            ORDER BY hora_inicio ASC, id ASC
        ) AS numero_correcto
    FROM rondas_ciclos
) calc
WHERE calc.id = rc.id
  AND rc.numero_ronda IS DISTINCT FROM calc.numero_correcto;


-- ── Verificación de seguridad antes del constraint ──────────────
-- Si por cualquier motivo (ej. hora_inicio NULL en alguna fila
-- corrupta) quedara algún duplicado tras el Paso 4, abortar aquí con
-- un mensaje claro en vez de dejar que el ADD CONSTRAINT de más abajo
-- falle con un error genérico de Postgres.
DO $$
DECLARE
    duplicados INT;
BEGIN
    SELECT COUNT(*) INTO duplicados
    FROM (
        SELECT recorredor_id, fecha, turno, numero_ronda
        FROM rondas_ciclos
        GROUP BY recorredor_id, fecha, turno, numero_ronda
        HAVING COUNT(*) > 1
    ) dup;

    IF duplicados > 0 THEN
        RAISE EXCEPTION
            'Quedan % grupos (recorredor_id, fecha, turno, numero_ronda) duplicados después del renumerado del Paso 4. No se agrega el UNIQUE constraint. Revisar manualmente antes de reintentar.',
            duplicados;
    END IF;
END $$;


-- ── PASO 5: UNIQUE constraint anti-carrera ──────────────────────
-- Previene el problema de carrera identificado por Alejandro: dos
-- INSERT casi simultáneos en /ciclo/iniciar leyendo el mismo COUNT(*)
-- antes de que ninguno haga commit, y terminando con el mismo
-- numero_ronda. Con este constraint, el segundo INSERT falla con un
-- error de violación de unicidad en vez de crear el duplicado; la
-- aplicación (fuera de esta migración, código de María) debe atrapar
-- ese error y reintentar con el siguiente número.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'rondas_ciclos_recorredor_fecha_turno_numero_key'
          AND conrelid = 'rondas_ciclos'::regclass
    ) THEN
        ALTER TABLE rondas_ciclos
            ADD CONSTRAINT rondas_ciclos_recorredor_fecha_turno_numero_key
            UNIQUE (recorredor_id, fecha, turno, numero_ronda);
    END IF;
END $$;


INSERT INTO schema_migrations (filename)
VALUES ('2026-08-07_reconciliacion_fecha_turno_rondas.sql')
ON CONFLICT (filename) DO NOTHING;


-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- Confirmar que ya no quedan mismatches de fecha_turno:
--
-- SELECT COUNT(*) FROM rondas_ciclos rc WHERE rc.fecha IS DISTINCT FROM (
--   CASE WHEN rc.turno = 'noche'
--          AND (rc.hora_inicio AT TIME ZONE 'America/Bogota')::time < TIME '06:00'
--        THEN ((rc.hora_inicio AT TIME ZONE 'America/Bogota')::date - 1)
--        ELSE (rc.hora_inicio AT TIME ZONE 'America/Bogota')::date END
-- );
--
-- SELECT COUNT(*) FROM rondas r JOIN rondas_ciclos rc ON rc.id = r.ciclo_id
-- WHERE r.fecha IS DISTINCT FROM rc.fecha;
--
-- SELECT recorredor_id, fecha, turno, numero_ronda, COUNT(*)
-- FROM rondas_ciclos GROUP BY 1,2,3,4 HAVING COUNT(*) > 1;
--
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
-- WHERE conrelid = 'rondas_ciclos'::regclass
--   AND conname = 'rondas_ciclos_recorredor_fecha_turno_numero_key';
