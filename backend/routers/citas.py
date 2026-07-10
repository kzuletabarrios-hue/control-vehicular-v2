# backend/routers/citas.py
# Carga del archivo diario de citas de proveedores (export de Basis/logística).
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DataError

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))
ALERTA_VENCE_MIN = 10  # aviso cuando falten <=10 min para el fin de la franja (+tolerancia)

_ORDEN_RE = re.compile(r"^4\d{9}$")
_HORA_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_FECHA_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_hora(v) -> str | None:
    s = _str(v)
    if not s:
        return None
    m = _HORA_RE.match(s)
    if not m:
        return None
    h, mnt = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mnt <= 59):
        return None
    return f"{h:02d}:{mnt:02d}:00"


def _parse_fecha(v) -> str | None:
    s = _str(v)
    if not s:
        return None
    m = _FECHA_RE.match(s)
    return m.group(1) if m else None


def _audit(db, user, accion, tabla, rid, datos_despues):
    db.execute(text("""
        INSERT INTO audit_log (usuario_id, usuario_email, accion, tabla, registro_id, datos_despues)
        VALUES (:uid, :email, :accion, :tabla, :rid, CAST(:despues AS jsonb))
    """), {
        "uid": user["id"] if user else None,
        "email": user["email"] if user else None,
        "accion": accion,
        "tabla": tabla,
        "rid": str(rid) if rid else None,
        "despues": json.dumps(datos_despues, default=str),
    })


def _tolerancia_default(db) -> int:
    row = db.execute(text("SELECT valor FROM configuracion WHERE clave = 'tolerancia_min_default'")).fetchone()
    try:
        return int(row.valor) if row else 30
    except (TypeError, ValueError):
        return 30


@router.get("/config")
def obtener_config(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    return {"tolerancia_min_default": _tolerancia_default(db)}


@router.put("/config")
def actualizar_config(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("citas", "write")),
):
    tolerancia = body.get("tolerancia_min_default")
    try:
        tolerancia = int(tolerancia)
    except (TypeError, ValueError):
        raise HTTPException(400, "La tolerancia debe ser un número de minutos")
    if tolerancia < 0 or tolerancia > 240:
        raise HTTPException(400, "La tolerancia debe estar entre 0 y 240 minutos")

    db.execute(text("""
        INSERT INTO configuracion (clave, valor, updated_at, updated_por)
        VALUES ('tolerancia_min_default', :v, NOW(), :uid)
        ON CONFLICT (clave) DO UPDATE SET valor = :v, updated_at = NOW(), updated_por = :uid
    """), {"v": str(tolerancia), "uid": current_user["id"]})
    db.commit()
    return {"tolerancia_min_default": tolerancia}


@router.post("/cargar")
def cargar_archivo(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("citas", "write")),
):
    filas = body.get("filas", [])
    nombre_archivo = _str(body.get("nombre_archivo"))
    if not filas:
        raise HTTPException(400, "Sin filas para importar")

    # 1) Validar todo en Python primero, sin tocar la base de datos todavía.
    #    Esto reemplaza por completo la programación de cada fecha que trae el
    #    archivo, así que preferimos fallar antes de escribir nada a dejar el
    #    día a medio reemplazar si una fila se cae a mitad del proceso.
    tolerancia = _tolerancia_default(db)
    validas = []
    errores = []
    vistos: dict[str, int] = {}  # (fecha, orden) -> primera fila donde apareció

    for i, fila in enumerate(filas):
        fila_num = i + 2  # fila 1 = encabezados
        orden = _str(fila.get("numero_orden_compra"))
        if not orden or not _ORDEN_RE.match(orden):
            errores.append({"fila": fila_num, "error": f"Número de orden inválido (debe empezar en 4 y tener 10 dígitos): {orden or '(vacío)'}"})
            continue

        fecha = _parse_fecha(fila.get("fecha"))
        if not fecha:
            errores.append({"fila": fila_num, "error": "Fecha de cita (Misma FeEn) vacía o inválida"})
            continue

        hora_inicio = _parse_hora(fila.get("hora_cita_inicio"))
        hora_fin = _parse_hora(fila.get("hora_cita_fin"))
        if not hora_inicio or not hora_fin:
            errores.append({"fila": fila_num, "error": "Hora de inicio o fin de la cita vacía o inválida"})
            continue

        clave = f"{fecha}|{orden}"
        if clave in vistos:
            errores.append({"fila": fila_num, "error": f"Orden {orden} repetida en el archivo (ya aparece en la fila {vistos[clave]})"})
            continue
        vistos[clave] = fila_num

        validas.append({
            "id": str(uuid.uuid4()),
            "fecha": fecha,
            "numero_orden_compra": orden,
            "proveedor_codigo": _str(fila.get("proveedor_codigo")),
            "proveedor_nombre": _str(fila.get("proveedor_nombre")),
            "flujo": _str(fila.get("flujo")),
            "descripcion_carga": _str(fila.get("descripcion_carga")),
            "fecha_documento_compra": _parse_fecha(fila.get("fecha_documento_compra")),
            "cantidad_pallets": _str(fila.get("cantidad_pallets")),
            "hora_cita_inicio": hora_inicio,
            "hora_cita_fin": hora_fin,
            "tolerancia_min": tolerancia,
        })

    archivo_id = str(uuid.uuid4())
    fechas_afectadas = sorted(set(v["fecha"] for v in validas))
    reemplazadas = 0
    fecha_principal = Counter(v["fecha"] for v in validas).most_common(1)

    try:
        # El archivo debe existir antes de las citas por el FK archivo_id, aunque
        # el resumen (filas_importadas/error) ya se conoce desde la validación en Python.
        db.execute(text("""
            INSERT INTO archivos_citas
                (id, fecha, nombre_archivo, subido_por, total_filas, filas_importadas, filas_error, detalle_errores)
            VALUES
                (:id, :fecha, :nombre_archivo, :subido_por, :total_filas, :filas_importadas, :filas_error, :detalle_errores)
        """), {
            "id": archivo_id,
            "fecha": fecha_principal[0][0] if fecha_principal else None,
            "nombre_archivo": nombre_archivo,
            "subido_por": current_user["id"],
            "total_filas": len(filas),
            "filas_importadas": len(validas),
            "filas_error": len(errores),
            "detalle_errores": json.dumps(errores),
        })

        for fecha in fechas_afectadas:
            borradas = db.execute(
                text("DELETE FROM citas_programadas WHERE fecha = :fecha"), {"fecha": fecha}
            )
            reemplazadas += borradas.rowcount or 0

        for v in validas:
            v["archivo_id"] = archivo_id
            db.execute(text("""
                INSERT INTO citas_programadas
                    (id, archivo_id, fecha, numero_orden_compra, proveedor_codigo, proveedor_nombre,
                     flujo, descripcion_carga, fecha_documento_compra, cantidad_pallets,
                     hora_cita_inicio, hora_cita_fin, tolerancia_min)
                VALUES
                    (:id, :archivo_id, :fecha, :numero_orden_compra, :proveedor_codigo, :proveedor_nombre,
                     :flujo, :descripcion_carga, :fecha_documento_compra, :cantidad_pallets,
                     :hora_cita_inicio, :hora_cita_fin, :tolerancia_min)
            """), v)

        try:
            _audit(db, current_user, "CARGAR_ARCHIVO", "archivos_citas", archivo_id, {
                "nombre_archivo": nombre_archivo, "fechas": fechas_afectadas,
                "importadas": len(validas), "errores": len(errores), "reemplazadas": reemplazadas,
            })
        except Exception:
            pass

        db.commit()
    except (IntegrityError, DataError) as e:
        db.rollback()
        raise HTTPException(400, f"No se pudo guardar el archivo: {str(e)[:200]}")

    return {"insertados": len(validas), "actualizados": reemplazadas, "errores": errores}


@router.get("")
def listar(
    fecha: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    where = "WHERE fecha = :fecha" if fecha else ""
    params = {"fecha": fecha} if fecha else {}
    rows = db.execute(
        text(f"SELECT * FROM citas_programadas {where} ORDER BY hora_cita_inicio ASC"), params
    ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/alertas")
def alertas(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    """Calculado en vivo en cada consulta -- nunca se persiste 'vencida' en
    citas_programadas.estado, así que esto nunca queda desincronizado de la
    hora real (mismo criterio que "por vencer" en el tablero de muelles)."""
    ahora_dt = datetime.now(_BOG)
    hoy = ahora_dt.date()
    ahora = ahora_dt.time()

    archivo = db.execute(text("""
        SELECT created_at FROM archivos_citas WHERE fecha = :hoy ORDER BY created_at DESC LIMIT 1
    """), {"hoy": hoy.isoformat()}).fetchone()

    rows = db.execute(text("""
        SELECT numero_orden_compra, proveedor_nombre, hora_cita_inicio, hora_cita_fin, tolerancia_min
        FROM citas_programadas WHERE fecha = :hoy AND estado = 'pendiente'
        ORDER BY hora_cita_fin ASC
    """), {"hoy": hoy.isoformat()}).fetchall()

    por_vencer, vencidas = [], []
    for r in rows:
        fin_tolerado = (datetime.combine(hoy, r.hora_cita_fin) + timedelta(minutes=r.tolerancia_min or 0)).time()
        item = {
            "numero_orden_compra": r.numero_orden_compra,
            "proveedor_nombre": r.proveedor_nombre,
            "hora_cita_inicio": r.hora_cita_inicio.strftime("%H:%M"),
            "hora_cita_fin": r.hora_cita_fin.strftime("%H:%M"),
        }
        if ahora > fin_tolerado:
            vencidas.append(item)
        elif (datetime.combine(hoy, fin_tolerado) - ahora_dt.replace(tzinfo=None)).total_seconds() <= ALERTA_VENCE_MIN * 60:
            por_vencer.append(item)

    return {
        "archivo_hoy": archivo is not None,
        "hora_carga": archivo.created_at.isoformat() if archivo else None,
        "por_vencer": por_vencer,
        "vencidas": vencidas,
    }
