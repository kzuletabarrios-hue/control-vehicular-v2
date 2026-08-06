# backend/routers/proveedores.py
import io
import json
import os
import uuid
from collections import Counter
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
    "tipo_vehiculo", "hora_ingreso", "hora_cita", "hora_salida", "fecha_salida",
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
            WITH base AS (
                SELECT p.* FROM proveedores p
                WHERE {cond}
            )
            SELECT * FROM base WHERE hora_salida IS NULL
            UNION ALL
            SELECT * FROM (
                SELECT * FROM base WHERE hora_salida IS NOT NULL
                ORDER BY fecha DESC, created_at DESC
                LIMIT :limit OFFSET :offset
            ) cerrados
            ORDER BY fecha DESC, created_at DESC
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


# ── Citas/reservas diarias de proveedores (carga desde WMS) ───────
# Repuntado 2026-08-05: NO usa una tabla propia. citas_programadas +
# archivos_citas ya existían en producción desde el 2026-07-10 (drift
# documentado en
# backend/migrations_manual/2026-08-05_documenta_citas_programadas_existente.sql)
# y las consume activamente una app externa a este repo -- este endpoint
# solo lee/escribe el esquema real, no lo modifica.
#
# numero_orden_compra en citas_programadas tiene CHECK ^4[0-9]{9}$ (10
# dígitos, empieza en 4) -- EXACTAMENTE la misma regla que ya usa
# proveedores_ordenes.numero_orden_compra (ver _ORDEN_RE en
# proveedores_publico.py, el campo que llena el conductor en el
# autorregistro QR). Por eso el número que aparece en la columna "O.
# Compra" del WMS (ej. "PT - 4602898240 - 2") se limpia extrayendo ese
# patrón de 10 dígitos tanto al importar el archivo como al buscar lo que
# teclea el guarda -- así el mismo número identifica la cita y la orden.

_FRANJA_RE = _re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
_DIGIT_RUN_RE = _re.compile(r"\d+")


def _str(v) -> str | None:
    """Normaliza celdas de Excel/JSON a texto limpio (o None si vacío)."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _extraer_numero_orden(v) -> str | None:
    """Busca dentro del texto (no asume posición fija) un tramo de EXACTAMENTE
    10 dígitos que empiece en 4 -- el mismo formato exigido por el CHECK de
    citas_programadas.numero_orden_compra y por proveedores_ordenes (regex
    ^4\\d{9}$). Sirve tanto para limpiar "O. Compra" del WMS ("PT -
    4602898240 - 2" -> "4602898240") como para limpiar lo que teclea el
    guarda en el campo "Número de orden" antes de comparar contra la BD.
    """
    s = _str(v)
    if not s:
        return None
    for grupo in _DIGIT_RUN_RE.findall(s):
        if len(grupo) == 10 and grupo[0] == "4":
            return grupo
    return None


def _parsear_franja_horaria(franja: str | None) -> tuple[str, str]:
    """Convierte 'HH:MM-HH:MM' en (hora_inicio, hora_fin) para las columnas
    TIME hora_cita_inicio/hora_cita_fin -- NOT NULL en la tabla real, así que
    a diferencia del diseño descartado de hoy (proveedores_citas_dia) ya NO
    se puede devolver (None, None).

    Decisión de negocio (bloqueante documentado por Jorge en la migración de
    2026-08-05): el WMS trae el placeholder "00:00-23:59" en algunas filas
    para indicar "todo el día / sin franja puntual". Se decidió (a) insertar
    ese literal 00:00:00-23:59:00 en vez de (b) excluir la fila del batch:
    como el patrón HH:MM-HH:MM ya matchea ese placeholder tal cual, no hace
    falta un caso especial -- se guarda como una franja de "todo el día" y
    la orden sigue disponible para autocompletar (proveedor + orden), solo
    sin acotar una hora específica. Excluir la fila perdería por completo
    esa orden de compra del lote de citas del día, que es peor para el
    guarda que una franja amplia.

    Filas sin franja reconocible (vacías o con un formato que no matchea)
    SÍ se excluyen -- no hay literal razonable que inventar ahí -- y se
    reportan en `errores` con ValueError.
    """
    if not franja:
        raise ValueError("Falta la franja horaria (columna F. Temporal)")
    m = _FRANJA_RE.match(franja)
    if not m:
        raise ValueError(f'Formato de franja horaria no reconocido (se esperaba HH:MM-HH:MM): "{franja}"')
    h1, m1, h2, m2 = m.groups()
    h1n, m1n, h2n, m2n = int(h1), int(m1), int(h2), int(m2)
    if not (0 <= h1n <= 23 and 0 <= m1n <= 59 and 0 <= h2n <= 23 and 0 <= m2n <= 59):
        raise ValueError(f'Franja horaria fuera de rango: "{franja}"')
    return f"{h1n:02d}:{m1n:02d}:00", f"{h2n:02d}:{m2n:02d}:00"


@router.get("/citas/buscar")
def buscar_cita(
    fecha: str,
    numero_orden_compra: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    """Lookup puntual para el autocompletado del formulario de ingreso.
    numero_orden_compra se limpia con la misma extracción de 10 dígitos que
    se usa al importar (ver _extraer_numero_orden) -- comparar contra texto
    crudo con espacios/prefijos nunca haría match contra el valor real
    guardado en citas_programadas (que cumple el CHECK ^4[0-9]{9}$).
    Nunca lanza error si no hay match: el guarda siempre puede seguir
    llenando el formulario a mano.
    """
    numero = _extraer_numero_orden(numero_orden_compra)
    if not fecha or not numero:
        return {"encontrado": False}
    row = db.execute(
        text("""
            SELECT proveedor_nombre, hora_cita_inicio, hora_cita_fin
            FROM citas_programadas
            WHERE fecha = :fecha AND numero_orden_compra = :numero
            LIMIT 1
        """),
        {"fecha": fecha, "numero": numero},
    ).fetchone()
    if not row:
        return {"encontrado": False}
    r = dict(row._mapping)
    return {
        "encontrado": True,
        "proveedor_nombre": r["proveedor_nombre"],
        "hora_cita_inicio": str(r["hora_cita_inicio"])[:5] if r["hora_cita_inicio"] else None,
        "hora_cita_fin": str(r["hora_cita_fin"])[:5] if r["hora_cita_fin"] else None,
    }


@router.post("/citas/importar")
def importar_citas(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    """Carga por lote del archivo de citas del WMS contra las tablas reales
    citas_programadas/archivos_citas (mismo patrón del sistema original,
    recuperable en git como c4b2a2a~1:backend/routers/citas.py):

    1) Cada fila se valida en Python ANTES de tocar la base de datos (número
       de orden de 10 dígitos que empiece en 4, fecha YYYY-MM-DD, franja
       horaria) -- las filas inválidas se reportan en `errores` sin abortar
       el resto del archivo.
    2) "Fecha Ejec." viene por fila, no una sola fecha elegida a mano: se
       calcula el conjunto de fechas distintas entre las filas válidas y se
       hace DELETE FROM citas_programadas WHERE fecha = :fecha por cada una
       antes de insertar -- restaura "la foto completa del día" para cada
       fecha que trae el archivo (no hay UNIQUE en la tabla real que lo
       garantice, ver migración de Jorge).
    3) Además, cada INSERT válido usa su propio SAVEPOINT: si una fila pasa
       las validaciones de Python pero aun así choca contra un CHECK/FK de
       la base de datos (defensa en profundidad), se reporta en `errores`
       sin perder las filas ya insertadas.
    4) Se registra siempre una fila en archivos_citas con el resumen final
       del lote (igual patrón que el sistema original), incluso si terminó
       sin ninguna fila importada.
    """
    filas = body.get("filas") or []
    nombre_archivo = _str(body.get("nombre_archivo") or body.get("archivo_origen"))
    if not filas:
        raise HTTPException(400, "Sin filas para importar")

    validas: list[tuple[int, dict]] = []
    errores: list[dict] = []
    vistos: dict[str, int] = {}  # "fecha|numero_orden" -> primera fila donde apareció

    for i, fila in enumerate(filas):
        fila_num = i + 2  # fila 1 = encabezados del Excel

        numero = _extraer_numero_orden(fila.get("numero_orden_compra"))
        if not numero:
            crudo = _str(fila.get("numero_orden_compra")) or "(vacío)"
            errores.append({"fila": fila_num, "error": f'Número de orden inválido (se esperan 10 dígitos que empiecen en 4 dentro de "O. Compra"): "{crudo}"'})
            continue

        fecha = _str(fila.get("fecha"))
        if not fecha or not _FECHA_RE.match(fecha) or not fecha_valida(fecha):
            errores.append({"fila": fila_num, "error": f'Fecha de la cita (Fecha Ejec.) vacía o inválida: "{fecha or ""}"'})
            continue

        try:
            hora_inicio, hora_fin = _parsear_franja_horaria(_str(fila.get("franja_horaria_texto")))
        except ValueError as e:
            errores.append({"fila": fila_num, "error": str(e)})
            continue

        clave = f"{fecha}|{numero}"
        if clave in vistos:
            errores.append({"fila": fila_num, "error": f'Orden "{numero}" repetida en el archivo para el {fecha} (ya está en la fila {vistos[clave]})'})
            continue
        vistos[clave] = fila_num

        validas.append((fila_num, {
            "id": str(uuid.uuid4()),
            "fecha": fecha,
            "numero_orden_compra": numero,
            "proveedor_nombre": _str(fila.get("proveedor")),
            "hora_cita_inicio": hora_inicio,
            "hora_cita_fin": hora_fin,
        }))

    archivo_id = str(uuid.uuid4())
    fechas_afectadas = sorted({v["fecha"] for _, v in validas})
    fecha_principal = Counter(v["fecha"] for _, v in validas).most_common(1)
    insertados = 0

    try:
        # El archivo debe existir antes que las citas por el FK archivo_id;
        # se registra con contadores en 0 y se actualiza al final con el
        # resumen real (incluye también los rechazos del SAVEPOINT).
        db.execute(text("""
            INSERT INTO archivos_citas
                (id, fecha, nombre_archivo, subido_por, total_filas, filas_importadas, filas_error, detalle_errores)
            VALUES
                (:id, :fecha, :nombre_archivo, :subido_por, :total_filas, 0, 0, CAST('[]' AS jsonb))
        """), {
            "id": archivo_id,
            "fecha": fecha_principal[0][0] if fecha_principal else None,
            "nombre_archivo": nombre_archivo,
            "subido_por": current_user["id"],
            "total_filas": len(filas),
        })

        for fecha in fechas_afectadas:
            db.execute(text("DELETE FROM citas_programadas WHERE fecha = :fecha"), {"fecha": fecha})

        for fila_num, vals in validas:
            vals["archivo_id"] = archivo_id
            try:
                sp = db.begin_nested()
                db.execute(text("""
                    INSERT INTO citas_programadas
                        (id, archivo_id, fecha, numero_orden_compra, proveedor_nombre,
                         hora_cita_inicio, hora_cita_fin)
                    VALUES
                        (:id, :archivo_id, :fecha, :numero_orden_compra, :proveedor_nombre,
                         :hora_cita_inicio, :hora_cita_fin)
                """), vals)
                sp.commit()
                insertados += 1
            except (IntegrityError, DataError):
                sp.rollback()
                errores.append({"fila": fila_num, "error": f'Orden "{vals["numero_orden_compra"]}" rechazada por la base de datos para el {vals["fecha"]}'})

        db.execute(text("""
            UPDATE archivos_citas
            SET filas_importadas = :filas_importadas, filas_error = :filas_error,
                detalle_errores = CAST(:detalle_errores AS jsonb)
            WHERE id = :id
        """), {
            "id": archivo_id,
            "filas_importadas": insertados,
            "filas_error": len(errores),
            "detalle_errores": json.dumps(errores, default=str),
        })

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "No se pudo importar el archivo de citas. Intenta de nuevo.")

    return {"insertados": insertados, "errores": errores, "archivo_id": archivo_id, "fechas": fechas_afectadas}


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
