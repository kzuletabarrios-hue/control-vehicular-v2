# backend/routers/dashboard.py
from datetime import date, timedelta
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
    hoy = date.today().isoformat()
    hace7 = (date.today() - timedelta(days=7)).isoformat()
    hace30 = (date.today() - timedelta(days=30)).isoformat()

    def count(tabla: str, filtro: str = "", params: dict = None):
        q = f"SELECT COUNT(*) FROM {tabla}"
        if filtro:
            q += f" WHERE {filtro}"
        return db.execute(text(q), params or {}).scalar() or 0

    flota_hoy      = count("flota_propia",  "fecha = :hoy",   {"hoy": hoy})
    flota_semana   = count("flota_propia",  "fecha >= :d",    {"d": hace7})
    flota_mes      = count("flota_propia",  "fecha >= :d",    {"d": hace30})
    flota_en_ruta  = count("flota_propia",  "fecha = :hoy AND hora_salida_cedi IS NOT NULL AND hora_llegada IS NULL", {"hoy": hoy})

    prov_hoy       = count("proveedores",   "fecha = :hoy",   {"hoy": hoy})
    prov_semana    = count("proveedores",   "fecha >= :d",    {"d": hace7})

    ca_hoy         = count("control_acceso","fecha = :hoy",   {"hoy": hoy})
    ca_activos     = count("control_acceso","fecha = :hoy AND hora_salida IS NULL", {"hoy": hoy})

    vis_hoy        = count("visitantes",    "fecha = :hoy",   {"hoy": hoy})

    visitavh_hoy   = count("visita_vehicular", "fecha = :hoy", {"hoy": hoy})

    # Últimas 5 placas flota
    ultimas_placas = db.execute(text("""
        SELECT DISTINCT ON (placa) placa, conductor, fecha
        FROM flota_propia
        ORDER BY placa, fecha DESC
        LIMIT 5
    """)).fetchall()

    # Distribución por empresa proveedores últimos 30 días
    empresas = db.execute(text("""
        SELECT empresa, COUNT(*) AS total
        FROM proveedores
        WHERE fecha >= :d AND empresa IS NOT NULL
        GROUP BY empresa
        ORDER BY total DESC
        LIMIT 10
    """), {"d": hace30}).fetchall()

    # Pendientes: vehículos sin llegada
    flota_sin_llegada = db.execute(text("""
        SELECT placa, conductor, hora_salida_cedi::text AS hora_salida, fecha::text
        FROM flota_propia
        WHERE hora_salida_cedi IS NOT NULL AND hora_llegada IS NULL
        ORDER BY fecha DESC, hora_salida_cedi DESC
        LIMIT 20
    """)).fetchall()

    # Pendientes: personas sin salida
    acceso_sin_salida = db.execute(text("""
        SELECT nombre, contratista, hora_ingreso::text, fecha::text
        FROM control_acceso
        WHERE hora_ingreso IS NOT NULL AND hora_salida IS NULL
        ORDER BY fecha DESC, hora_ingreso DESC
        LIMIT 20
    """)).fetchall()

    return {
        "fecha": hoy,
        "flota": {
            "hoy": flota_hoy,
            "semana": flota_semana,
            "mes": flota_mes,
            "en_ruta": flota_en_ruta,
        },
        "proveedores": {
            "hoy": prov_hoy,
            "semana": prov_semana,
        },
        "control_acceso": {
            "hoy": ca_hoy,
            "activos_sin_salida": ca_activos,
        },
        "visitantes": {
            "hoy": vis_hoy,
        },
        "visita_vehicular": {
            "hoy": visitavh_hoy,
        },
        "ultimas_placas": [dict(r._mapping) for r in ultimas_placas],
        "top_empresas_proveedores": [dict(r._mapping) for r in empresas],
        "pendientes": {
            "flota_sin_llegada": [dict(r._mapping) for r in flota_sin_llegada],
            "acceso_sin_salida": [dict(r._mapping) for r in acceso_sin_salida],
        },
    }
