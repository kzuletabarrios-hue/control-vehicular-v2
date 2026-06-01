# backend/routers/bd_maestros.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


# ── DISTRIBUCIÓN (tiendas) ────────────────────────────────────────

@router.get("/distribucion")
def listar_distribucion(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    rows = db.execute(text("SELECT * FROM distribucion ORDER BY name ASC")).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/distribucion", status_code=201)
def crear_distribucion(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "El nombre es requerido")
    rid = str(uuid.uuid4())
    db.execute(text("INSERT INTO distribucion (id, name) VALUES (:id, :name)"), {"id": rid, "name": name})
    db.commit()
    return {"id": rid, "message": "Tienda creada"}


@router.delete("/distribucion/{id}")
def eliminar_distribucion(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("DELETE FROM distribucion WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Tienda eliminada"}


# ── BD PROVEEDORES ────────────────────────────────────────────────

@router.get("/proveedores")
def listar_bd_proveedores(
    q: str = None,
    activo: bool = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    where = ["1=1"]
    params = {}
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = activo
    if q:
        where.append("(nombre ILIKE :q OR nit ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM bd_proveedores
        WHERE {' AND '.join(where)}
        ORDER BY nombre ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/proveedores", status_code=201)
def crear_bd_proveedor(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre es requerido")
    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO bd_proveedores (id, nombre, nit, contacto, celular, activo)
        VALUES (:id, :nombre, :nit, :contacto, :celular, :activo)
    """), {
        "id": rid,
        "nombre": nombre,
        "nit": body.get("nit"),
        "contacto": body.get("contacto"),
        "celular": body.get("celular"),
        "activo": body.get("activo", True),
    })
    db.commit()
    return {"id": rid, "message": "Proveedor creado"}


@router.put("/proveedores/{id}")
def actualizar_bd_proveedor(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    campos = ["nombre", "nit", "contacto", "celular", "activo"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE bd_proveedores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Proveedor actualizado"}


@router.delete("/proveedores/{id}")
def eliminar_bd_proveedor(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("UPDATE bd_proveedores SET activo = FALSE, updated_at = NOW() WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Proveedor desactivado"}


# ── BD CONTROL ACCESO ─────────────────────────────────────────────

@router.get("/control-acceso")
def listar_bd_ca(
    q: str = None,
    estado: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    where = ["1=1"]
    params = {}
    if estado:
        where.append("estado = :estado")
        params["estado"] = estado
    if q:
        where.append("(nombre ILIKE :q OR CAST(cedula AS TEXT) ILIKE :q OR contratista ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM bd_control_acceso
        WHERE {' AND '.join(where)}
        ORDER BY nombre ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/control-acceso", status_code=201)
def crear_bd_ca(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    cedula = body.get("cedula")
    nombre = (body.get("nombre") or "").strip()
    if not cedula or not nombre:
        raise HTTPException(400, "Cédula y nombre son requeridos")
    db.execute(text("""
        INSERT INTO bd_control_acceso (cedula, nombre, contratista, estado)
        VALUES (:cedula, :nombre, :contratista, :estado)
        ON CONFLICT (cedula) DO UPDATE SET nombre = EXCLUDED.nombre, contratista = EXCLUDED.contratista
    """), {
        "cedula": int(cedula),
        "nombre": nombre,
        "contratista": body.get("contratista"),
        "estado": body.get("estado", "ACTIVO"),
    })
    db.commit()
    return {"cedula": cedula, "message": "Persona registrada en BD"}


@router.put("/control-acceso/{cedula}")
def actualizar_bd_ca(
    cedula: int,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    campos = ["nombre", "contratista", "estado"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["cedula"] = cedula
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "cedula")
    db.execute(text(f"UPDATE bd_control_acceso SET {sets}, updated_at = NOW() WHERE cedula = :cedula"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.delete("/control-acceso/{cedula}")
def eliminar_bd_ca(
    cedula: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("UPDATE bd_control_acceso SET estado = 'INACTIVO', updated_at = NOW() WHERE cedula = :cedula"), {"cedula": cedula})
    db.commit()
    return {"message": "Persona marcada como inactiva"}
