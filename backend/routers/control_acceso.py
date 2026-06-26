# backend/routers/control_acceso.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


# ── SUSTANCIAS ────────────────────────────────────────────────────

@router.get("/sustancias")
def listar_sustancias(
    fecha: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "read")),
):
    where = ["1=1"]
    params = {}
    if fecha:
        where.append("fecha = :fecha")
        params["fecha"] = fecha
    rows = db.execute(text(f"SELECT * FROM sustancias WHERE {' AND '.join(where)} ORDER BY fecha DESC, created_at DESC LIMIT 100"), params).fetchall()
    return [dict(r._mapping) for r in rows]

@router.post("/sustancias", status_code=201)
def crear_sustancia(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("control_acceso", "write")),
):
    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO sustancias (id, fecha, descripcion, cantidad, responsable, observaciones, foto_url, creado_por)
        VALUES (:id, :fecha, :descripcion, :cantidad, :responsable, :observaciones, :foto_url, :creado_por)
    """), {
        "id": rid, "fecha": body.get("fecha"), "descripcion": body.get("descripcion"),
        "cantidad": body.get("cantidad"), "responsable": body.get("responsable"),
        "observaciones": body.get("observaciones"), "foto_url": body.get("foto_url"),
        "creado_por": current_user["id"],
    })
    db.commit()
    return {"id": rid, "message": "Sustancia registrada"}

@router.put("/sustancias/{id}")
def actualizar_sustancia(
    id: str, body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "write")),
):
    campos = ["fecha", "descripcion", "cantidad", "responsable", "observaciones", "foto_url"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos")
    vals["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE sustancias SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Actualizado"}

@router.delete("/sustancias/{id}")
def eliminar_sustancia(
    id: str, db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "delete")),
):
    db.execute(text("DELETE FROM sustancias WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Eliminado"}


# ── HERRAMIENTAS ───────────────────────────────────────────────────

@router.get("/herramientas")
def listar_herramientas(
    fecha: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "read")),
):
    where = ["1=1"]
    params = {}
    if fecha:
        where.append("fecha = :fecha")
        params["fecha"] = fecha
    rows = db.execute(text(f"SELECT * FROM herramientas WHERE {' AND '.join(where)} ORDER BY fecha DESC, created_at DESC LIMIT 100"), params).fetchall()
    return [dict(r._mapping) for r in rows]

@router.post("/herramientas", status_code=201)
def crear_herramienta(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("control_acceso", "write")),
):
    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO herramientas (id, fecha, descripcion, cantidad, responsable, observaciones, foto_url, creado_por)
        VALUES (:id, :fecha, :descripcion, :cantidad, :responsable, :observaciones, :foto_url, :creado_por)
    """), {
        "id": rid, "fecha": body.get("fecha"), "descripcion": body.get("descripcion"),
        "cantidad": body.get("cantidad"), "responsable": body.get("responsable"),
        "observaciones": body.get("observaciones"), "foto_url": body.get("foto_url"),
        "creado_por": current_user["id"],
    })
    db.commit()
    return {"id": rid, "message": "Herramienta registrada"}

@router.put("/herramientas/{id}")
def actualizar_herramienta(
    id: str, body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "write")),
):
    campos = ["fecha", "descripcion", "cantidad", "responsable", "observaciones", "foto_url"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos")
    vals["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE herramientas SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Actualizado"}

@router.delete("/herramientas/{id}")
def eliminar_herramienta(
    id: str, db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "delete")),
):
    db.execute(text("DELETE FROM herramientas WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Eliminado"}


# ── BD MAESTRO ────────────────────────────────────────────────────

@router.get("/bd/buscar")
def buscar_bd(
    q: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "read")),
):
    rows = db.execute(text("""
        SELECT * FROM bd_control_acceso
        WHERE nombre ILIKE :q OR CAST(cedula AS TEXT) ILIKE :q OR contratista ILIKE :q
        ORDER BY nombre ASC LIMIT 20
    """), {"q": f"%{q}%"}).fetchall()
    return [dict(r._mapping) for r in rows]


# ── CONTROL ACCESO PERSONAS ───────────────────────────────────────

@router.get("")
def listar(
    fecha: str = None,
    q: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "read")),
):
    where = ["1=1"]
    params = {"limit": limit, "offset": offset}
    if fecha:
        where.append("ca.fecha = :fecha")
        params["fecha"] = fecha
    if q:
        where.append("(ca.nombre ILIKE :q OR ca.contratista ILIKE :q OR CAST(ca.cedula AS TEXT) ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT ca.*, b.estado AS estado_bd
        FROM control_acceso ca
        LEFT JOIN bd_control_acceso b ON ca.cedula = b.cedula
        WHERE {' AND '.join(where)}
        ORDER BY ca.fecha DESC, ca.hora_ingreso DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM control_acceso ca
        WHERE {' AND '.join(where)}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "items": [dict(r._mapping) for r in rows]}


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "read")),
):
    row = db.execute(
        text("SELECT * FROM control_acceso WHERE id = :id"), {"id": id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    return dict(row._mapping)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("control_acceso", "write")),
):
    rid = str(uuid.uuid4())
    cedula = body.get("cedula")
    if cedula:
        existe_en_bd = db.execute(
            text("SELECT 1 FROM bd_control_acceso WHERE cedula = :c"), {"c": cedula}
        ).fetchone()
        if not existe_en_bd:
            cedula = None
    vals = {
        "id": rid,
        "fecha": body.get("fecha"),
        "cedula": cedula,
        "nombre": body.get("nombre"),
        "contratista": body.get("contratista"),
        "hora_ingreso": body.get("hora_ingreso"),
        "hora_salida": body.get("hora_salida"),
        "fecha_salida": body.get("fecha_salida"),
        "observaciones": body.get("observaciones"),
        "foto_url": body.get("foto_url"),
        "creado_por": current_user["id"],
    }
    db.execute(text("""
        INSERT INTO control_acceso
            (id, fecha, cedula, nombre, contratista, hora_ingreso, hora_salida, fecha_salida, observaciones, foto_url, creado_por)
        VALUES
            (:id, :fecha, :cedula, :nombre, :contratista, :hora_ingreso, :hora_salida, :fecha_salida, :observaciones, :foto_url, :creado_por)
    """), vals)
    db.commit()
    return {"id": rid, "message": "Registro creado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "write")),
):
    existe = db.execute(
        text("SELECT 1 FROM control_acceso WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    campos = ["fecha", "cedula", "nombre", "contratista", "hora_ingreso", "hora_salida", "fecha_salida", "observaciones", "foto_url"]
    vals = {c: body[c] for c in campos if c in body}
    if "cedula" in vals and vals["cedula"]:
        existe_en_bd = db.execute(
            text("SELECT 1 FROM bd_control_acceso WHERE cedula = :c"), {"c": vals["cedula"]}
        ).fetchone()
        if not existe_en_bd:
            del vals["cedula"]
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE control_acceso SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "delete")),
):
    existe = db.execute(
        text("SELECT 1 FROM control_acceso WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    db.execute(text("DELETE FROM control_acceso WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Registro eliminado"}
