-- ================================================================
-- Agrega columnas reales para "número de muelle liberado + hora de
-- liberación" a `proveedores`, para que el paso "Salida de muelle"
-- de la línea de tiempo del frontend (DetalleTiempos, frontend/index.html
-- ~línea 790: hhmmT(r.hora_muelle_liberado) / r.muelle_numero) deje de
-- depender de un JOIN contra muelle_eventos/muelles, tablas vacías y sin
-- uso operativo real (ver comentario de Alejandro, 2026-08-07, en
-- backend/routers/muelles.py líneas 12-18).
--
-- Contexto: el endpoint PUT /proveedores/{id}/liberar-muelle (commit
-- 1506e3a) hoy solo vacía proveedores.muelle_descargue. María detectó que
-- el frontend lee dos campos que _attach_muelle() (proveedores.py líneas
-- 130-160) construye al vuelo desde ese JOIN -- y que como muelle_eventos
-- está vacía, ese JOIN nunca puede devolver nada.
--
-- Estado real verificado en producción (Supabase) el 2026-08-08 por Jorge,
-- lectura directa ANTES de escribir este script (no se asume nada):
--
--   information_schema.columns: proveedores NO tiene columnas
--     `muelle_numero` ni `hora_muelle_liberado` (0 filas de resultado).
--   muelle_eventos: 0 filas.
--   muelles: 4 filas (catálogo cargado, pero SIN ningún evento asociado
--     -- el INNER JOIN de _attach_muelle contra muelle_eventos e siempre
--     devuelve conjunto vacío sin importar cuántas filas tenga `muelles`).
--   proveedores.muelle_descargue: TEXT, nullable (texto libre, sin CHECK)
--     -- misma naturaleza que la nueva `muelle_numero` de abajo.
--   Patrón de las columnas hora_* ya existentes en `proveedores`
--     (hora_ingreso, hora_wps, hora_ingreso_confirmado, hora_salida):
--     TODAS son TIME WITHOUT TIME ZONE, pobladas con
--     datetime.now(_BOG).strftime("%H:%M:%S") (zona Bogotá ya resuelta en
--     Python antes del INSERT/UPDATE, igual que hace
--     marcar_ingreso_wps/confirmar_autorregistro). `hora_muelle_liberado`
--     sigue exactamente ese mismo patrón (NO timestamptz): el frontend ya
--     formatea todos los pasos de la línea de tiempo con
--     hhmmT = t => String(t).slice(0,5), que espera un string "HH:MM:SS",
--     no un timestamp con fecha/zona -- usar timestamptz aquí rompería esa
--     consistencia y forzaría un formateo especial solo para este campo.
--
-- Confirmado (lectura de código, proveedores.py líneas 154-159): dentro de
-- _attach_muelle(), el for final SIEMPRE reasigna
--   item["muelle_numero"] = info.muelle_numero if info else None
--   item["hora_muelle_liberado"] = info.hora_muelle_liberado if info else None
-- sin condicionar a si esas claves ya traían un valor real desde
-- `SELECT p.*` / `SELECT * FROM proveedores` -- es decir, sobreescribe
-- incondicionalmente. Como el JOIN siempre da `info = None` (muelle_eventos
-- vacía), el resultado hoy sería SIEMPRE None para ambos campos aunque esta
-- migración los llene en la tabla. Ver instrucciones para María abajo --
-- esta migración por sí sola NO resuelve el problema, es la mitad de
-- esquema; falta el ajuste de código.
--
-- Sin backfill de datos: el evento "liberar muelle" no existía antes de
-- hoy (endpoint nuevo, commit 1506e3a), así que no hay historial que
-- reconciliar. Ambas columnas nacen NULL para todas las filas existentes
-- y solo las llenará, de ahora en adelante, el propio endpoint
-- liberar-muelle en cada liberación nueva.
--
-- Riesgo: BAJO. Son 2 columnas nuevas, nullable, sin default, sin CHECK,
-- sin FK, sin tocar ninguna columna/constraint existente -- no puede
-- romper ningún INSERT/UPDATE/SELECT que ya corre en producción (los
-- `SELECT *`/`SELECT p.*` de proveedores.py simplemente traerán 2 columnas
-- adicionales en el dict). Idempotente (ADD COLUMN IF NOT EXISTS): segura
-- de re-ejecutar. No requiere downtime ni bloqueo de tabla relevante en
-- Postgres moderno (ADD COLUMN nullable sin default es solo catálogo).
-- Aun así, queda pendiente de aplicar hasta que Karen confirme -- según
-- las reglas del equipo, cualquier cambio de esquema en producción se
-- reporta explícitamente antes de ejecutarse, aunque el riesgo sea bajo.
--
-- Fecha: 2026-08-08
-- ================================================================

ALTER TABLE proveedores
  ADD COLUMN IF NOT EXISTS muelle_numero        TEXT,
  ADD COLUMN IF NOT EXISTS hora_muelle_liberado  TIME WITHOUT TIME ZONE;

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-08_proveedores_muelle_liberado_columns.sql')
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'proveedores' AND column_name IN ('muelle_numero','hora_muelle_liberado');
