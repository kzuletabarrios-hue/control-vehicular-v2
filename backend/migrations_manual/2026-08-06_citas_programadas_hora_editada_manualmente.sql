-- ================================================================
-- Columna hora_editada_manualmente en citas_programadas -- flag para
-- que una edición manual de hora de cita (autorizada fuera del WMS,
-- ej. por un ajuste de última hora acordado por teléfono/correo con
-- el proveedor) sobreviva a la recarga por lote del archivo del
-- mismo día.
--
-- Contexto (decisión de Alejandro, 2026-08-06): el importador hace
-- hoy DELETE FROM citas_programadas WHERE fecha = :fecha antes de
-- reinsertar el lote completo de esa fecha (ver comentario de
-- citas_programadas.fecha en 2026-08-05_documenta_citas_programadas_
-- existente.sql) -- así resuelve la unicidad "una fila por orden y
-- fecha" a nivel procedimental, sin UNIQUE en la base de datos. Ese
-- mismo mecanismo es el problema a resolver aquí: si alguien edita a
-- mano hora_cita_inicio/hora_cita_fin de UNA cita puntual (vía este
-- repo, funcionalidad a implementar por María) y el WMS vuelve a
-- mandar el archivo de ese mismo día -- reenvío normal, no un caso
-- raro -- el DELETE + INSERT de reemplazo borra la fila editada junto
-- con el resto del lote y la recrea con la hora original del archivo,
-- perdiendo la edición manual sin aviso.
--
-- Esta columna es el mecanismo para que el importador pueda distinguir
-- "fila del archivo, reemplazable" de "fila con hora tocada a mano,
-- preservar". El cambio en el importador (fuera de esta migración,
-- backend, de María) es:
--   DELETE FROM citas_programadas
--   WHERE fecha = :fecha AND hora_editada_manualmente IS NOT TRUE;
-- (se usa IS NOT TRUE y no simplemente = false porque el default es
-- false pero conviene que el DELETE también capture cualquier fila
-- vieja con el valor en NULL si alguna vez llegara a estarlo, en vez
-- de dejarla huérfana sin borrar por accidente de comparación con
-- NULL).
--
-- Consecuencia de negocio que queda pendiente de resolver por quien
-- implemente el flujo (no es un problema de esquema): una fila con
-- hora_editada_manualmente = true deja de recibir las actualizaciones
-- del archivo del WMS para ESA fila puntual mientras el flag siga en
-- true (numero_orden_compra, estado, tolerancia_min, etc. tampoco se
-- tocan porque la fila entera sobrevive al reemplazo). Si el WMS
-- cambia legítimamente otro dato de esa misma orden en un envío
-- posterior (no solo la hora), ese cambio no se reflejará hasta que
-- alguien limpie el flag manualmente o se agregue lógica de
-- reconciliación -- decisión de negocio, no de base de datos.
--
-- Riesgo residual (mismo estándar de cautela que las migraciones
-- anteriores sobre esta tabla, 2026-08-05 y 2026-08-06): agregar una
-- columna NOT NULL DEFAULT false es de bajo riesgo para los patrones
-- estándar de acceso -- INSERT con columnas nombradas explícitas y
-- SELECT con columnas nombradas o SELECT * consumido por nombre de
-- columna (dict/objeto), que es la práctica común en drivers modernos
-- (psycopg con RealDictCursor, ORMs, PostgREST/Supabase client, etc.).
-- NO está verificado con el equipo que mantiene la app externa de
-- citas/muelles si su código hace INSERT ... VALUES (...) posicional
-- (sin listar columnas) o si depende de una aridad fija de columnas en
-- algún SELECT * (ej. mapeo posicional a una fila de un DataFrame, un
-- struct, o un array por índice) -- en cualquiera de esos dos casos,
-- una columna nueva SÍ podría romper su flujo al desalinear las
-- posiciones o el conteo de columnas esperado. Esta migración procede
-- de todas formas porque el riesgo es bajo y el patrón afectado es
-- minoritario, pero queda documentado explícitamente como riesgo no
-- descartado, no como riesgo cero.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS no falla si ya existe.
-- Fecha: 2026-08-06
-- ================================================================

ALTER TABLE public.citas_programadas
  ADD COLUMN IF NOT EXISTS hora_editada_manualmente BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN public.citas_programadas.hora_editada_manualmente IS
  'NOT NULL, default false. true = hora_cita_inicio/hora_cita_fin de esta fila puntual fueron editadas a mano (fuera del WMS, autorizado por el equipo) y la fila debe sobrevivir a la recarga del archivo del mismo día. El importador debe cambiar su DELETE FROM citas_programadas WHERE fecha = :fecha a WHERE fecha = :fecha AND hora_editada_manualmente IS NOT TRUE antes de reinsertar el lote, o esta fila se borra y se recrea con la hora original del archivo en el siguiente reenvío del WMS. Mientras el flag esté en true, la fila deja de recibir cualquier actualización del archivo (no solo la hora) hasta que se limpie el flag o se implemente reconciliación -- ver comentario extenso al inicio de 2026-08-06_citas_programadas_hora_editada_manualmente.sql.';

INSERT INTO schema_migrations (filename)
VALUES ('2026-08-06_citas_programadas_hora_editada_manualmente.sql')
ON CONFLICT (filename) DO NOTHING;
