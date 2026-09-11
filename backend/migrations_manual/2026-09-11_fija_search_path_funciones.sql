-- ================================================================
-- Fija search_path en las 4 funciones de public que get_advisors
-- reportaba como "function_search_path_mutable" (WARN), como parte
-- del barrido completo de hallazgos pendientes pedido por el
-- usuario despues de cerrar los hallazgos ALTO de la auditoria
-- externa y el ERROR de schema_migrations (ver
-- 2026-09-11_activa_rls_schema_migrations.sql).
--
-- Contexto del hallazgo: una funcion sin search_path fijo hereda el
-- search_path de quien la ejecuta. Si es SECURITY DEFINER, alguien
-- con permiso de crear objetos en un schema que aparezca antes en
-- ese search_path podria "secuestrar" la funcion creando una tabla u
-- otra funcion con el mismo nombre que algo que la funcion referencia
-- sin calificar por schema, y la funcion terminaria usando ese objeto
-- malicioso con los privilegios elevados del dueno de la funcion --
-- es el vector clasico de escalamiento de privilegios en Postgres.
--
-- Verificado antes de aplicar (via pg_proc.prosecdef) que las 4
-- funciones son SECURITY INVOKER, no SECURITY DEFINER:
--   trigger_set_updated_at, tiene_permiso,
--   fn_ca_bloquear_reversion_anulacion, fn_control_acceso_anular
-- Con SECURITY INVOKER el vector de escalamiento de privilegios no
-- aplica (la funcion ya corre con los privilegios de quien la llama,
-- no con los del dueno) -- por eso el hallazgo era WARN y no ERROR.
-- Aun asi se corrige como buena practica de endurecimiento: el cambio
-- es de riesgo nulo (no toca la logica de la funcion, solo fija de
-- donde resuelve nombres no calificados) y es la remediacion estandar
-- que recomienda el propio linter de Supabase.
--
-- Riesgo: NULO funcionalmente. No cambia el codigo ni el
-- comportamiento de ninguna funcion, solo fija su search_path.
--
-- Fecha: 2026-09-11
-- ================================================================

ALTER FUNCTION public.trigger_set_updated_at() SET search_path = public, pg_temp;
ALTER FUNCTION public.tiene_permiso(uuid, text, text) SET search_path = public, pg_temp;
ALTER FUNCTION public.fn_ca_bloquear_reversion_anulacion() SET search_path = public, pg_temp;
ALTER FUNCTION public.fn_control_acceso_anular(uuid, uuid, text, integer) SET search_path = public, pg_temp;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-09-11_fija_search_path_funciones.sql',
  'Fija search_path en las 4 funciones que get_advisors reportaba como function_search_path_mutable (WARN). Confirmado antes de aplicar que ninguna es SECURITY DEFINER (son SECURITY INVOKER), por lo que el vector clasico de escalamiento de privilegios no aplicaba; se corrige de todas formas como endurecimiento estandar, sin tocar logica. Cierra el ultimo hallazgo de seguridad accionable del barrido completo (get_advisors security + performance) pedido por el usuario.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT proname, prosecdef, proconfig FROM pg_proc
-- WHERE pronamespace = 'public'::regnamespace
--   AND proname IN ('trigger_set_updated_at','tiene_permiso','fn_ca_bloquear_reversion_anulacion','fn_control_acceso_anular');
-- -- Esperado: proconfig incluye "search_path=public, pg_temp" en las 4
