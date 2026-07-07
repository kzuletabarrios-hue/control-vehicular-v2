# backend/routers/visita_vehicular.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


@router.get("")
def listar(
    fecha: str = None,
    placa: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visita_vehicular", "read")),
):
    where = ["1=1"]
    params = {"limit": limit, "offset": offset}
    if fecha:
        where.append("fecha = :fecha")
        params["fecha"] = fecha
    if placa:
        where.append("placa ILIKE :placa")
        params["placa"] = f"%{placa}%"

    rows = db.execute(text(f"""
        SELECT * FROM visita_vehicular
        WHERE {' AND '.join(where)}
        ORDER BY fecha DESC, created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM visita_vehicular
        WHERE {' AND '.join(where)}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "items": [dict(r._mapping) for r in rows]}


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visita_vehicular", "read")),
):
    row = db.execute(
        text("SELECT * FROM visita_vehicular WHERE id = :id"), {"id": id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    return dict(row._mapping)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("visita_vehicular", "write")),
):
    if not body.get("placa") or not body.get("conductor"):
        raise HTTPException(400, "Placa y conductor son obligatorios")

    rid = str(uuid.uuid4())
    campos = [
        "fecha", "placa", "conductor", "motivo_visita",
        "empresa_pertenece", "dependencia_autoriza",
        "hora_ingreso", "hora_salida", "fecha_salida", "observaciones", "foto_url",
    ]
    vals = {c: body.get(c) for c in campos}
    vals["id"] = rid
    vals["creado_por"] = current_user["id"]

    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    db.execute(text(f"INSERT INTO visita_vehicular ({cols}) VALUES ({placeholders})"), vals)
    db.commit()
    return {"id": rid, "message": "Registro creado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visita_vehicular", "write")),
):
    existe = db.execute(
        text("SELECT 1 FROM visita_vehicular WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    campos = [
        "fecha", "placa", "conductor", "motivo_visita",
        "empresa_pertenece", "dependencia_autoriza",
        "hora_ingreso", "hora_salida", "fecha_salida", "observaciones", "foto_url",
    ]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE visita_vehicular SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visita_vehicular", "delete")),
):
    existe = db.execute(
        text("SELECT 1 FROM visita_vehicular WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    db.execute(text("DELETE FROM visita_vehicular WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Registro eliminado"}
