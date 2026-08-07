# backend/routers/muelles.py
#
# Fase 2 (solo lectura) del plan de consolidación con citas-muelles-cedi-r10.
# Decisión del arquitecto: este router expone ÚNICAMENTE el tablero de
# muelles en modo lectura. NO se agrega crear/asignar/liberar aquí -- los
# roles que hoy hacen esas operaciones (guarda_bodega, guarda_peatonal,
# guarda_vehicular) no existen todavía en este backend, y escribir sobre
# muelles/muelle_eventos desde dos apps distintas abriría una segunda vía
# de modificar el mismo estado operativo que ya gestiona citas-muelles-
# cedi-r10 en producción. Esa fase queda pendiente y explícita a futuro.
#
# Query réplica exacta de la de referencia en
# C:\citas-muelles-cedi-r10\backend\routers\muelles.py (función tablero()).
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))
ALERTA_MUELLE_MIN = 90  # mismo umbral que citas-muelles-cedi-r10


@router.get("")
def tablero(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("muelles", "read")),
):
    rows = db.execute(text("""
        SELECT
            m.id, m.numero, m.zona, m.tipo_carga_habitual,
            e.id AS evento_id, e.hora_asignado,
            p.id AS proveedor_id, p.placa_vehiculo, p.nombre_conductor, p.tipo_carga,
            (SELECT string_agg(
                po.empresa || CASE WHEN po.numero_orden_compra IS NOT NULL THEN ' (OC ' || po.numero_orden_compra || ')' ELSE '' END,
                ' · '
            ) FROM proveedores_ordenes po WHERE po.proveedor_id = p.id) AS empresas
        FROM muelles m
        LEFT JOIN muelle_eventos e ON e.muelle_id = m.id AND e.hora_liberado IS NULL
        LEFT JOIN proveedores p ON p.id = e.proveedor_id
        WHERE m.activo = TRUE
        ORDER BY m.numero
    """)).fetchall()

    ahora = datetime.now(_BOG)
    items = []
    for r in rows:
        d = dict(r._mapping)
        d["estado"] = "ocupado" if d["evento_id"] else "libre"
        if d["evento_id"]:
            minutos = int((ahora - d["hora_asignado"]).total_seconds() // 60)
            d["minutos_ocupado"] = minutos
            d["alerta_tiempo"] = minutos >= ALERTA_MUELLE_MIN
        items.append(d)
    return items
