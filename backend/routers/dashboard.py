# backend/routers/dashboard.py
from datetime import date, datetime, timedelta, timezone

_BOG = timezone(timedelta(hours=-5))
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

# Rango máximo permitido para GET /dashboard/estadisticas (ver
# docs/estadisticas_contrato.md sección 0): evita que un rango absurdo
# (ej. "desde 2020") fuerce un generate_series de miles de días con
# recálculo fila por fila en las secciones B y D.
RANGO_MAX_DIAS_ESTADISTICAS = 366


def _resolver_rango_estadisticas(
    fecha_desde: str | None, fecha_hasta: str | None
) -> tuple[date, date]:
    """Resuelve y valida el rango de fechas de /dashboard/estadisticas.

    Default (si faltan ambos parámetros o solo uno): últimos 30 días en
    zona horaria Colombia -- mismo patrón que el resto de este archivo
    (`_BOG = timezone(timedelta(hours=-5))`), sin `zoneinfo`: Bogotá no
    tiene horario de verano, así que el offset fijo ya usado en este
    módulo y en muelles.py es correcto (ver contrato, sección 0).
    """
    hoy = datetime.now(_BOG).date()
    try:
        hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else hoy
        desde = date.fromisoformat(fecha_desde) if fecha_desde else (hasta - timedelta(days=30))
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido, use YYYY-MM-DD")

    if desde > hasta:
        raise HTTPException(status_code=400, detail="fecha_desde no puede ser mayor a fecha_hasta")
    if (hasta - desde).days > RANGO_MAX_DIAS_ESTADISTICAS:
        raise HTTPException(
            status_code=400,
            detail=f"El rango máximo permitido es de {RANGO_MAX_DIAS_ESTADISTICAS} días",
        )
    return desde, hasta


def _num(valor):
    """Decimal/None -> float/None, preservando `null` (nunca lo convierte
    en `0` falso). Usado para promedios, medianas y porcentajes calculados
    en SQL con ROUND(...::numeric, 1), que psycopg2 devuelve como Decimal."""
    return float(valor) if valor is not None else None


def _fecha_iso(valor):
    """date -> 'YYYY-MM-DD'. Deja pasar valores ya-string sin romper."""
    return valor.isoformat() if hasattr(valor, "isoformat") else valor


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
        )
        SELECT
            f.f_hoy, f.f_semana, f.f_mes, f.f_en_ruta,
            p.p_hoy, p.p_semana, p.p_en_muelle,
            c.c_hoy, c.c_activos, c.c_dias_anteriores,
            v.v_hoy,
            vv.vv_hoy
        FROM flota_stats f, prov_stats p, ca_stats c, vis_stats v, vvh_stats vv
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
                      else ("Ingresado WPS" if r.estado_confirmacion == "ingresado_wps"
                      else ("Salió" if r.hora_salida else "En muelle")),
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
        "ultimas_placas": [dict(r._mapping) for r in ultimas_placas],
        "top_empresas_proveedores": [dict(r._mapping) for r in empresas],
        "pendientes": {
            "flota_sin_llegada": flota_sin_llegada,
            "acceso_sin_salida": acceso_sin_salida,
        },
    }


@router.get("/tiempo-autorregistro")
def tiempo_autorregistro(
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("dashboard", "read")),
):
    """Mediana, promedio y número de muestras de cuánto tarda un conductor en
    llenar el formulario de autorregistro por QR (proveedores.tiempo_autorregistro_segundos).
    Excluye NULL automáticamente (filas sin QR, ej. alta manual del guarda).
    Filtro opcional de rango de fechas sobre proveedores.fecha -- nombres de
    parámetro alineados con el resto del backend (ver export.py), no con
    /resumen de este mismo archivo, que no acepta filtro de fecha por request.
    """
    row = db.execute(text("""
        SELECT
            AVG(tiempo_autorregistro_segundos)                                     AS promedio_seg,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tiempo_autorregistro_segundos) AS mediana_seg,
            COUNT(tiempo_autorregistro_segundos)                                   AS muestras
        FROM proveedores
        WHERE tiempo_autorregistro_segundos IS NOT NULL
          AND (:desde IS NULL OR fecha >= :desde)
          AND (:hasta IS NULL OR fecha <= :hasta)
    """), {"desde": fecha_desde, "hasta": fecha_hasta}).mappings().one()

    promedio_seg = float(row["promedio_seg"]) if row["promedio_seg"] is not None else None
    mediana_seg  = float(row["mediana_seg"])  if row["mediana_seg"]  is not None else None

    return {
        "promedio_segundos": round(promedio_seg) if promedio_seg is not None else None,
        "promedio_minutos":  round(promedio_seg / 60, 1) if promedio_seg is not None else None,
        "mediana_segundos":  round(mediana_seg) if mediana_seg is not None else None,
        "mediana_minutos":   round(mediana_seg / 60, 1) if mediana_seg is not None else None,
        "muestras":          row["muestras"],
    }


@router.get("/estadisticas")
def estadisticas(
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("dashboard", "read")),
):
    """Pestaña "Estadísticas": 6 secciones (A-F) en un único JSON, para el
    mismo rango de fechas coherente en toda la pantalla -- ver contrato
    completo (queries, definiciones, exclusiones) en
    docs/estadisticas_contrato.md, escrito por Jorge Peña.

    Default sin parámetros: últimos 30 días en zona Bogotá. Rango máximo
    366 días. fecha_desde > fecha_hasta o formato inválido -> 400.
    """
    desde, hasta = _resolver_rango_estadisticas(fecha_desde, fecha_hasta)
    params = {"desde": desde, "hasta": hasta}

    # ── A. Tendencia diaria por módulo ──────────────────────────────
    tendencia_rows = db.execute(text("""
        WITH serie AS (
            SELECT generate_series((:desde)::date, (:hasta)::date, interval '1 day')::date AS dia
        ),
        flota_d AS (
            SELECT fecha AS dia, COUNT(*) AS n
            FROM flota_propia
            WHERE fecha BETWEEN :desde AND :hasta
            GROUP BY fecha
        ),
        prov_d AS (
            SELECT fecha AS dia, COUNT(*) AS n
            FROM proveedores
            WHERE fecha BETWEEN :desde AND :hasta
            GROUP BY fecha
        ),
        acceso_d AS (
            SELECT fecha AS dia, COUNT(*) AS n
            FROM control_acceso
            WHERE fecha BETWEEN :desde AND :hasta AND anulado = FALSE
            GROUP BY fecha
        ),
        visitantes_d AS (
            SELECT fecha AS dia, COUNT(*) AS n
            FROM visitantes
            WHERE fecha BETWEEN :desde AND :hasta
            GROUP BY fecha
        )
        SELECT
            s.dia,
            COALESCE(f.n, 0) AS flota,
            COALESCE(p.n, 0) AS proveedores,
            COALESCE(a.n, 0) AS control_acceso,
            COALESCE(v.n, 0) AS visitantes
        FROM serie s
        LEFT JOIN flota_d      f ON f.dia = s.dia
        LEFT JOIN prov_d       p ON p.dia = s.dia
        LEFT JOIN acceso_d     a ON a.dia = s.dia
        LEFT JOIN visitantes_d v ON v.dia = s.dia
        ORDER BY s.dia
    """), params).mappings().all()

    tendencia_diaria = [
        {
            "fecha":          _fecha_iso(r["dia"]),
            "flota":          r["flota"],
            "proveedores":    r["proveedores"],
            "control_acceso": r["control_acceso"],
            "visitantes":     r["visitantes"],
        }
        for r in tendencia_rows
    ]

    # ── B. Tiempo en muelle de proveedores (global + por día) ───────
    b_global = db.execute(text("""
        WITH base AS (
            SELECT
                p.id,
                (p.fecha + COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso)) AS ingreso_ts,
                (COALESCE(p.fecha_salida, p.fecha) + p.hora_salida)             AS salida_ts_base
            FROM proveedores p
            WHERE p.fecha BETWEEN :desde AND :hasta
              AND p.estado_confirmacion = 'confirmado'
              AND p.hora_salida IS NOT NULL
              AND COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso) IS NOT NULL
        ),
        calc AS (
            SELECT
                id, ingreso_ts,
                CASE WHEN salida_ts_base < ingreso_ts
                     THEN salida_ts_base + interval '1 day'
                     ELSE salida_ts_base
                END AS salida_ts
            FROM base
        ),
        minutos AS (
            SELECT id, EXTRACT(EPOCH FROM (salida_ts - ingreso_ts)) / 60.0 AS min
            FROM calc
        )
        SELECT
            ROUND(AVG(min)::numeric, 1)                                          AS promedio_minutos,
            ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min))::numeric, 1) AS mediana_minutos,
            COUNT(*)                                                             AS n_validos
        FROM minutos
        WHERE min > 0 AND min <= 1440
    """), params).mappings().one()

    b_por_dia_rows = db.execute(text("""
        WITH base AS (
            SELECT
                p.id, p.fecha AS dia,
                (p.fecha + COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso)) AS ingreso_ts,
                (COALESCE(p.fecha_salida, p.fecha) + p.hora_salida)             AS salida_ts_base
            FROM proveedores p
            WHERE p.fecha BETWEEN :desde AND :hasta
              AND p.estado_confirmacion = 'confirmado'
              AND p.hora_salida IS NOT NULL
              AND COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso) IS NOT NULL
        ),
        calc AS (
            SELECT
                dia, ingreso_ts,
                CASE WHEN salida_ts_base < ingreso_ts
                     THEN salida_ts_base + interval '1 day'
                     ELSE salida_ts_base
                END AS salida_ts
            FROM base
        ),
        minutos AS (
            SELECT dia, EXTRACT(EPOCH FROM (salida_ts - ingreso_ts)) / 60.0 AS min
            FROM calc
        ),
        validos AS (
            SELECT * FROM minutos WHERE min > 0 AND min <= 1440
        ),
        serie AS (
            SELECT generate_series((:desde)::date, (:hasta)::date, interval '1 day')::date AS dia
        )
        SELECT
            s.dia,
            ROUND(AVG(v.min)::numeric, 1)                                          AS promedio_minutos,
            ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.min))::numeric, 1) AS mediana_minutos,
            COUNT(v.min)                                                           AS n_validos
        FROM serie s
        LEFT JOIN validos v ON v.dia = s.dia
        GROUP BY s.dia
        ORDER BY s.dia
    """), params).mappings().all()

    tiempo_muelle_proveedores = {
        "global": {
            "promedio_minutos": _num(b_global["promedio_minutos"]),
            "mediana_minutos":  _num(b_global["mediana_minutos"]),
            "n_validos":        b_global["n_validos"],
        },
        "por_dia": [
            {
                "fecha":            _fecha_iso(r["dia"]),
                "promedio_minutos": _num(r["promedio_minutos"]),
                "mediana_minutos":  _num(r["mediana_minutos"]),
                "n_validos":        r["n_validos"],
            }
            for r in b_por_dia_rows
        ],
    }

    # ── C. Ingresos por hora del día (0-23) ─────────────────────────
    c_rows = db.execute(text("""
        WITH horas AS (
            SELECT generate_series(0, 23) AS hora
        ),
        ca_h AS (
            SELECT EXTRACT(HOUR FROM hora_ingreso)::int AS hora, COUNT(*) AS n
            FROM control_acceso
            WHERE fecha BETWEEN :desde AND :hasta
              AND anulado = FALSE
              AND hora_ingreso IS NOT NULL
            GROUP BY 1
        ),
        prov_h AS (
            SELECT EXTRACT(HOUR FROM hora_ingreso)::int AS hora, COUNT(*) AS n
            FROM proveedores
            WHERE fecha BETWEEN :desde AND :hasta
              AND hora_ingreso IS NOT NULL
            GROUP BY 1
        ),
        flota_h AS (
            SELECT EXTRACT(HOUR FROM hora_salida_cedi)::int AS hora, COUNT(*) AS n
            FROM flota_propia
            WHERE fecha_salida BETWEEN :desde AND :hasta
              AND hora_salida_cedi IS NOT NULL
            GROUP BY 1
        )
        SELECT
            h.hora,
            COALESCE(ca.n, 0) AS control_acceso,
            COALESCE(p.n, 0)  AS proveedores,
            COALESCE(f.n, 0)  AS flota_salidas_cedi
        FROM horas h
        LEFT JOIN ca_h   ca ON ca.hora = h.hora
        LEFT JOIN prov_h p  ON p.hora  = h.hora
        LEFT JOIN flota_h f ON f.hora  = h.hora
        ORDER BY h.hora
    """), params).mappings().all()

    ingresos_por_hora = [
        {
            "hora":               r["hora"],
            "control_acceso":     r["control_acceso"],
            "proveedores":        r["proveedores"],
            "flota_salidas_cedi": r["flota_salidas_cedi"],
        }
        for r in c_rows
    ]

    # ── D. Flota: tiempo de ruta (global + top N por placa) ─────────
    d_global = db.execute(text("""
        WITH rutas AS (
            SELECT
                f.id, f.placa,
                (f.fecha_salida + f.hora_salida_cedi) AS salida_ts,
                (f.fecha_llegada + f.hora_llegada)    AS llegada_ts
            FROM flota_propia f
            WHERE f.fecha_salida BETWEEN :desde AND :hasta
              AND f.fecha_salida  IS NOT NULL AND f.hora_salida_cedi IS NOT NULL
              AND f.fecha_llegada IS NOT NULL AND f.hora_llegada     IS NOT NULL
        ),
        minutos AS (
            SELECT id, placa, EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 AS min
            FROM rutas
        )
        SELECT
            ROUND(AVG(min)::numeric, 1)                                          AS promedio_minutos,
            ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min))::numeric, 1) AS mediana_minutos,
            COUNT(*)                                                             AS n_validos
        FROM minutos
        WHERE min > 0 AND min <= 2880
    """), params).mappings().one()

    d_top_rows = db.execute(text("""
        WITH rutas AS (
            SELECT
                f.id, f.placa,
                (f.fecha_salida + f.hora_salida_cedi) AS salida_ts,
                (f.fecha_llegada + f.hora_llegada)    AS llegada_ts
            FROM flota_propia f
            WHERE f.fecha_salida BETWEEN :desde AND :hasta
              AND f.fecha_salida  IS NOT NULL AND f.hora_salida_cedi IS NOT NULL
              AND f.fecha_llegada IS NOT NULL AND f.hora_llegada     IS NOT NULL
        ),
        minutos AS (
            SELECT id, placa, EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 AS min
            FROM rutas
            WHERE EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 > 0
              AND EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 <= 2880
        )
        SELECT
            placa,
            ROUND(AVG(min)::numeric, 1)                                          AS promedio_minutos,
            ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min))::numeric, 1) AS mediana_minutos,
            COUNT(*)                                                             AS n_viajes
        FROM minutos
        GROUP BY placa
        ORDER BY n_viajes DESC, promedio_minutos DESC
        LIMIT 10
    """), params).mappings().all()

    tiempo_ruta_flota = {
        "global": {
            "promedio_minutos": _num(d_global["promedio_minutos"]),
            "mediana_minutos":  _num(d_global["mediana_minutos"]),
            "n_validos":        d_global["n_validos"],
        },
        "top_placas": [
            {
                "placa":            r["placa"],
                "promedio_minutos": _num(r["promedio_minutos"]),
                "mediana_minutos":  _num(r["mediana_minutos"]),
                "n_viajes":         r["n_viajes"],
            }
            for r in d_top_rows
        ],
    }

    # ── E. Flota: pallets y contenedores despachados por día ────────
    e_rows = db.execute(text("""
        WITH serie AS (
            SELECT generate_series((:desde)::date, (:hasta)::date, interval '1 day')::date AS dia
        ),
        flota_agg AS (
            SELECT fecha AS dia, SUM(n_pallets) AS pallets, SUM(n_contenedores) AS contenedores
            FROM flota_propia
            WHERE fecha BETWEEN :desde AND :hasta
            GROUP BY fecha
        )
        SELECT
            s.dia,
            COALESCE(fa.pallets, 0)::int      AS pallets,
            COALESCE(fa.contenedores, 0)::int AS contenedores
        FROM serie s
        LEFT JOIN flota_agg fa ON fa.dia = s.dia
        ORDER BY s.dia
    """), params).mappings().all()

    carga_despachada_por_dia = [
        {
            "fecha":        _fecha_iso(r["dia"]),
            "pallets":      r["pallets"],
            "contenedores": r["contenedores"],
        }
        for r in e_rows
    ]

    # ── F. Flota: cumplimiento de sellos (global + por día) ─────────
    f_global = db.execute(text("""
        SELECT
            COUNT(*) AS total_viajes,
            COUNT(*) FILTER (WHERE sello IS NOT NULL AND btrim(sello) <> '') AS con_sello_salida,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE sello IS NOT NULL AND btrim(sello) <> '')
                / NULLIF(COUNT(*), 0)
            , 1) AS pct_sello_salida,
            COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL) AS viajes_con_llegada,
            COUNT(*) FILTER (
                WHERE hora_llegada IS NOT NULL
                  AND sello_entrada IS NOT NULL AND btrim(sello_entrada) <> ''
            ) AS con_sello_entrada,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE hora_llegada IS NOT NULL
                      AND sello_entrada IS NOT NULL AND btrim(sello_entrada) <> ''
                )
                / NULLIF(COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL), 0)
            , 1) AS pct_sello_entrada
        FROM flota_propia
        WHERE fecha BETWEEN :desde AND :hasta
    """), params).mappings().one()

    f_por_dia_rows = db.execute(text("""
        WITH serie AS (
            SELECT generate_series((:desde)::date, (:hasta)::date, interval '1 day')::date AS dia
        ),
        agg AS (
            SELECT
                fecha AS dia,
                COUNT(*) AS total_viajes,
                COUNT(*) FILTER (WHERE sello IS NOT NULL AND btrim(sello) <> '') AS con_sello_salida,
                COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL) AS viajes_con_llegada,
                COUNT(*) FILTER (
                    WHERE hora_llegada IS NOT NULL
                      AND sello_entrada IS NOT NULL AND btrim(sello_entrada) <> ''
                ) AS con_sello_entrada
            FROM flota_propia
            WHERE fecha BETWEEN :desde AND :hasta
            GROUP BY fecha
        )
        SELECT
            s.dia,
            COALESCE(a.total_viajes, 0)      AS total_viajes,
            COALESCE(a.con_sello_salida, 0)  AS con_sello_salida,
            ROUND(100.0 * COALESCE(a.con_sello_salida, 0) / NULLIF(a.total_viajes, 0), 1) AS pct_sello_salida,
            COALESCE(a.viajes_con_llegada, 0) AS viajes_con_llegada,
            COALESCE(a.con_sello_entrada, 0)  AS con_sello_entrada,
            ROUND(100.0 * COALESCE(a.con_sello_entrada, 0) / NULLIF(a.viajes_con_llegada, 0), 1) AS pct_sello_entrada
        FROM serie s
        LEFT JOIN agg a ON a.dia = s.dia
        ORDER BY s.dia
    """), params).mappings().all()

    cumplimiento_sellos = {
        "global": {
            "total_viajes":       f_global["total_viajes"],
            "con_sello_salida":   f_global["con_sello_salida"],
            "pct_sello_salida":   _num(f_global["pct_sello_salida"]),
            "viajes_con_llegada": f_global["viajes_con_llegada"],
            "con_sello_entrada":  f_global["con_sello_entrada"],
            "pct_sello_entrada":  _num(f_global["pct_sello_entrada"]),
        },
        "por_dia": [
            {
                "fecha":              _fecha_iso(r["dia"]),
                "total_viajes":       r["total_viajes"],
                "con_sello_salida":   r["con_sello_salida"],
                "pct_sello_salida":   _num(r["pct_sello_salida"]),
                "viajes_con_llegada": r["viajes_con_llegada"],
                "con_sello_entrada":  r["con_sello_entrada"],
                "pct_sello_entrada":  _num(r["pct_sello_entrada"]),
            }
            for r in f_por_dia_rows
        ],
    }

    return {
        "fecha_desde": desde.isoformat(),
        "fecha_hasta": hasta.isoformat(),
        "tendencia_diaria": tendencia_diaria,
        "tiempo_muelle_proveedores": tiempo_muelle_proveedores,
        "ingresos_por_hora": ingresos_por_hora,
        "tiempo_ruta_flota": tiempo_ruta_flota,
        "carga_despachada_por_dia": carga_despachada_por_dia,
        "cumplimiento_sellos": cumplimiento_sellos,
    }
