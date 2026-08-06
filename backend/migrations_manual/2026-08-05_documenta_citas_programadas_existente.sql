-- ================================================================
-- Documenta (drift retroactivo) las tablas citas_programadas y
-- archivos_citas.
--
-- Migración de SOLO DOCUMENTACIÓN: no hay CREATE TABLE, ALTER TABLE
-- ni ningún cambio de estructura o datos en este archivo. Las dos
-- tablas ya existen en producción (Supabase) y las usa ACTIVAMENTE
-- una app aparte -- fuera de este repositorio -- de gestión de
-- citas/muelles de proveedores. Se crearon directo en la base de
-- datos el 2026-07-10 (10 filas reales en citas_programadas y 7 en
-- archivos_citas al momento de este diagnóstico, 2026-08-05); nunca
-- hubo un CREATE TABLE versionado en git para ninguna de las dos --
-- drift total, igual en naturaleza al de
-- 2026-08-01_roles_guarda_alta_formal.sql y
-- 2026-08-01_proveedores_estado_confirmacion_columns.sql, pero aquí
-- afecta a dos tablas completas, no solo columnas o filas.
--
-- Contexto del hallazgo (2026-08-05): el equipo empezó hoy una tabla
-- nueva `proveedores_citas_dia` para una funcionalidad de "citas de
-- proveedores" pensando que era territorio nuevo; esa migración se
-- descartó sin aplicarse al descubrirse que citas_programadas +
-- archivos_citas ya cumplen ese propósito en producción desde hace 26
-- días y ya tienen un consumidor activo (la app externa). El código
-- de este repo se repunta para usar las tablas reales en vez de crear
-- una paralela.
--
-- Esquema REAL leído directo de Supabase (list_tables) el 2026-08-05,
-- no se infiere ni se completa nada por analogía:
-- ================================================================

COMMENT ON TABLE public.citas_programadas IS
  'Citas de proveedores para ingreso/carga en muelles, importadas por lote desde un archivo (ver archivos_citas). Tabla creada directo en Supabase el 2026-07-10, SIN migración versionada en git (drift retroactivo documentado el 2026-08-05). USO COMPARTIDO: consumida activamente por una app de citas/muelles externa a este repositorio -- cualquier cambio de estructura (tipos, constraints, columnas) puede romper esa app sin que este repo lo detecte. No tiene UNIQUE sobre (fecha, numero_orden_compra); la unicidad por fecha se maneja de forma procedimental (el importador hace DELETE FROM citas_programadas WHERE fecha = :fecha antes de reinsertar el lote del día), no está garantizada por la base de datos. Ver también proveedores_ordenes.cita_id (FK hacia esta tabla, nullable, ya existente).';

COMMENT ON COLUMN public.citas_programadas.id IS
  'PK, uuid, default extensions.uuid_generate_v4().';

COMMENT ON COLUMN public.citas_programadas.archivo_id IS
  'FK -> archivos_citas.id, nullable. Referencia al lote de importación que originó esta fila; NULL si la cita se creó/editó fuera de un import por archivo.';

COMMENT ON COLUMN public.citas_programadas.fecha IS
  'Fecha de la cita. NOT NULL. Es la clave de negocio usada por el importador para reemplazar el lote del día completo (DELETE + INSERT), no hay constraint UNIQUE que lo garantice a nivel de BD.';

COMMENT ON COLUMN public.citas_programadas.numero_orden_compra IS
  'NOT NULL. CHECK: numero_orden_compra ~ ''^4[0-9]{9}$'' -- exactamente 10 dígitos, debe empezar en 4. Cualquier valor fuera de ese patrón es rechazado por la base de datos, no solo por validación de aplicación.';

COMMENT ON COLUMN public.citas_programadas.hora_cita_inicio IS
  'NOT NULL -- SIN excepción. HALLAZGO CRÍTICO documentado 2026-08-05: el archivo real del WMS trae un placeholder "00:00-23:59" en la columna F. Temporal para indicar "todo el día / sin franja horaria específica". Ese placeholder NO puede mapearse a (NULL, NULL) al insertar en esta tabla real -- viola este NOT NULL y el INSERT falla. Esto es distinto de la tabla proveedores_citas_dia que se descartó hoy (ahí sí se había diseñado hora_cita_inicio/fin como nullable para ese caso). Cómo tratar esas filas ("00:00-23:59" -> literal 00:00:00-23:59:00 vs. excluir la fila del batch con un motivo en errores) es una decisión de comportamiento de negocio, no de esquema -- queda pendiente de resolver por quien implemente el importador, no la resuelve esta migración.';

COMMENT ON COLUMN public.citas_programadas.hora_cita_fin IS
  'NOT NULL -- ver nota completa en el comentario de hora_cita_inicio sobre el placeholder "00:00-23:59" del archivo WMS y el mismo bloqueante pendiente de decisión de negocio.';

COMMENT ON COLUMN public.citas_programadas.tolerancia_min IS
  'NOT NULL, default 30. Minutos de tolerancia sobre hora_cita_inicio/fin para considerar la cita vigente/vencida.';

COMMENT ON COLUMN public.citas_programadas.estado IS
  'NOT NULL, default ''pendiente''. CHECK: estado = ANY (ARRAY[''pendiente'',''usada'',''vencida'',''cancelada'']). Cualquier otro valor es rechazado por la base de datos.';

COMMENT ON COLUMN public.citas_programadas.proveedor_id IS
  'FK -> proveedores.id, nullable. Vínculo opcional al maestro de proveedores; proveedor_codigo/proveedor_nombre (columnas de texto libre, también nullable) son el dato tal cual viene del archivo del WMS y pueden no coincidir 1:1 con un proveedor_id resuelto.';

COMMENT ON TABLE public.archivos_citas IS
  'Bitácora de lotes de importación de citas_programadas: un archivo subido = una fila aquí, con contadores de filas totales/importadas/con error y detalle_errores en jsonb. Igual que citas_programadas: creada directo en Supabase el 2026-07-10 sin migración versionada en git, y con el mismo consumidor externo activo -- no se toca su estructura sin coordinar con esa app.';

COMMENT ON COLUMN public.archivos_citas.subido_por IS
  'FK -> usuarios.id, nullable. Usuario del sistema (de este repo, tabla usuarios) que subió el archivo -- es el único punto de acoplamiento directo entre este repo y el flujo de importación además de citas_programadas/archivos_citas en sí.';

COMMENT ON COLUMN public.archivos_citas.total_filas IS
  'NOT NULL, default 0.';

COMMENT ON COLUMN public.archivos_citas.filas_importadas IS
  'NOT NULL, default 0.';

COMMENT ON COLUMN public.archivos_citas.filas_error IS
  'NOT NULL, default 0.';

-- ── Sugerencia NO aplicada (a criterio de Alejandro/María) ─────────
-- citas_programadas no tiene UNIQUE sobre (fecha, numero_orden_compra)
-- y hoy depende de que el importador borre el día completo antes de
-- reinsertar. Si el flujo cambia a upsert por fila (en vez de
-- DELETE+INSERT por fecha), un UNIQUE INDEX sobre
-- (fecha, numero_orden_compra) evitaría duplicados accidentales y
-- habilitaría ON CONFLICT. NO se agrega aquí porque la app externa no
-- controlada por este repo también escribe/lee esta tabla y no se
-- puede confirmar sin coordinación que su flujo de escritura cumpla
-- hoy esa unicidad (un ALTER TABLE ... ADD CONSTRAINT fallaría de
-- inmediato si ya existen violaciones, y aunque no las hubiera hoy,
-- un INSERT futuro de esa app podría violarlo sin previo aviso). Si
-- se decide agregarlo, debe ser en un archivo de migración aparte,
-- coordinado con quien mantiene la app externa, y verificando primero
-- con SELECT fecha, numero_orden_compra, COUNT(*) FROM
-- citas_programadas GROUP BY 1,2 HAVING COUNT(*) > 1 que no hay
-- duplicados ya presentes.

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-05_documenta_citas_programadas_existente.sql')
ON CONFLICT (filename) DO NOTHING;
