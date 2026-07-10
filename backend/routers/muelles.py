# backend/routers/muelles.py
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))
ALERTA_MUELLE_MIN = 90  # confirmado con el usuario -- ajustar aquí si hace falta


def _audit(db, user, accion, rid, datos_despues):
    db.execute(text("""
        INSERT INTO audit_log (usuario_id, usuario_email, accion, tabla, registro_id, datos_despues)
        VALUES (:uid, :email, :accion, 'muelle_eventos', :rid, CAST(:despues AS jsonb))
    """), {
        "uid": user["id"], "email": user["email"], "accion": accion,
        "rid": str(rid), "despues": json.dumps(datos_despues, default=str),
    })


@router.get("")
def tablero(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("muelles", "read")),
):
    rows = db.execute(text("""
        SELECT
            m.id, m.numero, m.zona,
            e.id AS evento_id, e.hora_asignado,
            p.id AS proveedor_id, p.placa_vehiculo, p.nombre_conductor,
            (SELECT string_agg(po.empresa, ' · ') FROM proveedores_ordenes po WHERE po.proveedor_id = p.id) AS empresas
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


@router.post("", status_code=201)
def crear_muelle(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("muelles", "write")),
):
    numero = (body.get("numero") or "").strip()
    if not numero:
        raise HTTPException(400, "El número de muelle es obligatorio")
    zona = (body.get("zona") or "").strip() or None

    mid = str(uuid.uuid4())
    try:
        db.execute(
            text("INSERT INTO muelles (id, numero, zona) VALUES (:id, :numero, :zona)"),
            {"id": mid, "numero": numero, "zona": zona},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, f"Ya existe un muelle con el número {numero}")
    return {"id": mid, "message": "Muelle creado"}


@router.delete("/{id}")
def desactivar_muelle(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("muelles", "write")),
):
    ocupado = db.execute(
        text("SELECT 1 FROM muelle_eventos WHERE muelle_id = :id AND hora_liberado IS NULL"), {"id": id}
    ).fetchone()
    if ocupado:
        raise HTTPException(400, "No se puede desactivar un muelle ocupado")
    db.execute(text("UPDATE muelles SET activo = FALSE WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Muelle desactivado"}


@router.post("/{id}/asignar", status_code=201)
def asignar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("muelles", "asignar")),
):
    proveedor_id = (body.get("proveedor_id") or "").strip()
    if not proveedor_id:
        raise HTTPException(400, "Falta el vehículo a asignar")

    muelle = db.execute(text("SELECT numero, activo FROM muelles WHERE id = :id"), {"id": id}).fetchone()
    if not muelle:
        raise HTTPException(404, "Muelle no encontrado")
    if not muelle.activo:
        raise HTTPException(400, "Este muelle está desactivado")

    ocupante = db.execute(text("""
        SELECT p.placa_vehiculo FROM muelle_eventos e
        JOIN proveedores p ON p.id = e.proveedor_id
        WHERE e.muelle_id = :id AND e.hora_liberado IS NULL
    """), {"id": id}).fetchone()
    if ocupante:
        raise HTTPException(409, f"El muelle {muelle.numero} ya se encuentra ocupado por el vehículo {ocupante.placa_vehiculo}.")

    ya_asignado = db.execute(text("""
        SELECT m.numero FROM muelle_eventos e JOIN muelles m ON m.id = e.muelle_id
        WHERE e.proveedor_id = :pid AND e.hora_liberado IS NULL
    """), {"pid": proveedor_id}).fetchone()
    if ya_asignado:
        raise HTTPException(409, f"Este vehículo ya está asignado al muelle {ya_asignado.numero}.")

    eid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO muelle_eventos (id, muelle_id, proveedor_id, asignado_por)
        VALUES (:id, :muelle_id, :proveedor_id, :asignado_por)
    """), {"id": eid, "muelle_id": id, "proveedor_id": proveedor_id, "asignado_por": current_user["id"]})
    try:
        _audit(db, current_user, "ASIGNAR_MUELLE", eid, {"muelle": muelle.numero, "proveedor_id": proveedor_id})
    except Exception:
        pass
    db.commit()
    return {"id": eid, "message": f"Muelle {muelle.numero} asignado"}


@router.post("/{id}/liberar")
def liberar(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("muelles", "liberar")),
):
    evento = db.execute(
        text("SELECT id FROM muelle_eventos WHERE muelle_id = :id AND hora_liberado IS NULL"), {"id": id}
    ).fetchone()
    if not evento:
        raise HTTPException(400, "Este muelle no está ocupado")

    db.execute(text("""
        UPDATE muelle_eventos SET liberado_por = :uid, hora_liberado = NOW() WHERE id = :eid
    """), {"uid": current_user["id"], "eid": evento.id})
    try:
        _audit(db, current_user, "LIBERAR_MUELLE", evento.id, {"muelle_id": id})
    except Exception:
        pass
    db.commit()
    return {"message": "Muelle liberado"}
