# backend/routers/control_acceso.py
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


# ── ANULACIÓN: modelo de entrada y helpers de traducción de errores ─
class AnularBody(BaseModel):
    motivo: str

    @field_validator("motivo")
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("El motivo de anulación es obligatorio")
        return v


def _mensaje_error_pg(e: DBAPIError) -> str:
    """Extrae el texto legible que la función fn_control_acceso_anular
    manda vía RAISE EXCEPTION, sin el ruido de CONTEXT/DETAIL que
    psycopg2 concatena en str(e.orig)."""
    orig = getattr(e, "orig", None)
    diag = getattr(orig, "diag", None)
    msg = getattr(diag, "message_primary", None) if diag else None
    if msg:
        return msg
    return str(orig or e).split("\n")[0].strip()


def _codigo_http_anulacion(mensaje: str) -> int:
    m = mensaje.lower()
    if "no encontrado" in m:
        return 404
    if "no tiene el permiso" in m:
        return 403
    # "ya está anulado", "fuera de la ventana" y "motivo ... obligatorio"
    # (esta última es defensa en profundidad: Pydantic ya la bloquea antes).
    return 400


# ── VALIDACIÓN DE REGISTROS DE PERSONAS ───────────────────────────
# Misma zona horaria fija que usan dashboard.py, export.py y /api/tiempo
# (Bogotá = UTC-5, sin DST).
_BOG = timezone(timedelta(hours=-5))
_BIGINT_MAX = 9223372036854775807
_RE_CEDULA = re.compile(r"[0-9]+")
_RE_HORA = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?")

MSG_CEDULA = "La cédula es obligatoria y debe ser un número válido mayor que cero"
MSG_NOMBRE = "El nombre es obligatorio"
MSG_CONTRATISTA = "Selecciona un contratista"


def _validar_cedula(valor) -> int:
    """Cédula numérica, positiva y dentro de BIGINT (acepta str o int)."""
    if isinstance(valor, bool):
        raise HTTPException(400, MSG_CEDULA)
    if isinstance(valor, int):
        n = valor
    elif isinstance(valor, str):
        t = valor.strip()
        if not _RE_CEDULA.fullmatch(t):
            raise HTTPException(400, MSG_CEDULA)
        n = int(t)
    else:
        raise HTTPException(400, MSG_CEDULA)
    if n <= 0 or n > _BIGINT_MAX:
        raise HTTPException(400, MSG_CEDULA)
    return n


def _validar_texto_obligatorio(valor, mensaje: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise HTTPException(400, mensaje)
    return valor.strip()


def _validar_fecha(valor, campo: str):
    """None/'' -> None. Formato YYYY-MM-DD o 400."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str) and len(valor) == 10:
        try:
            date.fromisoformat(valor)
            return valor
        except ValueError:
            pass
    raise HTTPException(400, f"{campo}: fecha inválida, use el formato AAAA-MM-DD")


def _validar_hora(valor, campo: str):
    """None/'' -> None. Formato HH:MM o HH:MM:SS o 400."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str) and _RE_HORA.fullmatch(valor):
        return valor
    raise HTTPException(400, f"{campo}: hora inválida, use el formato HH:MM")


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
        INSERT INTO sustancias (id, fecha, descripcion, cantidad, responsable, hora_salida, fecha_salida, observaciones, foto_url, es_consumible, creado_por)
        VALUES (:id, :fecha, :descripcion, :cantidad, :responsable, :hora_salida, :fecha_salida, :observaciones, :foto_url, :es_consumible, :creado_por)
    """), {
        "id": rid, "fecha": body.get("fecha"), "descripcion": body.get("descripcion"),
        "cantidad": body.get("cantidad"), "responsable": body.get("responsable"),
        "hora_salida": body.get("hora_salida"), "fecha_salida": body.get("fecha_salida"),
        "observaciones": body.get("observaciones"), "foto_url": body.get("foto_url"),
        "es_consumible": bool(body.get("es_consumible")),
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
    campos = ["fecha", "descripcion", "cantidad", "responsable", "hora_salida", "fecha_salida", "observaciones", "foto_url", "es_consumible"]
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
        INSERT INTO herramientas (id, fecha, descripcion, cantidad, responsable, hora_salida, fecha_salida, observaciones, foto_url, es_consumible, creado_por)
        VALUES (:id, :fecha, :descripcion, :cantidad, :responsable, :hora_salida, :fecha_salida, :observaciones, :foto_url, :es_consumible, :creado_por)
    """), {
        "id": rid, "fecha": body.get("fecha"), "descripcion": body.get("descripcion"),
        "cantidad": body.get("cantidad"), "responsable": body.get("responsable"),
        "hora_salida": body.get("hora_salida"), "fecha_salida": body.get("fecha_salida"),
        "observaciones": body.get("observaciones"), "foto_url": body.get("foto_url"),
        "es_consumible": bool(body.get("es_consumible")),
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
    campos = ["fecha", "descripcion", "cantidad", "responsable", "hora_salida", "fecha_salida", "observaciones", "foto_url", "es_consumible"]
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
    incluir_anulados: bool = False,
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
    if not incluir_anulados:
        # Por defecto los anulados no se mezclan en el listado operativo.
        # Cubierto por el índice parcial idx_ca_activos_fecha (fecha DESC,
        # hora_ingreso DESC) WHERE anulado = FALSE.
        where.append("ca.anulado = FALSE")

    where_sql = ' AND '.join(where)
    rows = db.execute(text(f"""
        WITH base AS (
            SELECT ca.*, b.estado AS estado_bd
            FROM control_acceso ca
            LEFT JOIN bd_control_acceso b ON ca.cedula = b.cedula
            WHERE {where_sql}
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
    # La cédula se guarda aunque la persona no esté en bd_control_acceso
    # (sin FK desde la migración 20261011120000): el listado la marca con
    # estado_bd NULL para que el coordinador la dé de alta en el maestro.
    cedula = _validar_cedula(body.get("cedula"))
    nombre = _validar_texto_obligatorio(body.get("nombre"), MSG_NOMBRE)
    contratista = _validar_texto_obligatorio(body.get("contratista"), MSG_CONTRATISTA)

    ahora = datetime.now(_BOG)
    fecha = _validar_fecha(body.get("fecha"), "fecha") or ahora.strftime("%Y-%m-%d")
    hora_ingreso = _validar_hora(body.get("hora_ingreso"), "hora_ingreso") or ahora.strftime("%H:%M")
    hora_salida = _validar_hora(body.get("hora_salida"), "hora_salida")
    fecha_salida = _validar_fecha(body.get("fecha_salida"), "fecha_salida")

    rid = str(uuid.uuid4())
    vals = {
        "id": rid,
        "fecha": fecha,
        "cedula": cedula,
        "nombre": nombre,
        "contratista": contratista,
        "hora_ingreso": hora_ingreso,
        "hora_salida": hora_salida,
        "fecha_salida": fecha_salida,
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

    # Solo se valida lo que el body trae: el botón "Salida" manda
    # únicamente hora/fecha de salida y debe funcionar también en
    # registros históricos sin cédula. Cédula y nombre no se pueden vaciar.
    if "cedula" in vals:
        vals["cedula"] = _validar_cedula(vals["cedula"])
    if "nombre" in vals:
        vals["nombre"] = _validar_texto_obligatorio(vals["nombre"], MSG_NOMBRE)
    if "fecha" in vals:
        vals["fecha"] = _validar_fecha(vals["fecha"], "fecha")
        if vals["fecha"] is None:  # columna NOT NULL
            raise HTTPException(400, "fecha: es obligatoria")
    if "fecha_salida" in vals:
        vals["fecha_salida"] = _validar_fecha(vals["fecha_salida"], "fecha_salida")
    if "hora_ingreso" in vals:
        vals["hora_ingreso"] = _validar_hora(vals["hora_ingreso"], "hora_ingreso")
    if "hora_salida" in vals:
        vals["hora_salida"] = _validar_hora(vals["hora_salida"], "hora_salida")
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE control_acceso SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.put("/{id}/anular")
def anular(
    id: str,
    body: AnularBody,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("control_acceso", "anular")),
):
    """Anula (soft-delete trazable) un registro de control_acceso.
    Toda la regla de negocio (permiso, motivo obligatorio, ventana de
    tiempo, no doble anulación) y el audit_log los resuelve
    fn_control_acceso_anular en la propia base de datos; acá solo se
    traduce el RAISE EXCEPTION de Postgres a HTTP.
    p_ventana_horas no se pasa: se usa el DEFAULT 24h de la función
    (placeholder pendiente de confirmar con Alejandro/negocio).
    """
    try:
        row = db.execute(
            text("SELECT * FROM fn_control_acceso_anular(:id, :usuario_id, :motivo)"),
            {"id": id, "usuario_id": current_user["id"], "motivo": body.motivo},
        ).fetchone()
        db.commit()
    except DBAPIError as e:
        db.rollback()
        mensaje = _mensaje_error_pg(e)
        raise HTTPException(status_code=_codigo_http_anulacion(mensaje), detail=mensaje)

    return dict(row._mapping)


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
