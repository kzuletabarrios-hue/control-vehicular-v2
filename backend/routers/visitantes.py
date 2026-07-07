# backend/routers/visitantes.py
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
    q: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visitantes", "read")),
):
    where = ["1=1"]
    params = {"limit": limit, "offset": offset}
    if fecha:
        where.append("fecha = :fecha")
        params["fecha"] = fecha
    if q:
        where.append("(nombre ILIKE :q OR empresa ILIKE :q OR cedula ILIKE :q)")
        params["q"] = f"%{q}%"

    where_sql = ' AND '.join(where)
    rows = db.execute(text(f"""
        WITH base AS (
            SELECT * FROM visitantes WHERE {where_sql}
        )
        SELECT * FROM base WHERE hora_salida IS NULL
        UNION ALL
        SELECT * FROM (
            SELECT * FROM base WHERE hora_salida IS NOT NULL
            ORDER BY fecha DESC, hora_ingreso DESC
            LIMIT :limit OFFSET :offset
        ) cerrados
        ORDER BY fecha DESC, hora_ingreso DESC
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM visitantes
        WHERE {' AND '.join(where)}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "items": [dict(r._mapping) for r in rows]}


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visitantes", "read")),
):
    row = db.execute(
        text("SELECT * FROM visitantes WHERE id = :id"), {"id": id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    return dict(row._mapping)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("visitantes", "write")),
):
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre del visitante es requerido")

    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO visitantes
            (id, fecha, nombre, cedula, empresa, empresa_pertenece, hora_ingreso, hora_salida, fecha_salida, observaciones, foto_url,
             actividad_a_desarrollar, dependencia_autoriza, creado_por)
        VALUES
            (:id, :fecha, :nombre, :cedula, :empresa, :empresa_pertenece, :hora_ingreso, :hora_salida, :fecha_salida, :observaciones, :foto_url,
             :actividad_a_desarrollar, :dependencia_autoriza, :creado_por)
    """), {
        "id": rid,
        "fecha": body.get("fecha"),
        "nombre": nombre,
        "cedula": body.get("cedula"),
        "empresa": body.get("empresa"),
        "empresa_pertenece": body.get("empresa_pertenece"),
        "hora_ingreso": body.get("hora_ingreso"),
        "hora_salida": body.get("hora_salida"),
        "fecha_salida": body.get("fecha_salida"),
        "observaciones": body.get("observaciones"),
        "foto_url": body.get("foto_url"),
        "actividad_a_desarrollar": body.get("actividad_a_desarrollar"),
        "dependencia_autoriza": body.get("dependencia_autoriza"),
        "creado_por": current_user["id"],
    })
    db.commit()
    return {"id": rid, "message": "Visitante registrado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visitantes", "write")),
):
    existe = db.execute(
        text("SELECT 1 FROM visitantes WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    campos = ["fecha", "nombre", "cedula", "empresa", "empresa_pertenece", "hora_ingreso", "hora_salida", "fecha_salida", "observaciones", "foto_url",
              "actividad_a_desarrollar", "dependencia_autoriza"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE visitantes SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visitantes", "delete")),
):
    existe = db.execute(
        text("SELECT 1 FROM visitantes WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    db.execute(text("DELETE FROM visitantes WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Registro eliminado"}
