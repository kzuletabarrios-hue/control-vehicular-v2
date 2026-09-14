-- ================================================================
-- Activa RLS en public.schema_migrations (hallazgo ERROR de
-- get_advisors de Supabase, descubierto al cerrar los 2 hallazgos
-- ALTO de la auditoria externa -- no es parte de esa auditoria, es
-- un hallazgo propio detectado hoy con las herramientas de Supabase).
--
-- Contexto: schema_migrations es la tabla interna que usan las
-- migraciones de este proyecto para registrar cuales ya se
-- aplicaron (INSERT INTO schema_migrations (filename, nota) ...).
-- Tenia RLS DESHABILITADO por completo (no solo "sin politicas" --
-- deshabilitado de raiz), y ademas el rol `anon` (la llave publica
-- del proyecto) tenia otorgados SELECT, INSERT, UPDATE, DELETE y
-- TRUNCATE sobre ella (verificado con information_schema.role_table_grants).
-- Sin RLS, esos grants se aplican directo via la API REST de
-- Supabase (PostgREST), sin pasar por el backend de esta app ni por
-- ninguna autenticacion propia.
--
-- Confirmado EN VIVO, no solo por el linter: un GET anonimo a
-- https://vhzxtgrpnztwntoqhfaf.supabase.co/rest/v1/schema_migrations
-- con la publishable key devolvia el historial completo de
-- migraciones (nombres de archivo y notas, incluyendo referencias a
-- hallazgos de seguridad internos) a cualquiera, sin login. Los
-- grants de escritura tambien estaban ahi, aunque no se probo el
-- INSERT/DELETE/TRUNCATE en vivo por ser destructivo -- el mismo
-- vacio de RLS que permite el SELECT anonimo permite esas
-- operaciones igual, es la misma causa raiz.
--
-- Por que la solucion es solo "activar RLS sin politicas" (no revocar
-- los grants de anon/authenticated, no crear politicas nuevas): el
-- backend de esta app SIEMPRE se conecta directo a Postgres via
-- DATABASE_URL (SQLAlchemy, ver backend/database.py), nunca usa la
-- API REST/PostgREST de Supabase para ninguna tabla -- exactamente el
-- mismo patron que las otras 30 tablas de `public`, que ya tenian RLS
-- activado sin politicas desde antes (confirmado con get_advisors:
-- ese es el estado esperado y documentado de este proyecto, no un
-- accidente). Activar RLS sin politicas dejar a schema_migrations en
-- ese mismo estado estandar: acceso total bloqueado via PostgREST
-- (anon/authenticated reciben 200 con lista vacia, no error, es el
-- comportamiento normal de RLS-sin-politicas), acceso normal
-- preservado para el backend (que no pasa por RLS al conectarse
-- directo con el rol de la conexion).
--
-- Riesgo: NULO funcionalmente. No se toca ningun dato, no se cambian
-- grants, no se crean politicas. Es un ALTER TABLE de un solo bit
-- (relrowsecurity = true) sin efecto sobre la conexion directa del
-- backend. Verificado despues de aplicar: el GET anonimo que antes
-- devolvia el historial completo ahora devuelve [] (lista vacia,
-- HTTP 200), y get_advisors ya no reporta el hallazgo ERROR
-- "RLS Disabled in Public" para esta tabla -- pasa a aparecer en el
-- mismo grupo INFO "RLS Enabled No Policy" que las demas 30 tablas.
--
-- Fecha: 2026-09-11
-- ================================================================

ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '2026-09-11_activa_rls_schema_migrations.sql',
  'Activa RLS en schema_migrations (hallazgo ERROR de get_advisors: la tabla tenia RLS deshabilitado y el rol anon tenia grants completos de SELECT/INSERT/UPDATE/DELETE/TRUNCATE, expuestos via la API REST publica de Supabase sin pasar por el backend). Confirmado en vivo antes y despues del cambio con un GET anonimo via PostgREST. No se tocaron grants ni se crearon politicas -- mismo patron que las otras 30 tablas de public, que ya tenian RLS activado sin politicas.'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT relrowsecurity FROM pg_class WHERE relname = 'schema_migrations' AND relnamespace = 'public'::regnamespace;
-- -- Esperado: true
--
-- curl -s "https://vhzxtgrpnztwntoqhfaf.supabase.co/rest/v1/schema_migrations?select=filename&limit=5" \
--   -H "apikey: <publishable key>"
-- -- Esperado: [] (antes devolvia el historial completo)
