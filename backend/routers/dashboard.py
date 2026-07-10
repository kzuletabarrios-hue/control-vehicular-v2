# backend/routers/dashboard.py
from datetime import datetime, timedelta, timezone

_BOG = timezone(timedelta(hours=-5))
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


@router.get("/resumen")
def resumen(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("dashboard", "read")),
):
    hoy_d  = datetime.now(_BOG).date()
    hoy    = hoy_d.isoformat()
    hace7  = (hoy_d - timedelta(days=7)).isoformat()
    hace30 = (hoy_d - timedelta(days=30)).isoformat()

    # 1 query para todos los conteos en lugar de 10 queries separadas
    stats = db.execute(text("""
        WITH
        flota_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE fecha = :hoy)                                                          AS f_hoy,
                COUNT(*) FILTER (WHERE fecha >= :hace7)                                                       AS f_semana,
                COUNT(*) FILTER (WHERE fecha >= :hace30)                                                      AS f_mes,
                COUNT(*) FILTER (WHERE fecha = :hoy AND hora_salida_cedi IS NOT NULL AND hora_llegada IS NULL) AS f_en_ruta
            FROM flota_propia
        ),
        prov_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE fecha = :hoy)    AS p_hoy,
                COUNT(*) FILTER (WHERE fecha >= :hace7) AS p_semana,
                COUNT(*) FILTER (WHERE estado_confirmacion = 'confirmado' AND hora_salida IS NULL) AS p_en_muelle
            FROM proveedores
        ),
        ca_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE fecha = :hoy)                              AS c_hoy,
                COUNT(*) FILTER (WHERE fecha = :hoy AND hora_salida IS NULL)      AS c_activos,
                COUNT(*) FILTER (WHERE fecha != :hoy AND hora_salida IS NULL)     AS c_dias_anteriores
            FROM control_acceso
        ),
        vis_stats AS (
            SELECT COUNT(*) FILTER (WHERE fecha = :hoy) AS v_hoy FROM visitantes
        ),
        vvh_stats AS (
            SELECT COUNT(*) FILTER (WHERE fecha = :hoy) AS vv_hoy FROM visita_vehicular
        ),
        citas_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE fecha = :hoy) AS ci_total,
                COUNT(*) FILTER (WHERE fecha = :hoy AND estado = 'usada') AS ci_usadas,
                COUNT(*) FILTER (WHERE fecha = :hoy AND estado = 'pendiente'
                    AND (hora_cita_fin + (tolerancia_min || ' minutes')::interval) >= (NOW() AT TIME ZONE 'America/Bogota')::time) AS ci_pendientes,
                COUNT(*) FILTER (WHERE fecha = :hoy AND estado = 'pendiente'
                    AND (hora_cita_fin + (tolerancia_min || ' minutes')::interval) < (NOW() AT TIME ZONE 'America/Bogota')::time) AS ci_vencidas
            FROM citas_programadas
        ),
        muelles_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE e.id IS NOT NULL) AS mu_ocupados,
                COUNT(*) FILTER (WHERE e.id IS NULL)     AS mu_libres
            FROM muelles m
            LEFT JOIN muelle_eventos e ON e.muelle_id = m.id AND e.hora_liberado IS NULL
            WHERE m.activo = TRUE
        ),
        muelle_tiempo AS (
            SELECT AVG(EXTRACT(EPOCH FROM (hora_liberado - hora_asignado)) / 60)::int AS mu_prom_min
            FROM muelle_eventos
            WHERE hora_liberado IS NOT NULL AND (hora_liberado AT TIME ZONE 'America/Bogota')::date = :hoy
        ),
        esperando AS (
            SELECT COUNT(*) AS mu_esperando
            FROM proveedores p
            WHERE p.fecha = :hoy AND p.estado_confirmacion = 'confirmado' AND p.hora_salida IS NULL
              AND NOT EXISTS (SELECT 1 FROM muelle_eventos e WHERE e.proveedor_id = p.id AND e.hora_liberado IS NULL)
        ),
        rechazos AS (
            SELECT COUNT(*) AS ci_rechazadas
            FROM audit_log
            WHERE accion = 'VALIDACION_RECHAZADA' AND (created_at AT TIME ZONE 'America/Bogota')::date = :hoy
        )
        SELECT
            f.f_hoy, f.f_semana, f.f_mes, f.f_en_ruta,
            p.p_hoy, p.p_semana, p.p_en_muelle,
            c.c_hoy, c.c_activos, c.c_dias_anteriores,
            v.v_hoy,
            vv.vv_hoy,
            ci.ci_total, ci.ci_usadas, ci.ci_pendientes, ci.ci_vencidas,
            mu.mu_ocupados, mu.mu_libres, mt.mu_prom_min, es.mu_esperando,
            rz.ci_rechazadas
        FROM flota_stats f, prov_stats p, ca_stats c, vis_stats v, vvh_stats vv,
             citas_stats ci, muelles_stats mu, muelle_tiempo mt, esperando es, rechazos rz
    """), {"hoy": hoy, "hace7": hace7, "hace30": hace30}).mappings().one()

    # Últimas 5 placas flota
    ultimas_placas = db.execute(text("""
        SELECT DISTINCT ON (placa) placa, conductor, fecha
        FROM flota_propia
        ORDER BY placa, fecha DESC
        LIMIT 5
    """)).fetchall()

    # Distribución por empresa proveedores últimos 30 días
    empresas = db.execute(text("""
        SELECT po.empresa, COUNT(*) AS total
        FROM proveedores_ordenes po
        JOIN proveedores p ON p.id = po.proveedor_id
        WHERE p.fecha >= :d AND po.empresa IS NOT NULL
        GROUP BY po.empresa
        ORDER BY total DESC
        LIMIT 10
    """), {"d": hace30}).fetchall()

    # Detalle de proveedores actualmente en muelle (ingreso confirmado, sin salida)
    en_muelle = db.execute(text("""
        SELECT p.placa_vehiculo, p.nombre_conductor, p.muelle_descargue, p.hora_ingreso,
               string_agg(DISTINCT po.empresa, ', ') AS empresas
        FROM proveedores p
        LEFT JOIN proveedores_ordenes po ON po.proveedor_id = p.id
        WHERE p.estado_confirmacion = 'confirmado' AND p.hora_salida IS NULL
        GROUP BY p.id, p.placa_vehiculo, p.nombre_conductor, p.muelle_descargue, p.hora_ingreso
        ORDER BY p.hora_ingreso ASC
    """)).fetchall()
    en_muelle_detalle = [
        {
            "placa":     r.placa_vehiculo,
            "conductor": r.nombre_conductor,
            "muelle":    r.muelle_descargue,
            "hora_ingreso": r.hora_ingreso.isoformat() if r.hora_ingreso else None,
            "empresas":  r.empresas,
        }
        for r in en_muelle
    ]

    # Detalle de flota, acceso, proveedores y visitantes de hoy (para el clic en cada tarjeta)
    flota_hoy_rows = db.execute(text("""
        SELECT placa, conductor, muelle_cargue, hora_salida_muelle, hora_salida_cedi, hora_llegada
        FROM flota_propia
        WHERE fecha = :hoy
        ORDER BY created_at DESC
        LIMIT 30
    """), {"hoy": hoy}).fetchall()
    flota_hoy_detalle = [
        {
            "placa": r.placa, "conductor": r.conductor, "muelle": r.muelle_cargue,
            "estado": "Regresó" if r.hora_llegada else ("En ruta" if r.hora_salida_cedi else "En bodega"),
        }
        for r in flota_hoy_rows
    ]

    acceso_hoy_rows = db.execute(text("""
        SELECT nombre, contratista, hora_ingreso, hora_salida
        FROM control_acceso
        WHERE fecha = :hoy
        ORDER BY hora_ingreso DESC
    """), {"hoy": hoy}).fetchall()
    acceso_hoy_detalle = [
        {
            "nombre": r.nombre, "contratista": r.contratista,
            "hora_ingreso": r.hora_ingreso.isoformat() if r.hora_ingreso else None,
            "activo": r.hora_salida is None,
        }
        for r in acceso_hoy_rows
    ][:30]

    prov_hoy_rows = db.execute(text("""
        SELECT p.placa_vehiculo, p.nombre_conductor, p.hora_ingreso, p.hora_salida,
               p.estado_confirmacion,
               string_agg(DISTINCT po.empresa, ', ') AS empresas
        FROM proveedores p
        LEFT JOIN proveedores_ordenes po ON po.proveedor_id = p.id
        WHERE p.fecha = :hoy
        GROUP BY p.id, p.placa_vehiculo, p.nombre_conductor, p.hora_ingreso, p.hora_salida, p.estado_confirmacion
        ORDER BY p.hora_ingreso DESC
    """), {"hoy": hoy}).fetchall()
    prov_hoy_detalle = [
        {
            "placa": r.placa_vehiculo, "conductor": r.nombre_conductor,
            "hora_ingreso": r.hora_ingreso.isoformat() if r.hora_ingreso else None,
            "empresas": r.empresas,
            "estado": "Por confirmar" if r.estado_confirmacion == "pendiente"
                      else ("Salió" if r.hora_salida else "En muelle"),
        }
        for r in prov_hoy_rows
    ][:30]

    visitantes_hoy_rows = db.execute(text("""
        SELECT nombre, empresa, hora_ingreso, hora_salida
        FROM visitantes
        WHERE fecha = :hoy
        ORDER BY hora_ingreso DESC
    """), {"hoy": hoy}).fetchall()
    visitantes_hoy_detalle = [
        {
            "nombre": r.nombre, "empresa": r.empresa,
            "hora_ingreso": r.hora_ingreso.isoformat() if r.hora_ingreso else None,
            "activo": r.hora_salida is None,
        }
        for r in visitantes_hoy_rows
    ][:30]

    # Detalle de accesos sin salida de dias anteriores (para seguimiento --
    # antes se perdian del limite de 100 del listado principal)
    acceso_dias_anteriores_rows = db.execute(text("""
        SELECT ca.nombre, ca.cedula, ca.contratista, ca.fecha, ca.hora_ingreso
        FROM control_acceso ca
        WHERE ca.fecha != :hoy AND ca.hora_salida IS NULL
        ORDER BY ca.fecha ASC, ca.hora_ingreso ASC
    """), {"hoy": hoy}).fetchall()
    acceso_dias_anteriores_detalle = [
        {
            "nombre": r.nombre, "cedula": r.cedula, "contratista": r.contratista,
            "fecha": r.fecha.isoformat() if hasattr(r.fecha, "isoformat") else r.fecha,
            "hora_ingreso": r.hora_ingreso.isoformat() if r.hora_ingreso else None,
            "dias": (hoy_d - r.fecha).days,
        }
        for r in acceso_dias_anteriores_rows
    ]

    # Pendientes vehículos sin llegada + personas sin salida en 1 query
    pendientes = db.execute(text("""
        SELECT 'flota' AS tipo, placa, conductor,
               hora_salida_cedi::text AS hora_ref, fecha::text, NULL AS contratista
        FROM flota_propia
        WHERE hora_salida_cedi IS NOT NULL AND hora_llegada IS NULL
        UNION ALL
        SELECT 'acceso', nombre, NULL,
               hora_ingreso::text, fecha::text, contratista
        FROM control_acceso
        WHERE hora_ingreso IS NOT NULL AND hora_salida IS NULL
        ORDER BY fecha DESC, hora_ref DESC
        LIMIT 40
    """)).fetchall()

    flota_sin_llegada = [
        {"placa": r.placa, "conductor": r.conductor, "hora_salida": r.hora_ref, "fecha": r.fecha}
        for r in pendientes if r.tipo == "flota"
    ][:20]
    acceso_sin_salida = [
        {"nombre": r.placa, "contratista": r.contratista, "hora_ingreso": r.hora_ref, "fecha": r.fecha}
        for r in pendientes if r.tipo == "acceso"
    ][:20]

    return {
        "fecha": hoy,
        "flota": {
            "hoy":         stats["f_hoy"],
            "semana":      stats["f_semana"],
            "mes":         stats["f_mes"],
            "en_ruta":     stats["f_en_ruta"],
            "hoy_detalle": flota_hoy_detalle,
        },
        "proveedores": {
            "hoy":               stats["p_hoy"],
            "semana":            stats["p_semana"],
            "en_muelle":         stats["p_en_muelle"],
            "en_muelle_detalle": en_muelle_detalle,
            "hoy_detalle":       prov_hoy_detalle,
        },
        "control_acceso": {
            "hoy":                        stats["c_hoy"],
            "activos_sin_salida":         stats["c_activos"],
            "hoy_detalle":                acceso_hoy_detalle,
            "dias_anteriores_pendientes": stats["c_dias_anteriores"],
            "dias_anteriores_detalle":    acceso_dias_anteriores_detalle,
        },
        "visitantes": {
            "hoy":         stats["v_hoy"],
            "hoy_detalle": visitantes_hoy_detalle,
        },
        "visita_vehicular": {
            "hoy": stats["vv_hoy"],
        },
        "citas": {
            "total":       stats["ci_total"],
            "usadas":      stats["ci_usadas"],
            "pendientes":  stats["ci_pendientes"],
            "vencidas":    stats["ci_vencidas"],
            "rechazadas":  stats["ci_rechazadas"],
        },
        "muelles": {
            "ocupados":       stats["mu_ocupados"],
            "libres":         stats["mu_libres"],
            "tiempo_prom_min": stats["mu_prom_min"],
            "esperando":      stats["mu_esperando"],
        },
        "ultimas_placas": [dict(r._mapping) for r in ultimas_placas],
        "top_empresas_proveedores": [dict(r._mapping) for r in empresas],
        "pendientes": {
            "flota_sin_llegada": flota_sin_llegada,
            "acceso_sin_salida": acceso_sin_salida,
        },
    }
