-- ================================================================
-- control_acceso.cedula: quitar la FK a bd_control_acceso(cedula).
--
-- Problema: en producción la FK control_acceso_cedula_fkey
-- (ON DELETE SET NULL) hacía que el backend borrara la cédula
-- (cedula = None) de toda persona que no estuviera en el maestro
-- bd_control_acceso. Hay 154 ingresos sin cédula (9 en los últimos
-- 14 días).
--
-- Decisión de negocio (usuaria): la persona se registra igual y su
-- cédula se guarda aunque no esté en el maestro.
--
-- Diseño:
--  - Se elimina la FK; la columna sigue siendo BIGINT NULL. No se
--    crean personas automáticamente en el maestro:
--    bd_control_acceso.estado es ACTIVO/INACTIVO (INACTIVO = baja
--    lógica desde bd_maestros.py DELETE y carga_masiva.py); un alta
--    automática marcaría como "autorizada" a alguien que nadie
--    validó y ensuciaría el catálogo.
--  - Una cédula fuera del maestro llega al listado y al export con
--    estado_bd NULL (LEFT JOIN existente) -> la UI puede marcarla
--    "no verificada". No se cambia ninguna query.
--  - Índice: idx_ca_cedula ON control_acceso(cedula) ya existe desde
--    20260601101420_schema_base.sql y cubre el LEFT JOIN. Aquí solo
--    se asegura con IF NOT EXISTS (no-op si ya está).
--  - Pérdida de integridad aceptada: ya no hay garantía referencial
--    cédula -> maestro. Ya no hay ON DELETE SET NULL, así que borrar
--    en el maestro (hoy solo baja lógica) no tocará los ingresos.
--
-- Datos: los 154 ingresos que ya quedaron con cedula NULL NO se
-- pueden recuperar con esta migración (el valor original se perdió).
-- Solo aplica hacia adelante, tras desplegar también el cambio en
-- backend/routers/control_acceso.py (quitar el cedula = None).
--
-- Dependencias revisadas (grep): ninguna vista ni función depende
-- de la FK (fn_control_acceso_anular, triggers de control_acceso,
-- dashboard.py y export.py solo leen la columna / hacen LEFT JOIN).
--
-- Idempotente. Riesgo: BAJO (DROP CONSTRAINT es solo metadatos; toma
-- un lock breve sobre control_acceso y bd_control_acceso).
-- Propuesta -- no aplicada a producción.
-- ================================================================

SET lock_timeout = '5s';

ALTER TABLE public.control_acceso
    DROP CONSTRAINT IF EXISTS control_acceso_cedula_fkey;

CREATE INDEX IF NOT EXISTS idx_ca_cedula ON public.control_acceso (cedula);

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-10-11_control_acceso_cedula_sin_fk.sql',
  'Elimina la FK control_acceso_cedula_fkey (cedula -> bd_control_acceso, ON DELETE SET NULL) para que la cédula se guarde aunque la persona no esté en el maestro. Columna sigue BIGINT NULL; idx_ca_cedula ya existía. Sin backfill: las cédulas ya perdidas no son recuperables. Requiere quitar el cedula = None en backend/routers/control_acceso.py (crear y actualizar).'
)
ON CONFLICT (filename) DO NOTHING;

-- ── ROLLBACK (comentado, no ejecutar sin revisar) ────────────────
-- ADVERTENCIA: recrear la FK FALLA si ya existen ingresos con una
-- cédula que no está en bd_control_acceso (es justo el caso que esta
-- migración permite). Opciones:
--   a) Revisar primero cuántas hay (consulta de verificación abajo)
--      y darlas de alta en el maestro o ponerlas en NULL.
--   b) Crearla NOT VALID: no revisa filas existentes, solo valida
--      las nuevas/modificadas; luego VALIDATE cuando estén limpias:
--        ALTER TABLE public.control_acceso
--          ADD CONSTRAINT control_acceso_cedula_fkey
--          FOREIGN KEY (cedula) REFERENCES public.bd_control_acceso(cedula)
--          ON DELETE SET NULL NOT VALID;
--        -- ALTER TABLE public.control_acceso VALIDATE CONSTRAINT control_acceso_cedula_fkey;
--   c) Versión estricta (falla si hay huérfanas):
--        ALTER TABLE public.control_acceso
--          ADD CONSTRAINT control_acceso_cedula_fkey
--          FOREIGN KEY (cedula) REFERENCES public.bd_control_acceso(cedula)
--          ON DELETE SET NULL;
--   Y volver a desplegar el backend anterior (con cedula = None), de
--   lo contrario los INSERT de cédulas fuera del maestro darán error
--   de FK. Después: DELETE FROM schema_migrations WHERE filename = '2026-10-11_control_acceso_cedula_sin_fk.sql';

-- ── VERIFICACIÓN (informativo) ──────────────────────────────────
-- La FK ya no debe existir (0 filas) y el índice sí (1 fila):
-- SELECT conname FROM pg_constraint WHERE conname = 'control_acceso_cedula_fkey';
-- SELECT indexname FROM pg_indexes WHERE indexname = 'idx_ca_cedula';
-- Ingresos con cédula fuera del maestro (tras el despliegue del backend):
-- SELECT count(*) FROM control_acceso ca
--   LEFT JOIN bd_control_acceso b ON b.cedula = ca.cedula
--  WHERE ca.cedula IS NOT NULL AND b.cedula IS NULL;
-- Ingresos sin cédula (históricos, no recuperables): 
-- SELECT count(*) FROM control_acceso WHERE cedula IS NULL;
