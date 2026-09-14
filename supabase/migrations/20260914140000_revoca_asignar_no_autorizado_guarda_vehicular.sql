-- ================================================================
-- Revoca el permiso "asignar" en el módulo "muelles" del rol
-- `guarda_vehicular` -- hallazgo de seguridad: cambio NO AUTORIZADO
-- aplicado directo en producción, fuera de git.
--
-- Autor: Jorge Peña (Arquitecto de BD), a pedido de Alejandro/Karen.
-- Investigación: 2026-09-14. Aplicación real en producción: 2026-09-14,
-- manual, por Karen (dueña del proyecto) vía SQL Editor de Supabase --
-- no por este backend/API (por eso, igual que el resto de cambios de
-- permisos de rol de este proyecto, NO queda ninguna fila en
-- `audit_log`: esa tabla solo audita escrituras que pasan por el
-- helper `_audit()` del backend sobre archivos_citas,
-- citas_programadas, control_acceso, flota_propia y proveedores --
-- nunca sobre `roles`, ni para este cambio ni para ningún otro de los
-- ~15 cambios de permisos ya versionados en este mismo directorio).
-- Este archivo es la migración versionada que documenta ese cambio ya
-- aplicado, para que quede en git y no vuelva a pasar como drift no
-- documentado.
--
-- ── HALLAZGO (auditoría 2026-09-14, ver
--    00000000000000_LEAME_metodologia_y_hallazgos.sql sección 2c para
--    el reporte original) ────────────────────────────────────────
--
-- Se detectó que roles.permisos->'muelles' de guarda_vehicular tenía
-- en producción 3 valores: ["asignar","liberar","read"]. Solo "read"
-- (2026-08-25_permiso_muelles_read_guarda_vehicular.sql) y "liberar"
-- (2026-09-04_permiso_muelles_liberar_guarda_vehicular.sql) estaban
-- explicados por una migración versionada -- "asignar" no aparecía en
-- ningún script de git, ni en ningún commit, ni en ninguna fila de
-- `audit_log`.
--
-- Karen confirmó explícitamente (2026-09-14) que NO reconoce ni
-- autorizó ese permiso para guarda_vehicular -- se trató en adelante
-- como posible hallazgo de seguridad, no solo como gap de
-- documentación, y se investigó antes de tocar nada:
--
--   1) audit_log: 0 filas relacionadas con `roles` o `guarda_vehicular`
--      en 30.663 filas totales (14-jun a 14-sep-2026) -- consistente
--      con que ningún cambio de rol de este proyecto pasa por una API
--      auditada, no es evidencia específica de mala fe por sí sola.
--   2) Logs de plataforma de Supabase: no se pudieron revisar en la
--      sesión de investigación (sin acceso a herramientas MCP de
--      Supabase en ese momento) -- pendiente si algún día se quiere
--      identificar el origen exacto, sujeto a la ventana de retención
--      de logs de Supabase.
--   3) Uso en código: grep exhaustivo de
--      `require_permiso("muelles", ...)` y `puede(user,'muelles',...)`
--      en TODO backend/ y frontend/ -- el único valor de "asignar" con
--      historia real en este repo fue el endpoint
--      `POST /muelles/{id}/asignar` (require_permiso("muelles",
--      "asignar")), introducido el 2026-07-10 en el commit 7119a25
--      ("Fase 3: catálogo de muelles..."), diseñado EXPLÍCITAMENTE
--      para los roles coordinador/admin únicamente (mensaje del
--      commit: "asignar (coordinador/admin) y liberar
--      (guarda_bodega/admin)") -- nunca para guarda_vehicular. Ese
--      mismo endpoint se eliminó del repo apenas ~2 horas después, el
--      mismo día, en el commit c4b2a2a ("revert: quitar el sistema de
--      citas/muelles de este repo"), que además deja constancia
--      explícita de que los permisos de `coordinador` en la base de
--      datos se dejaron intactos a propósito porque la app externa
--      citas-muelles-cedi-r10 los iba a reusar -- sin mencionar en
--      ningún momento a guarda_vehicular. Desde ese revert (2026-07-10)
--      hasta hoy, "muelles:asignar" es una acción MUERTA en este repo:
--      ningún endpoint ni componente de frontend la chequea.
--
--   CONCLUSIÓN: no hay ningún origen legítimo, documentado ni en uso,
--   de "asignar" para guarda_vehicular. Recomendación de Jorge (dada
--   antes de esta migración): revertir. Karen confirmó la reversión.
--
-- ── QUÉ HACE ESTE ARCHIVO ────────────────────────────────────────
-- Documenta -- de forma idempotente -- el UPDATE ya aplicado
-- manualmente en producción el 2026-09-14. Mismo patrón de filtrado
-- seguro de array jsonb que 2026-09-07_revoca_muelles_liberar_guarda_bodega.sql
-- (jsonb_agg(...) FILTER, nunca reemplazo directo del array completo):
-- remueve únicamente el elemento "asignar", preserva "liberar" y
-- "read" sin tocarlos, y no toca ninguna otra clave del jsonb de
-- guarda_vehicular (flota, maestros, dashboard, novedades, visitantes,
-- proveedores, visita_vehicular) ni ninguna otra fila de `roles`.
--
-- Estado ANTES (producción, 2026-09-14): ["asignar","liberar","read"].
-- Estado DESPUÉS (verificado por Jorge con SELECT de solo lectura
-- contra producción, 2026-09-14, posterior a la aplicación manual de
-- Karen): exactamente ["liberar","read"] -- confirmado también que el
-- resto del jsonb de guarda_vehicular quedó intacto
-- ({"flota":["read","write"],"maestros":["read"],"dashboard":["read"],
-- "novedades":["read","write"],"visitantes":["read","write"],
-- "proveedores":["editar_cita","read","write"],
-- "visita_vehicular":["read","write"]}).
--
-- Idempotente: correr este archivo contra producción (donde ya se
-- aplicó a mano) es un no-op seguro -- "asignar" ya no está en el
-- array, el FILTER no encuentra nada que quitar y el resultado queda
-- igual. Correr este archivo contra un ambiente NUEVO (que nunca tuvo
-- el drift, p.ej. local/test reconstruido desde supabase/migrations/)
-- también es no-op seguro: si "asignar" nunca estuvo en el array de
-- ese ambiente, el filtro tampoco encuentra nada que quitar.
--
-- Riesgo: NINGUNO -- revoca una acción que ningún código activo
-- consulta hoy; no hay endpoint ni componente de frontend que deje de
-- funcionar por este cambio.
-- ================================================================

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{muelles}',
    (
        SELECT COALESCE(
            jsonb_agg(elem) FILTER (WHERE elem <> '"asignar"'::jsonb),
            '[]'::jsonb
        )
        FROM jsonb_array_elements(
            COALESCE(permisos -> 'muelles', '[]'::jsonb)
        ) AS elem
    ),
    true
)
WHERE nombre = 'guarda_vehicular';

INSERT INTO schema_migrations (filename, nota)
VALUES (
  '20260914140000_revoca_asignar_no_autorizado_guarda_vehicular.sql',
  'Revoca "asignar" de permisos->''muelles'' de guarda_vehicular -- permiso no autorizado por Karen, sin origen legítimo documentado (el único uso histórico de "muelles:asignar" en este repo, commit 7119a25 del 2026-07-10, estaba diseñado exclusivamente para coordinador/admin y se eliminó del código el mismo día en el commit c4b2a2a) y sin ningún require_permiso/puede() activo en backend/frontend que lo consulte. Investigado 2026-09-14 (audit_log sin filas relacionadas con roles -- consistente con que ningún cambio de rol de este proyecto pasa por API auditada). Aplicado manualmente por Karen vía SQL Editor de Supabase el 2026-09-14, tras su confirmación explícita. Verificado por Jorge con SELECT de solo lectura: quedó exactamente ["liberar","read"], resto del jsonb de guarda_vehicular intacto. Este archivo documenta el cambio ya aplicado (idempotente, no-op si se re-ejecuta).'
)
ON CONFLICT (filename) DO NOTHING;

-- ── VERIFICACIÓN (informativo, no modifica datos) ───────────────
-- SELECT nombre, permisos -> 'muelles' AS muelles, permisos
-- FROM roles
-- WHERE nombre = 'guarda_vehicular';
-- -- Esperado: muelles debe contener EXACTAMENTE ["liberar","read"]
-- -- (2 elementos, sin "asignar"), y el resto de claves del jsonb
-- -- (flota, maestros, dashboard, novedades, visitantes, proveedores,
-- -- visita_vehicular) debe seguir intacto.
-- ================================================================
