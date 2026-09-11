-- ================================================================
-- Cierra a escritura pública el bucket de Supabase Storage "fotos".
--
-- ⚠ DIFERENCIA respecto a las demás migraciones de esta carpeta: esto
-- NO es DDL de Postgres sobre tablas de negocio de control-vehicular-v2
-- (no toca `roles`, `proveedores`, ni ninguna tabla del schema
-- `public`). Es DDL de RLS (Row Level Security) sobre `storage.objects`,
-- la tabla interna con la que Supabase Storage modela las policies de
-- cada bucket. Vive en el MISMO proyecto/base de Supabase (mismo
-- Postgres, distinto schema), así que técnicamente se puede correr
-- desde el mismo SQL Editor, pero NO es 100% automática como las
-- demás migraciones de esta carpeta: los DROP POLICY del punto 2
-- usan nombres de política PLACEHOLDER porque yo (Jorge, sin acceso a
-- herramientas MCP de Supabase contra el proyecto real) no puedo leer
-- los nombres reales de las policies existentes. Quien ejecute esto
-- DEBE correr primero el diagnóstico del punto 1, confirmar ahí los
-- nombres reales, y solo entonces adaptar los DROP POLICY antes de
-- correrlos. No lances el punto 2 a ciegas con los nombres de ejemplo.
--
-- Contexto de negocio / hallazgo de seguridad: auditoría externa
-- (matriz ISO 31000, hallazgo ALTO). El bucket `fotos` de Supabase
-- Storage tiene hoy policies de INSERT y DELETE (posiblemente también
-- UPDATE) que dan acceso a los roles `anon`/`public` sobre
-- storage.objects filtrado por bucket_id = 'fotos'. Eso significa que
-- cualquiera que tenga la publishable key del proyecto (que NO es
-- secreta por diseño -- ver comentario en backend/routers/uploads.py,
-- líneas 15-20) puede subir o borrar archivos en ese bucket
-- directamente contra la API de Supabase Storage, sin pasar por el
-- backend de control-vehicular-v2 ni por ninguna autenticación de la
-- app. Confirmado además en backend/routers/uploads.py (función
-- _storage_upload, líneas 23-51): HOY el propio backend sube fotos
-- usando esa misma publishable key (SUPABASE_PUBLISHABLE_KEY /
-- fallback hardcodeado en línea 20) contra
-- POST /storage/v1/object/fotos/{filename} -- es decir, el backend
-- depende hoy de que esa policy pública de INSERT exista.
--
-- ⚠ RIESGO DE SECUENCIA (mi opinión técnica, no lo callo): si este
-- script se corre ANTES de que María cambie
-- backend/routers/uploads.py para subir con la service_role key (que
-- por diseño de Supabase bypassa RLS/policies de Storage por
-- completo, según el enfoque ya validado por Alejandro), el endpoint
-- POST /upload-foto empezará a fallar con 500 ("Error Supabase
-- Storage: ...") para TODOS los usuarios en cuanto se elimine la
-- policy pública de INSERT, porque hoy sube con la publishable key,
-- no con service_role. Esto rompería en producción el flujo de subir
-- fotos de evidencia (salidas de flota, proveedores, visitas, etc.)
-- hasta que el backend quede actualizado. Orden correcto de
-- despliegue: 1) María despliega el cambio de uploads.py a
-- service_role key, 2) se valida que /upload-foto sigue subiendo bien
-- con service_role, 3) recién ahí se ejecuta este script para cerrar
-- las policies públicas de escritura. Si se ejecuta en el orden
-- inverso, hay una ventana de indisponibilidad total de subida de
-- fotos entre el DROP POLICY y el deploy del backend.
--
-- El SELECT público SÍ se mantiene intacto: el frontend consume las
-- fotos con <img src=...> directo a la URL pública
-- (/storage/v1/object/public/fotos/{filename}), sin sesión de
-- Supabase -- no se toca ninguna policy de SELECT/lectura sobre este
-- bucket. Tampoco hace falta crear una policy de INSERT/DELETE para
-- el rol `authenticated` como reemplazo: la service_role key que
-- usará el backend bypassa RLS por completo, así que no necesita
-- ninguna policy a su favor.
--
-- Fecha: 2026-09-07
-- ================================================================


-- ── PASO 1 · DIAGNÓSTICO (SELECT, no modifica nada) ─────────────
-- Ejecutar PRIMERO y a mano en el SQL Editor de Supabase (o vía MCP
-- get_advisors / list de policies si esa herramienta lo permite).
-- Objetivo: confirmar el estado ANTES real -- nombres exactos de
-- policy, comando (INSERT/UPDATE/DELETE/SELECT), roles afectados
-- (anon/authenticated/public) y la condición (qual / with_check) que
-- filtra por bucket_id = 'fotos' -- en vez de asumirlo.

SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'storage'
  AND tablename  = 'objects'
ORDER BY cmd, policyname;

-- Filtra visualmente (o agrega ILIKE) las filas donde qual/with_check
-- contenga "fotos" (o el bucket_id correspondiente) y cmd esté en
-- ('INSERT','UPDATE','DELETE') y roles incluya 'anon' o 'public'.
-- ESAS son las policies a eliminar en el paso 2 -- copia sus
-- `policyname` exactos, no uses los placeholders de abajo tal cual.


-- ── PASO 2 · ELIMINAR policies públicas de escritura/borrado ────
-- ⚠ Los nombres `fotos_insert_public`, `fotos_update_public` y
-- `fotos_delete_public` de abajo son PLACEHOLDERS de ejemplo -- NO
-- están confirmados contra el proyecto real (no tengo acceso a MCP de
-- Supabase). Reemplázalos por los `policyname` reales obtenidos en el
-- PASO 1 antes de ejecutar. Si alguno de los tres comandos
-- (INSERT/UPDATE/DELETE) no tiene policy pública asociada en el
-- diagnóstico, omite esa línea -- no hace falta correr un DROP de
-- algo que no existe.
--
-- IF EXISTS evita que el script falle si ya se corrió antes (parcial
-- o completamente) o si alguno de los nombres no existe -- lo hace
-- seguro de reintentar, pero NO reemplaza la verificación manual del
-- paso 1: un DROP POLICY con el nombre equivocado simplemente no hace
-- nada (falso positivo de "ya está resuelto"), por eso el diagnóstico
-- previo es obligatorio, no opcional.

DROP POLICY IF EXISTS "fotos_insert_public" ON storage.objects;
DROP POLICY IF EXISTS "fotos_update_public" ON storage.objects;
DROP POLICY IF EXISTS "fotos_delete_public" ON storage.objects;

-- Si el diagnóstico del PASO 1 revela nombres distintos (lo más
-- probable -- Supabase suele generar nombres como "Give anon users
-- access to fotos bucket abc123" desde el Dashboard), sustituye las
-- 3 líneas de arriba por los DROP POLICY reales, por ejemplo:
--
--   DROP POLICY IF EXISTS "Give anon INSERT access to fotos 1a2b3c" ON storage.objects;
--
-- No se incluye aquí un DROP POLICY genérico "para todas las policies
-- de escritura del bucket fotos" (ej. vía DO $$ ... $$ con un cursor
-- sobre pg_policies) a propósito: es más seguro revisar cada nombre a
-- ojo contra el diagnóstico del PASO 1 antes de borrar, dado que esta
-- tabla también puede tener policies de otros buckets del mismo
-- proyecto que NO deben tocarse.


-- ── PASO 3 · VERIFICACIÓN posterior (informativo) ───────────────
-- Repetir el diagnóstico del PASO 1 después del DROP y confirmar:
--   a) Ya no aparece ninguna fila con cmd IN ('INSERT','UPDATE','DELETE')
--      y roles conteniendo 'anon'/'public' para el bucket 'fotos'.
--   b) La policy de SELECT pública sobre el bucket 'fotos' SIGUE
--      apareciendo intacta (no se tocó en este script).

SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'storage'
  AND tablename  = 'objects'
ORDER BY cmd, policyname;

-- Adicionalmente (recomendado por Alejandro): correr get_advisors
-- (tipo "security") de las herramientas MCP de Supabase después de
-- este cambio, para que el propio Supabase confirme que no queda
-- ninguna policy pública de escritura sobre storage.objects y que no
-- se introdujo ningún otro hallazgo de seguridad nuevo (ej. un bucket
-- distinto quedando sin ninguna policy de SELECT si alguno de los
-- DROP se aplicó al nombre equivocado).
--
-- Prueba funcional obligatoria antes de dar esto por cerrado: con la
-- publishable key (no service_role), intentar un POST directo a
-- /storage/v1/object/fotos/{cualquier-nombre} y confirmar que ahora
-- responde 403 (RLS violation) en vez de 200/201. Y, por separado,
-- confirmar que POST /upload-foto del backend (YA actualizado por
-- María a service_role key) sigue funcionando -- ver advertencia de
-- secuencia al inicio de este archivo.
--
-- Este archivo NO se autorregistra en `schema_migrations` (esa tabla
-- vive en el schema `public` y documenta cambios de esquema de
-- negocio de control-vehicular-v2; este script no crea ni modifica
-- ninguna tabla de negocio). Si de todos modos se quiere dejar rastro
-- auditable de que esto se ejecutó, se puede insertar manualmente
-- después de verificar el PASO 3:
--
--   INSERT INTO public.schema_migrations (filename, nota)
--   VALUES (
--     '2026-09-07_cierra_bucket_fotos_escritura_publica.sql',
--     'Ejecutado manualmente en Supabase SQL Editor el <FECHA REAL>. Policies eliminadas: <nombres reales obtenidos en el PASO 1>. Verificado con get_advisors y prueba funcional (403 con publishable key, 200 con service_role vía backend).'
--   )
--   ON CONFLICT (filename) DO NOTHING;
