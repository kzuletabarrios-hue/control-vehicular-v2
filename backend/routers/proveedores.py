# backend/routers/proveedores.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

CAMPOS_VEHICULO = [
    "fecha", "placa_vehiculo", "nombre_conductor", "cedula_conductor",
    "telefono_conductor",
    "tipo_vehiculo", "hora_ingreso", "hora_salida", "fecha_salida",
    "fecha_pago_arl", "observaciones", "foto_url",
    # Legacy columns kept nullable for backward compat
    "empresa", "muelle_descargue", "carga_compartida",
    "actividad_a_desarrollar", "dependencia_autoriza",
]

CAMPOS_ORDEN = [
    "empresa", "carga_compartida",
    "actividad_a_desarrollar", "dependencia_autoriza",
]


def _attach_ordenes(db, items: list[dict]) -> list[dict]:
    if not items:
        return items
    ids = [r["id"] for r in items]
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": v for i, v in enumerate(ids)}
    rows = db.execute(
        text(f"""
            SELECT * FROM proveedores_ordenes
            WHERE proveedor_id IN ({placeholders})
            ORDER BY proveedor_id, created_at
        """),
        params,
    ).fetchall()
    ordenes_map: dict[str, list] = {}
    for o in rows:
        od = dict(o._mapping)
        ordenes_map.setdefault(str(od["proveedor_id"]), []).append(od)
    for item in items:
        item["ordenes"] = ordenes_map.get(str(item["id"]), [])
    return items


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
    params: dict = {"limit": limit, "offset": offset}
    if fecha:
        where.append("p.fecha = :fecha")
        params["fecha"] = fecha
    if empresa:
        where.append(
            "EXISTS (SELECT 1 FROM proveedores_ordenes po "
            "WHERE po.proveedor_id = p.id AND po.empresa ILIKE :empresa)"
        )
        params["empresa"] = f"%{empresa}%"

    cond = " AND ".join(where)
    rows = db.execute(
        text(f"""
            SELECT p.* FROM proveedores p
            WHERE {cond}
            ORDER BY p.fecha DESC, p.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()

    total = db.execute(
        text(f"SELECT COUNT(*) FROM proveedores p WHERE {cond}"),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    ).scalar()

    items = [dict(r._mapping) for r in rows]
    _attach_ordenes(db, items)
    return {"total": total, "items": items}


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
    item = dict(row._mapping)
    _attach_ordenes(db, [item])
    return item


def _clean(v):
    return None if v == "" else v


def _insert_ordenes(db, proveedor_id: str, ordenes: list[dict]):
    for orden in ordenes:
        oid = str(uuid.uuid4())
        ovals = {c: _clean(orden.get(c)) for c in CAMPOS_ORDEN}
        ovals["id"] = oid
        ovals["proveedor_id"] = proveedor_id
        ocols = ", ".join(ovals.keys())
        opholds = ", ".join(f":{k}" for k in ovals.keys())
        db.execute(text(f"INSERT INTO proveedores_ordenes ({ocols}) VALUES ({opholds})"), ovals)


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    vehiculo = body.get("vehiculo") or body
    ordenes = body.get("ordenes", [])

    rid = str(uuid.uuid4())
    vals = {c: _clean(vehiculo.get(c)) for c in CAMPOS_VEHICULO}
    vals["id"] = rid
    vals["creado_por"] = current_user["id"]
    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
    _insert_ordenes(db, rid, ordenes)
    db.commit()
    return {"id": rid, "message": "Registro creado"}


@router.post("/{id}/ordenes", status_code=201)
def agregar_orden(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    if not db.execute(text("SELECT 1 FROM proveedores WHERE id = :id"), {"id": id}).fetchone():
        raise HTTPException(404, "Registro no encontrado")
    oid = str(uuid.uuid4())
    ovals = {c: body.get(c) for c in CAMPOS_ORDEN}
    ovals["id"] = oid
    ovals["proveedor_id"] = id
    ocols = ", ".join(ovals.keys())
    opholds = ", ".join(f":{k}" for k in ovals.keys())
    db.execute(text(f"INSERT INTO proveedores_ordenes ({ocols}) VALUES ({opholds})"), ovals)
    db.commit()
    return {"id": oid, "message": "Orden agregada"}


@router.put("/{id}/ordenes/{oid}")
def actualizar_orden(
    id: str,
    oid: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    if not db.execute(
        text("SELECT 1 FROM proveedores_ordenes WHERE id = :oid AND proveedor_id = :pid"),
        {"oid": oid, "pid": id},
    ).fetchone():
        raise HTTPException(404, "Orden no encontrada")
    vals = {c: body[c] for c in CAMPOS_ORDEN if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["oid"] = oid
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "oid")
    db.execute(text(f"UPDATE proveedores_ordenes SET {sets} WHERE id = :oid"), vals)
    db.commit()
    return {"message": "Orden actualizada"}


@router.delete("/{id}/ordenes/{oid}")
def eliminar_orden(
    id: str,
    oid: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "delete")),
):
    db.execute(
        text("DELETE FROM proveedores_ordenes WHERE id = :oid AND proveedor_id = :pid"),
        {"oid": oid, "pid": id},
    )
    db.commit()
    return {"message": "Orden eliminada"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    if not db.execute(text("SELECT 1 FROM proveedores WHERE id = :id"), {"id": id}).fetchone():
        raise HTTPException(404, "Registro no encontrado")
    vals = {c: body[c] for c in CAMPOS_VEHICULO if c in body}
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
    if not db.execute(text("SELECT 1 FROM proveedores WHERE id = :id"), {"id": id}).fetchone():
        raise HTTPException(404, "Registro no encontrado")
    db.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Registro eliminado"}


# ── Legacy batch endpoint (kept for backward compat) ──────────────────────────
@router.post("/batch", status_code=201)
def crear_batch(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    registros = body.get("registros", [])
    if not registros:
        raise HTTPException(400, "Sin registros para guardar")

    ids = []
    for reg in registros:
        rid = str(uuid.uuid4())
        vals = {c: _clean(reg.get(c)) for c in CAMPOS_VEHICULO}
        vals["id"] = rid
        vals["creado_por"] = current_user["id"]
        cols = ", ".join(vals.keys())
        placeholders = ", ".join(f":{k}" for k in vals.keys())
        db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
        orden_data = {c: reg.get(c) for c in CAMPOS_ORDEN}
        if any(v for v in orden_data.values()):
            _insert_ordenes(db, rid, [orden_data])
        ids.append(rid)

    db.commit()
    return {"ids": ids, "message": f"{len(ids)} registros creados"}
