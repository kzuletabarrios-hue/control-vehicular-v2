# backend/routers/proveedores.py
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
    empresa: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "read")),
):
    where = ["1=1"]
    params = {"limit": limit, "offset": offset}
    if fecha:
        where.append("fecha = :fecha")
        params["fecha"] = fecha
    if empresa:
        where.append("empresa ILIKE :empresa")
        params["empresa"] = f"%{empresa}%"

    rows = db.execute(text(f"""
        SELECT * FROM proveedores
        WHERE {' AND '.join(where)}
        ORDER BY fecha DESC, created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM proveedores
        WHERE {' AND '.join(where)}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "items": [dict(r._mapping) for r in rows]}


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "read")),
):
    row = db.execute(
        text("SELECT * FROM proveedores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    return dict(row._mapping)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    rid = str(uuid.uuid4())
    campos = [
        "fecha", "placa_vehiculo", "nombre_conductor", "tipo_vehiculo",
        "empresa", "muelle_descargue", "carga_compartida",
        "hora_ingreso", "hora_salida", "actividad_a_desarrollar",
        "dependencia_autoriza", "fecha_pago_arl", "observaciones", "foto_url",
        "fecha_salida",
    ]
    vals = {c: body.get(c) for c in campos}
    vals["id"] = rid
    vals["creado_por"] = current_user["id"]

    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
    db.commit()
    return {"id": rid, "message": "Registro creado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    existe = db.execute(
        text("SELECT 1 FROM proveedores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    campos = [
        "fecha", "placa_vehiculo", "nombre_conductor", "tipo_vehiculo",
        "empresa", "muelle_descargue", "carga_compartida",
        "hora_ingreso", "hora_salida", "actividad_a_desarrollar",
        "dependencia_autoriza", "fecha_pago_arl", "observaciones", "foto_url",
        "fecha_salida",
    ]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE proveedores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "delete")),
):
    existe = db.execute(
        text("SELECT 1 FROM proveedores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    db.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Registro eliminado"}
