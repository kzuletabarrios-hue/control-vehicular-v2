# backend/routers/conductores.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


@router.get("")
def listar(
    activo: bool = None,
    q: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    where = ["1=1"]
    params = {}
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = activo
    if q:
        where.append("(conductor ILIKE :q OR CAST(codigo AS TEXT) ILIKE :q OR n_cedula ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM conductores
        WHERE {' AND '.join(where)}
        ORDER BY conductor ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    row = db.execute(
        text("SELECT * FROM conductores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Conductor no encontrado")
    return dict(row._mapping)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "write")),
):
    conductor = body.get("conductor", "").strip()
    if not conductor:
        raise HTTPException(400, "El nombre del conductor es requerido")

    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO conductores (id, codigo, conductor, n_cedula, celular, tipo, activo, foto_url)
        VALUES (:id, :codigo, :conductor, :cedula, :celular, :tipo, :activo, :foto)
    """), {
        "id": rid,
        "codigo": body.get("codigo"),
        "conductor": conductor,
        "cedula": body.get("n_cedula"),
        "celular": body.get("celular"),
        "tipo": body.get("tipo"),
        "activo": body.get("activo", True),
        "foto": body.get("foto_url"),
    })
    db.commit()
    return {"id": rid, "message": "Conductor creado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "write")),
):
    existe = db.execute(
        text("SELECT 1 FROM conductores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Conductor no encontrado")

    campos = ["codigo", "conductor", "n_cedula", "celular", "tipo", "activo", "foto_url"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE conductores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Conductor actualizado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "delete")),
):
    existe = db.execute(
        text("SELECT 1 FROM conductores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Conductor no encontrado")

    db.execute(text("UPDATE conductores SET activo = FALSE, updated_at = NOW() WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Conductor desactivado"}
