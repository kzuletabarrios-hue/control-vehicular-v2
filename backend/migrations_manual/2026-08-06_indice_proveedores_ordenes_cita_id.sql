-- ================================================================
-- Índice (y UNIQUE parcial) sobre proveedores_ordenes.cita_id, de
-- cara al nuevo endpoint de alertas de citas próximas a vencer
-- (GET /proveedores/citas/alertas, a implementar por María).
--
-- Contexto (verificado 2026-08-06 antes de escribir esto):
--   - proveedores_ordenes es una tabla 100% de este repo. No hay
--     ningún otro consumidor conocido (a diferencia de
--     citas_programadas/archivos_citas, documentadas el 2026-08-05
--     como de uso compartido con una app externa). Un cambio de
--     estructura aquí no representa el mismo riesgo.
--   - cita_id (FK -> citas_programadas.id, nullable) ya existe en
--     producción (drift, igual en naturaleza al de
--     numero_orden_compra documentado el 2026-08-05) pero hasta hoy
--     NUNCA se escribe desde este repo: no está en CAMPOS_ORDEN
--     (backend/routers/proveedores.py línea 33) y ninguna de las tres
--     rutas de escritura de proveedores_ordenes (_insert_ordenes línea
--     486, POST /{id}/ordenes línea 532, PUT /{id}/ordenes/{oid} línea
--     555) la incluye. Es decir: hoy la columna es 100% NULL y el
--     endpoint de alertas será su PRIMER escritor real. Confirmado
--     seguro: empezar a escribir en cita_id no compite con ninguna
--     otra escritura conocida.
--
-- Por qué el índice SÍ hace falta, aunque el volumen diario sea bajo
-- (decenas de citas/día, no miles):
--   citas_programadas se vacía y recarga por fecha en cada import
--   (DELETE + INSERT del lote del día), así que su tamaño se mantiene
--   chico y estable. proveedores_ordenes NO tiene ese comportamiento:
--   acumula una fila por cada orden registrada desde el arranque del
--   sistema, sin purga ni archivado, y ya ronda del orden de miles de
--   filas (proveedores llevaba 1408 filas al 2026-08-01, y cada
--   registro genera al menos una fila en proveedores_ordenes). Un
--   NOT EXISTS/LEFT JOIN de "citas de hoy sin match" recorre
--   proveedores_ordenes completo por cada fila de citas_programadas de
--   hoy si no hay índice en cita_id -- funciona hoy por el volumen
--   bajo de citas_programadas, pero degrada con el tiempo a medida que
--   proveedores_ordenes sigue creciendo indefinidamente. Agregar el
--   índice ahora, cuando la tabla todavía es chica, es gratis
--   (CREATE INDEX normal, sin bloqueo perceptible); esperar a que sea
--   grande para agregarlo obligaría a CREATE INDEX CONCURRENTLY con
--   más cuidado operativo.
--
-- Por qué es UNIQUE (parcial) y no solo un índice simple:
--   Un cita_id representa "esta orden ya registró su llegada para
--   esta cita". Si dos filas de proveedores_ordenes llegaran a apuntar
--   al mismo cita_id -- por un doble clic del guarda, un reintento de
--   red duplicado, o un bug en la lógica de matching de María -- una
--   misma cita quedaría "usada" dos veces, lo cual no tiene sentido de
--   negocio (una cita = una llegada) y ensuciaría cualquier reporte
--   futuro de cumplimiento de citas. La columna hoy es 100% NULL, así
--   que agregar el UNIQUE ahora tiene riesgo cero de violación en el
--   momento de crear el índice (no hay backfill que limpiar, a
--   diferencia de por qué NO se agregó un UNIQUE similar en
--   citas_programadas el 2026-08-05). El índice es PARCIAL
--   (WHERE cita_id IS NOT NULL) porque NULL no representa "sin cita
--   asignada aún" como un valor a des-duplicar -- Postgres ya trata
--   NULL <> NULL en UNIQUE por defecto, pero se deja explícito para
--   que el propósito del índice quede claro y no se preste a
--   confusión con un UNIQUE total.
--
--   Este mismo índice UNIQUE parcial resuelve a la vez el punto de
--   rendimiento (sirve para el NOT EXISTS/LEFT JOIN por cita_id) y el
--   de integridad (bloquea a nivel de base de datos el doble match) --
--   no hace falta un índice aparte para cada cosa.
--
--   Nota para María: el INSERT/UPDATE que setee cita_id en
--   proveedores_ordenes debe capturar IntegrityError (violación de
--   este UNIQUE) y responder con un mensaje claro tipo "esta cita ya
--   tiene una llegada registrada" -- no debe tratarse como error 500
--   genérico, es un caso de negocio esperable (carrera entre dos
--   guardas, doble clic, etc.).
--
-- Idempotente: CREATE INDEX IF NOT EXISTS no falla si ya existe.
-- Fecha: 2026-08-06
-- ================================================================

COMMENT ON COLUMN public.proveedores_ordenes.cita_id IS
  'FK -> citas_programadas.id, nullable. Drift retroactivo (columna ya existente en producción, sin ALTER TABLE versionado en git hasta esta migración -- mismo patrón que numero_orden_compra, documentado el 2026-08-05). Hasta el 2026-08-06 nunca se escribió desde este repo (no está en CAMPOS_ORDEN ni en ninguna ruta de escritura de proveedores_ordenes); a partir de la funcionalidad de alertas de citas, marca "esta orden ya registró su llegada para esta cita programada". Tiene un UNIQUE parcial (idx_proveedores_ordenes_cita_id_unico) que impide que dos filas de proveedores_ordenes apunten a la misma cita.';

COMMENT ON COLUMN public.proveedores_ordenes.numero_orden_compra IS
  'Drift retroactivo (columna ya existente en producción, sin ALTER TABLE versionado en git hasta esta migración). A diferencia de citas_programadas.numero_orden_compra, esta columna NO tiene CHECK a nivel de base de datos (verificado 2026-08-06 vía pg_constraint: solo hay FKs y PK en esta tabla) -- el guarda puede guardar aquí texto libre en su alta manual (frontend/index.html, ProveedoresPage), no necesariamente el formato de 10 dígitos. El autorregistro QR del conductor sí normaliza a 10 dígitos antes de guardar (validación de aplicación, no de esquema). No asumir el formato al leer esta columna.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_proveedores_ordenes_cita_id_unico
  ON public.proveedores_ordenes (cita_id)
  WHERE cita_id IS NOT NULL;

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-06_indice_proveedores_ordenes_cita_id.sql')
ON CONFLICT (filename) DO NOTHING;
