# backend/routers/citas.py
#
# Fase 3 (solo lectura) del plan de consolidación con citas-muelles-cedi-r10.
# Decisión del arquitecto: este router expone ÚNICAMENTE consulta del estado
# de citas de proveedores (validación contra el archivo de logística del
# WMS). NO se agrega aquí la carga del archivo (POST) ni la edición de la
# tolerancia (PUT) -- esas operaciones siguen siendo exclusivas de
# citas-muelles-cedi-r10, por la misma razón que en muelles.py: escribir
# sobre citas_programadas/configuracion desde dos apps distintas abriría una
# segunda vía de modificar el mismo estado operativo que ya gestiona esa
# app en producción.
#
# Lógica de alertas() copiada literal de la de referencia en
# C:\citas-muelles-cedi-r10\backend\routers\citas.py -- incluyendo el
# cálculo con datetime.combine(fecha, hora) y el filtro fecha IN (hoy, ayer),
# que corrige un bug histórico con franjas que cruzan medianoche al sumar la
# tolerancia. No se cambia ni una línea de esa fórmula: ambas apps leen la
# misma tabla citas_programadas y deben mostrar los mismos conteos.
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))
ALERTA_VENCE_MIN  = 10  # aviso cuando falten <=10 min para el fin de la franja (+tolerancia)
ALERTA_INICIO_MIN = 5   # aviso cuando falten <=5 min para que empiece la hora de la cita


def _tolerancia_default(db) -> int:
    row = db.execute(text("SELECT valor FROM configuracion WHERE clave = 'tolerancia_min_default'")).fetchone()
    try:
        return int(row.valor) if row else 30
    except (TypeError, ValueError):
        return 30


@router.get("/config")
def obtener_config(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    return {"tolerancia_min_default": _tolerancia_default(db)}


@router.get("")
def listar(
    fecha: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    where = "WHERE fecha = :fecha" if fecha else ""
    params = {"fecha": fecha} if fecha else {}
    rows = db.execute(
        text(f"SELECT * FROM citas_programadas {where} ORDER BY hora_cita_inicio ASC"), params
    ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/alertas")
def alertas(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    """Calculado en vivo en cada consulta -- nunca se persiste 'vencida' en
    citas_programadas.estado, así que esto nunca queda desincronizado de la
    hora real (mismo criterio que "por vencer" en el tablero de muelles)."""
    ahora_dt = datetime.now(_BOG).replace(tzinfo=None)
    hoy = ahora_dt.date()
    ayer = hoy - timedelta(days=1)

    archivo = db.execute(text("""
        SELECT created_at FROM archivos_citas WHERE fecha = :hoy ORDER BY created_at DESC LIMIT 1
    """), {"hoy": hoy.isoformat()}).fetchone()

    # Incluye también las de ayer: una franja que terminaba tarde en la noche
    # más la tolerancia puede seguir vigente después de medianoche.
    rows = db.execute(text("""
        SELECT numero_orden_compra, proveedor_nombre, hora_cita_inicio, hora_cita_fin, tolerancia_min, fecha
        FROM citas_programadas WHERE fecha IN (:hoy, :ayer) AND estado = 'pendiente'
        ORDER BY hora_cita_fin ASC
    """), {"hoy": hoy.isoformat(), "ayer": ayer.isoformat()}).fetchall()

    por_vencer, vencidas, por_iniciar = [], [], []
    for r in rows:
        # datetime completo (fecha+hora), no solo .time(): comparar horas
        # sueltas rompe cuando la franja+tolerancia cruza la medianoche.
        inicio_dt = datetime.combine(r.fecha, r.hora_cita_inicio)
        fin_dt = datetime.combine(r.fecha, r.hora_cita_fin) + timedelta(minutes=r.tolerancia_min or 0)
        item = {
            "numero_orden_compra": r.numero_orden_compra,
            "proveedor_nombre": r.proveedor_nombre,
            "hora_cita_inicio": r.hora_cita_inicio.strftime("%H:%M"),
            "hora_cita_fin": r.hora_cita_fin.strftime("%H:%M"),
        }
        if ahora_dt > fin_dt:
            vencidas.append(item)
        elif (fin_dt - ahora_dt).total_seconds() <= ALERTA_VENCE_MIN * 60:
            por_vencer.append(item)
        if ahora_dt <= inicio_dt and (inicio_dt - ahora_dt).total_seconds() <= ALERTA_INICIO_MIN * 60:
            por_iniciar.append(item)

    return {
        "archivo_hoy": archivo is not None,
        "hora_carga": archivo.created_at.isoformat() if archivo else None,
        "por_vencer": por_vencer,
        "vencidas": vencidas,
        "por_iniciar": por_iniciar,
    }
