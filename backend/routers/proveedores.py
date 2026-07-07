# backend/routers/proveedores.py
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DataError

from database import get_db
from routers.auth import require_permiso, SECRET_KEY, ALGORITHM

router = APIRouter()

CAMPOS_VEHICULO = [
    "fecha", "placa_vehiculo", "nombre_conductor", "tipo_documento", "cedula_conductor",
    "telefono_conductor",
    "tipo_vehiculo", "hora_ingreso", "hora_salida", "fecha_salida",
    "fecha_pago_arl", "arl_proveedor", "epp_cumple",
    "tipo_carga", "formato_carga", "cantidad_pallets", "manejo_carga",
    "observaciones", "foto_url",
    # Legacy columns kept nullable for backward compat
    "empresa", "muelle_descargue", "carga_compartida",
    "actividad_a_desarrollar", "dependencia_autoriza",
]

CAMPOS_ORDEN = [
    "empresa", "carga_compartida",
    "actividad_a_desarrollar", "dependencia_autoriza", "numero_orden_compra",
]

# ── QR de autorregistro de proveedores ────────────────────────────
# Dos tokens con propósitos distintos:
# 1) QR_INGRESO: el que se ve/escanea en pantalla, caduca rápido (evita que una foto
#    guardada del QR sirva para autorregistrarse más tarde).
# 2) SESION_REGISTRO: se emite al validar el QR con éxito (GET /token-info) y es el
#    que realmente se usa para el POST /autorregistro -- dura mucho más, para que el
#    conductor tenga tiempo de llenar el formulario sin que le caduque a mitad.
QR_INGRESO_TIPO    = "ingreso_proveedor_qr"
QR_INGRESO_TTL_SEG = 300  # 5 min: tiempo para escanear el QR y que la pagina valide

SESION_REGISTRO_TIPO    = "ingreso_proveedor_sesion"
SESION_REGISTRO_TTL_SEG = 1800  # 30 min: tiempo para llenar el formulario una vez escaneado


def crear_token_ingreso_qr() -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=QR_INGRESO_TTL_SEG)
    return jwt.encode({"tipo": QR_INGRESO_TIPO, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def validar_token_ingreso_qr(token: str) -> None:
    if not token:
        raise HTTPException(400, "Falta el código de la portería. Escanea el QR nuevamente.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "El código QR expiró. Pide al guarda que muestre el QR actualizado y escanéalo de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Código QR inválido.")
    if payload.get("tipo") != QR_INGRESO_TIPO:
        raise HTTPException(400, "Código QR inválido.")


def crear_token_sesion_registro() -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=SESION_REGISTRO_TTL_SEG)
    return jwt.encode({"tipo": SESION_REGISTRO_TIPO, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def validar_token_sesion_registro(token: str) -> None:
    if not token:
        raise HTTPException(400, "Tu sesión de registro no es válida. Escanea el QR nuevamente.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Tu sesión de registro expiró por inactividad. Pide al guarda que muestre el QR y escanéalo de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Tu sesión de registro no es válida.")
    if payload.get("tipo") != SESION_REGISTRO_TIPO:
        raise HTTPException(400, "Tu sesión de registro no es válida.")


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


# ── QR de autorregistro (portería) ────────────────────────────────
# IMPORTANTE: debe ir ANTES de /{id} (GET) — si no, FastAPI captura
# "qr-imagen" como si fuera un id y esta ruta queda inalcanzable.

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://control-vehicular-v2.vercel.app")


@router.get("/qr-imagen")
def qr_imagen(
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        raise HTTPException(500, "Librería qrcode no instalada en el servidor")

    token = crear_token_ingreso_qr()
    url = f"{FRONTEND_URL}/?ingreso_proveedor=1&token={token}"
    img = qrcode.make(url, image_factory=SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


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


import re as _re
_FECHA_RE = _re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def fecha_valida(v) -> bool:
    """Espejo del fechaValida() del frontend: YYYY-MM-DD con año 2000-2100."""
    if not v:
        return True
    m = _FECHA_RE.match(str(v))
    if not m:
        return False
    anio = int(m.group(1))
    return 2000 <= anio <= 2100


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
    # El registro creado directamente por un guarda ya queda con ingreso
    # autorizado de inmediato (estado_confirmacion='confirmado' por defecto).
    vals["hora_ingreso_confirmado"] = vals.get("hora_ingreso")
    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    try:
        db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
        _insert_ordenes(db, rid, ordenes)
        db.commit()
    except (IntegrityError, DataError):
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa las fechas y los campos de selección (tipo de documento, tipo/formato de carga, quién maneja la carga).")
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
    try:
        db.execute(text(f"UPDATE proveedores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
        db.commit()
    except (IntegrityError, DataError):
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa las fechas y los campos de selección (tipo de documento, tipo/formato de carga, quién maneja la carga).")
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


@router.put("/{id}/confirmar")
def confirmar_autorregistro(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    row = db.execute(text("SELECT estado_confirmacion FROM proveedores WHERE id = :id"), {"id": id}).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    if row.estado_confirmacion == "confirmado":
        raise HTTPException(409, "Este registro ya estaba confirmado")
    _BOG = timezone(timedelta(hours=-5))
    hora = datetime.now(_BOG).strftime("%H:%M:%S")
    db.execute(
        text("""
            UPDATE proveedores
            SET estado_confirmacion = 'confirmado', hora_ingreso_confirmado = :hora, updated_at = NOW()
            WHERE id = :id
        """),
        {"id": id, "hora": hora},
    )
    db.commit()
    return {"message": "Ingreso confirmado"}


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
    try:
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
    except (IntegrityError, DataError):
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa las fechas y los campos de selección (tipo de documento, tipo/formato de carga, quién maneja la carga).")
    return {"ids": ids, "message": f"{len(ids)} registros creados"}
