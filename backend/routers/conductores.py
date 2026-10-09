# backend/routers/conductores.py
"""Maestro de conductores.

Contrato de permisos (decisión usuaria + Alejandro, 2026-10-08):
  * Lectura (GET): flota.read O conductores.read. El operador tiene flota pero
    no conductores; el guarda peatonal tiene conductores pero no flota.
  * Alta/edición (POST/PUT): conductores.write -> solo guarda_peatonal y admin.
  * Desactivar (DELETE): conductores.delete -> solo admin.
Bodega y vehicular únicamente ELIGEN de la lista; el coordinador es solo lectura.

Contrato para la pantalla del puesto peatonal:
  * GET  /api/conductores?activo=true            lista del maestro
  * GET  /api/conductores?cedula=1.234.567       coincidencia exacta por cédula
         normalizada (solo dígitos); [] si no existe -> avisar duplicado antes de guardar
  * POST /api/conductores   {conductor, n_cedula, celular?, tipo?}
         201 {id, message} | 422 cédula inválida (6-10 dígitos) | 409 cédula duplicada
         | 400 sin nombre | 403 sin permiso
  * PUT  /api/conductores/{id}   mismos campos (parcial) y mismos códigos
  El nombre se guarda en MAYÚSCULAS sin espacios dobles; la cédula, solo dígitos.
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user, require_permiso
from utils_nombres import normalizar_nombre

router = APIRouter()

_RE_CEDULA = re.compile(r"^[0-9]{6,10}$")
_MSG_CEDULA = "La cédula debe tener entre 6 y 10 dígitos (solo números)"
_SQL_CEDULA_NORM = r"regexp_replace(COALESCE(n_cedula, ''), '\D', '', 'g')"


def _puede_leer(current_user: dict = Depends(get_current_user)):
    permisos = current_user.get("permisos") or {}
    if "read" in permisos.get("flota", []) or "read" in permisos.get("conductores", []):
        return current_user
    raise HTTPException(403, "Sin permiso para 'read' en 'conductores'")


def normalizar_cedula(raw):
    """'1.234.567' / 'CC 1234567' -> '1234567'. None/vacío -> None."""
    if raw is None:
        return None
    digitos = re.sub(r"\D", "", str(raw))
    return digitos or None


def _cedula_valida(raw) -> str:
    ced = normalizar_cedula(raw)
    if not ced or not _RE_CEDULA.match(ced):
        raise HTTPException(422, _MSG_CEDULA)
    return ced


def _verificar_cedula_libre(db: Session, cedula: str, excluir_id: str = None):
    sql = f"SELECT id, conductor FROM conductores WHERE {_SQL_CEDULA_NORM} = :ced"
    params = {"ced": cedula}
    if excluir_id:
        sql += " AND id <> CAST(:excluir AS UUID)"
        params["excluir"] = excluir_id
    row = db.execute(text(sql + " LIMIT 1"), params).fetchone()
    if row:
        raise HTTPException(409, f"Ya existe un conductor con la cédula {cedula}: {row.conductor}")


@router.get("")
def listar(
    activo: bool = None,
    q: str = None,
    cedula: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(_puede_leer),
):
    where = ["1=1"]
    params = {}
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = activo
    if q:
        where.append("(conductor ILIKE :q OR CAST(codigo AS TEXT) ILIKE :q OR n_cedula ILIKE :q)")
        params["q"] = f"%{q}%"
    if cedula is not None:
        where.append(f"{_SQL_CEDULA_NORM} = :ced")
        params["ced"] = normalizar_cedula(cedula) or "no-coincide"

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
    _: dict = Depends(_puede_leer),
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
    _: dict = Depends(require_permiso("conductores", "write")),
):
    conductor = normalizar_nombre(body.get("conductor"))
    if not conductor:
        raise HTTPException(400, "El nombre del conductor es requerido")
    cedula = _cedula_valida(body.get("n_cedula"))
    _verificar_cedula_libre(db, cedula)

    rid = str(uuid.uuid4())
    try:
        db.execute(text("""
            INSERT INTO conductores (id, codigo, conductor, n_cedula, celular, tipo, activo, foto_url)
            VALUES (:id, :codigo, :conductor, :cedula, :celular, :tipo, :activo, :foto)
        """), {
            "id": rid,
            "codigo": body.get("codigo"),
            "conductor": conductor,
            "cedula": cedula,
            "celular": body.get("celular"),
            "tipo": body.get("tipo"),
            "activo": body.get("activo", True),
            "foto": body.get("foto_url"),
        })
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "uq_conductores_cedula_norm" in str(e.orig):
            raise HTTPException(409, f"Ya existe un conductor con la cédula {cedula}")
        raise
    return {"id": rid, "message": "Conductor creado"}


@router.put("/{id}")
def actualizar(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("conductores", "write")),
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
    if "conductor" in vals:
        vals["conductor"] = normalizar_nombre(vals["conductor"])
        if not vals["conductor"]:
            raise HTTPException(400, "El nombre del conductor es requerido")
    if "n_cedula" in vals:
        vals["n_cedula"] = _cedula_valida(vals["n_cedula"])
        _verificar_cedula_libre(db, vals["n_cedula"], excluir_id=id)
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    try:
        db.execute(text(f"UPDATE conductores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "uq_conductores_cedula_norm" in str(e.orig):
            raise HTTPException(409, "Ya existe un conductor con esa cédula")
        raise
    return {"message": "Conductor actualizado"}


@router.delete("/{id}")
def eliminar(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("conductores", "delete")),
):
    existe = db.execute(
        text("SELECT 1 FROM conductores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Conductor no encontrado")

    db.execute(text("UPDATE conductores SET activo = FALSE, updated_at = NOW() WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Conductor desactivado"}
