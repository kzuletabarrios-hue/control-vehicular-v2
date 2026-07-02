# backend/routers/flota.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import get_current_user, require_permiso

router = APIRouter()


@router.get("")
def listar(
    fecha: str = None,
    placa: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    where = ["1=1"]
    params = {"limit": limit, "offset": offset}
    if fecha:
        where.append("f.fecha = :fecha")
        params["fecha"] = fecha
    if placa:
        where.append("f.placa ILIKE :placa")
        params["placa"] = f"%{placa}%"

    rows = db.execute(text(f"""
        SELECT f.*, c.conductor AS nombre_conductor_bd
        FROM flota_propia f
        LEFT JOIN conductores c ON f.codigo_conductor = c.codigo
        WHERE {' AND '.join(where)}
        ORDER BY f.fecha DESC, f.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM flota_propia f
        WHERE {' AND '.join(where)}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "items": [dict(r._mapping) for r in rows]}


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    row = db.execute(
        text("SELECT * FROM flota_propia WHERE id = :id"), {"id": id}
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    return dict(row._mapping)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("flota", "write")),
):
    import uuid
    rid = str(uuid.uuid4())
    campos = [
        "fecha", "placa", "codigo_conductor", "conductor",
        "n_pallets", "n_contenedores", "cant_volumen_externo", "muelle_cargue",
        "tienda_1", "tienda_2", "tienda_3", "tienda_4", "tienda_5",
        "ultima_tienda", "ultima_tienda_visitada",
        "protocolo", "sello", "tipo_sello", "sello_entrada",
        "hora_salida_muelle", "temperatura", "hora_salida_cedi", "hora_llegada",
        "fecha_salida", "fecha_llegada",
        "observacion", "foto_url",
        "obs_salida", "foto_salida", "obs_llegada", "foto_llegada",
    ]
    vals = {c: body.get(c) for c in campos}
    vals["id"] = rid
    vals["creado_por"] = current_user["id"]

    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    db.execute(text(f"INSERT INTO flota_propia ({cols}) VALUES ({placeholders})"), vals)

    try:
        _audit(db, current_user, "INSERT", "flota_propia", rid, None, vals)
    except Exception:
        pass
    db.commit()
    return {"id": rid, "message": "Registro creado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("flota", "write")),
):
    antes = db.execute(
        text("SELECT * FROM flota_propia WHERE id = :id"), {"id": id}
    ).fetchone()
    if not antes:
        raise HTTPException(404, "Registro no encontrado")

    campos = [
        "fecha", "placa", "codigo_conductor", "conductor",
        "n_pallets", "n_contenedores", "cant_volumen_externo", "muelle_cargue",
        "tienda_1", "tienda_2", "tienda_3", "tienda_4", "tienda_5",
        "ultima_tienda", "ultima_tienda_visitada",
        "protocolo", "sello", "tipo_sello", "sello_entrada",
        "hora_salida_muelle", "temperatura", "hora_salida_cedi", "hora_llegada",
        "fecha_salida", "fecha_llegada",
        "observacion", "foto_url",
        "obs_salida", "foto_salida", "obs_llegada", "foto_llegada",
    ]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE flota_propia SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    try:
        _audit(db, current_user, "UPDATE", "flota_propia", id, dict(antes._mapping), vals)
    except Exception:
        pass
    db.commit()
    return {"message": "Registro actualizado"}


@router.post("/{id}/duplicar", status_code=201)
def duplicar(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("flota", "write")),
):
    import uuid
    from datetime import date
    original = db.execute(
        text("SELECT * FROM flota_propia WHERE id = :id"), {"id": id}
    ).fetchone()
    if not original:
        raise HTTPException(404, "Registro no encontrado")

    d = dict(original._mapping)
    nuevo_id = str(uuid.uuid4())
    d["id"] = nuevo_id
    d["fecha"] = date.today().isoformat()
    d["creado_por"] = current_user["id"]
    d.pop("created_at", None)
    d.pop("updated_at", None)

    cols = ", ".join(d.keys())
    placeholders = ", ".join(f":{k}" for k in d.keys())
    db.execute(text(f"INSERT INTO flota_propia ({cols}) VALUES ({placeholders})"), d)
    _audit(db, current_user, "INSERT", "flota_propia", nuevo_id, None, d)
    db.commit()
    return {"id": nuevo_id, "message": "Registro duplicado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("flota", "delete")),
):
    antes = db.execute(
        text("SELECT * FROM flota_propia WHERE id = :id"), {"id": id}
    ).fetchone()
    if not antes:
        raise HTTPException(404, "Registro no encontrado")

    db.execute(text("DELETE FROM flota_propia WHERE id = :id"), {"id": id})
    try:
        _audit(db, current_user, "DELETE", "flota_propia", id, dict(antes._mapping), None)
    except Exception:
        pass
    db.commit()
    return {"message": "Registro eliminado"}


def _audit(db, user, accion, tabla, rid, antes, despues):
    import json
    db.execute(text("""
        INSERT INTO audit_log (usuario_id, usuario_email, accion, tabla, registro_id, datos_antes, datos_despues)
        VALUES (:uid, :email, :accion, :tabla, :rid, CAST(:antes AS jsonb), CAST(:despues AS jsonb))
    """), {
        "uid": user["id"],
        "email": user["email"],
        "accion": accion,
        "tabla": tabla,
        "rid": str(rid),
        "antes": json.dumps(antes, default=str) if antes else None,
        "despues": json.dumps(despues, default=str) if despues else None,
    })
