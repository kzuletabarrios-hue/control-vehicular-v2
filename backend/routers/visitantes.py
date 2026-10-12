# backend/routers/visitantes.py
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso
from validaciones_registro import (
    BOG,
    validar_texto_obligatorio,
    validar_fecha,
    validar_hora,
)

router = APIRouter()

# ── VALIDACIÓN DE REGISTROS DE VISITANTES ─────────────────────────
# Obligatorios al CREAR (observaciones sigue opcional). Los mensajes son los
# mismos que muestra VisitantesPage.js antes de enviar.
MSG_NOMBRE = "El nombre del visitante es requerido"
MSG_CEDULA = ("La cédula o documento es obligatoria: mínimo 5 caracteres entre letras y números "
              "(se permite guion), sin espacios")
MSG_EMPRESA_PERTENECE = "La empresa a la que pertenece es obligatoria (escribe «Particular» si no pertenece a ninguna)"
MSG_EMPRESA = "Indica a quién visita o la dependencia"
MSG_ACTIVIDAD = "La actividad a desarrollar es obligatoria"
MSG_AUTORIZA = "Indica quién autoriza la visita"

# campo -> mensaje (texto libre obligatorio, además de cedula)
_OBLIGATORIOS_TEXTO = {
    "nombre": MSG_NOMBRE,
    "empresa_pertenece": MSG_EMPRESA_PERTENECE,
    "empresa": MSG_EMPRESA,
    "actividad_a_desarrollar": MSG_ACTIVIDAD,
    "dependencia_autoriza": MSG_AUTORIZA,
}
_RE_CEDULA = re.compile(r"[A-Za-z0-9-]+")


def _validar_cedula(valor) -> str:
    """Documento alfanumérico (cédula o pasaporte): sin espacios a los lados
    (se recortan), solo letras/números/guion y al menos 5 alfanuméricos."""
    if not isinstance(valor, str):
        raise HTTPException(400, MSG_CEDULA)
    t = valor.strip()
    if not _RE_CEDULA.fullmatch(t) or sum(c.isalnum() for c in t) < 5:
        raise HTTPException(400, MSG_CEDULA)
    return t


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
    nombre = validar_texto_obligatorio(body.get("nombre"), MSG_NOMBRE)
    cedula = _validar_cedula(body.get("cedula"))
    textos = {c: validar_texto_obligatorio(body.get(c), m)
              for c, m in _OBLIGATORIOS_TEXTO.items() if c != "nombre"}

    ahora = datetime.now(BOG)
    fecha = validar_fecha(body.get("fecha"), "fecha") or ahora.strftime("%Y-%m-%d")
    hora_ingreso = validar_hora(body.get("hora_ingreso"), "hora_ingreso") or ahora.strftime("%H:%M")
    hora_salida = validar_hora(body.get("hora_salida"), "hora_salida")
    fecha_salida = validar_fecha(body.get("fecha_salida"), "fecha_salida")

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
        "fecha": fecha,
        "nombre": nombre,
        "cedula": cedula,
        "empresa": textos["empresa"],
        "empresa_pertenece": textos["empresa_pertenece"],
        "hora_ingreso": hora_ingreso,
        "hora_salida": hora_salida,
        "fecha_salida": fecha_salida,
        "observaciones": body.get("observaciones"),
        "foto_url": body.get("foto_url"),
        "actividad_a_desarrollar": textos["actividad_a_desarrollar"],
        "dependencia_autoriza": textos["dependencia_autoriza"],
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
        text("SELECT cedula FROM visitantes WHERE id = :id"), {"id": id}
    ).fetchone()
    if not existe:
        raise HTTPException(404, "Registro no encontrado")

    campos = ["fecha", "nombre", "cedula", "empresa", "empresa_pertenece", "hora_ingreso", "hora_salida", "fecha_salida", "observaciones", "foto_url",
              "actividad_a_desarrollar", "dependencia_autoriza"]
    vals = {c: body[c] for c in campos if c in body}

    # Solo se valida lo que el body trae: el botón "Salida" manda únicamente
    # hora/fecha de salida (y a veces observaciones/foto) y debe funcionar
    # también en históricos con campos vacíos. Los obligatorios no se pueden
    # vaciar; la cédula se valida solo si cambia (un histórico con un documento
    # corto no queda bloqueado al editar otros campos).
    for c, m in _OBLIGATORIOS_TEXTO.items():
        if c in vals:
            vals[c] = validar_texto_obligatorio(vals[c], m)
    if "cedula" in vals:
        actual = (existe.cedula or "").strip()
        v = vals["cedula"]
        if isinstance(v, str) and actual and v.strip() == actual:
            vals["cedula"] = actual
        else:
            vals["cedula"] = _validar_cedula(v)
    if "fecha" in vals:
        vals["fecha"] = validar_fecha(vals["fecha"], "fecha")
        if vals["fecha"] is None:  # columna NOT NULL
            raise HTTPException(400, "fecha: es obligatoria")
    if "fecha_salida" in vals:
        vals["fecha_salida"] = validar_fecha(vals["fecha_salida"], "fecha_salida")
    if "hora_ingreso" in vals:
        vals["hora_ingreso"] = validar_hora(vals["hora_ingreso"], "hora_ingreso")
    if "hora_salida" in vals:
        vals["hora_salida"] = validar_hora(vals["hora_salida"], "hora_salida")
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
