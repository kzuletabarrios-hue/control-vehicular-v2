-- ================================================================
-- Crea indices para las 22 llaves foraneas de public sin indice de
-- cobertura, hallazgo INFO "unindexed_foreign_keys" de get_advidors
-- (performance), revisado como parte del barrido completo de
-- hallazgos pedido por el usuario tras cerrar los de seguridad.
--
-- Por que importa: sin indice en la columna FK, cualquier UPDATE o
-- DELETE sobre la tabla referenciada (ej. borrar un usuario) obliga
-- a Postgres a hacer un seq scan sobre la tabla que tiene la FK para
-- verificar que no queden filas huerfanas, y ademas cualquier JOIN
-- por esa columna en el codigo de la app tiene que escanear la tabla
-- completa en vez de usar un indice. Todas las tablas involucradas
-- son chicas hoy (control_acceso ~7.7k filas es la mas grande), pero
-- varias (control_acceso, citas_programadas, proveedores,
-- flota_propia) son las de mas escritura/consulta de la app y van a
-- seguir creciendo.
--
-- Riesgo: BAJO. CREATE INDEX normal (sin CONCURRENTLY) toma un lock
-- breve de escritura sobre la tabla mientras construye el indice,
-- pero dado el tamano actual de las tablas (todas <8k filas) esto es
-- cuestion de milisegundos. No cambia ningun dato ni comportamiento
-- de la app, solo acelera lecturas/JOINs/borrados futuros.
--
-- Fecha: 2026-09-11
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_archivos_citas_subido_por ON public.archivos_citas (subido_por);
CREATE INDEX IF NOT EXISTS idx_citas_programadas_archivo_id ON public.citas_programadas (archivo_id);
CREATE INDEX IF NOT EXISTS idx_citas_programadas_proveedor_id ON public.citas_programadas (proveedor_id);
CREATE INDEX IF NOT EXISTS idx_configuracion_updated_por ON public.configuracion (updated_por);
CREATE INDEX IF NOT EXISTS idx_control_acceso_creado_por_fk ON public.control_acceso (creado_por_fk);
CREATE INDEX IF NOT EXISTS idx_flota_propia_codigo_conductor ON public.flota_propia (codigo_conductor);
CREATE INDEX IF NOT EXISTS idx_flota_propia_creado_por_fk ON public.flota_propia (creado_por_fk);
CREATE INDEX IF NOT EXISTS idx_flota_propia_tienda_1 ON public.flota_propia (tienda_1);
CREATE INDEX IF NOT EXISTS idx_flota_propia_tienda_2 ON public.flota_propia (tienda_2);
CREATE INDEX IF NOT EXISTS idx_flota_propia_tienda_3 ON public.flota_propia (tienda_3);
CREATE INDEX IF NOT EXISTS idx_flota_propia_tienda_4 ON public.flota_propia (tienda_4);
CREATE INDEX IF NOT EXISTS idx_flota_propia_tienda_5 ON public.flota_propia (tienda_5);
CREATE INDEX IF NOT EXISTS idx_flota_propia_ultima_tienda ON public.flota_propia (ultima_tienda);
CREATE INDEX IF NOT EXISTS idx_herramientas_creado_por ON public.herramientas (creado_por);
CREATE INDEX IF NOT EXISTS idx_muelle_eventos_asignado_por ON public.muelle_eventos (asignado_por);
CREATE INDEX IF NOT EXISTS idx_muelle_eventos_liberado_por ON public.muelle_eventos (liberado_por);
CREATE INDEX IF NOT EXISTS idx_proveedores_creado_por_fk ON public.proveedores (creado_por_fk);
CREATE INDEX IF NOT EXISTS idx_proveedores_marcado_wps_por ON public.proveedores (marcado_wps_por);
CREATE INDEX IF NOT EXISTS idx_sustancias_creado_por ON public.sustancias (creado_por);
CREATE INDEX IF NOT EXISTS idx_usuarios_creado_por ON public.usuarios (creado_por);
CREATE INDEX IF NOT EXISTS idx_visita_vehicular_creado_por ON public.visita_vehicular (creado_por);
CREATE INDEX IF NOT EXISTS idx_visitantes_creado_por_fk ON public.visitantes (creado_por_fk);

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-09-11_indices_llaves_foraneas.sql',
  'Crea indices para las 22 llaves foraneas sin cobertura reportadas por get_advisors (performance, INFO). Tablas chicas (max ~7.7k filas en control_acceso), lock de creacion despreciable. No cambia datos ni comportamiento, solo acelera JOINs/DELETEs futuros. Ultimo item accionable del barrido de performance pedido por el usuario.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%creado_por%' OR indexname LIKE 'idx_%_fkey%';
