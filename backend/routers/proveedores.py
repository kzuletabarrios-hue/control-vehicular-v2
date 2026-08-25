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
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DataError

from database import get_db
from routers.auth import require_permiso, SECRET_KEY, ALGORITHM

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))

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
    # cita_id (FK -> citas_programadas.id, nullable): marca "esta orden ya
    # registró su llegada para esta cita programada". Ver migración
    # 2026-08-06_indice_proveedores_ordenes_cita_id.sql (UNIQUE parcial que
    # impide que dos filas apunten a la misma cita). NULL es normal cuando
    # el guarda llena a mano sin que haya habido match con citas_programadas.
    "cita_id",
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


def _raise_error_insercion(db: Session, e: IntegrityError):
    """Traduce un IntegrityError de INSERT/UPDATE en proveedores/proveedores_ordenes
    a un mensaje de negocio. El caso especial es la violación del UNIQUE parcial
    idx_proveedores_ordenes_cita_id_unico (ver migración
    2026-08-06_indice_proveedores_ordenes_cita_id.sql): dos filas de
    proveedores_ordenes intentando apuntar a la misma cita_id -- esperable por una
    carrera entre dos guardas, un doble clic o un reintento de red, no un error
    real del sistema, así que responde 409 con un mensaje claro en vez de un 500
    o el 400 genérico de "datos inválidos"."""
    db.rollback()
    if "idx_proveedores_ordenes_cita_id_unico" in str(getattr(e, "orig", e)):
        raise HTTPException(409, "Esta cita ya tiene una llegada registrada. Si esto es un error, acércate a la caseta para que el guarda lo revise.")
    raise HTTPException(400, "Datos inválidos: revisa las fechas y los campos de selección (tipo de documento, tipo/formato de carga, quién maneja la carga).")


def _audit(db, user, accion, tabla, rid, antes, despues):
    """Copia local del helper de auditoría de flota.py (líneas ~196-201) --
    a propósito no se comparte entre módulos por ahora (decisión de
    Alejandro)."""
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


def _attach_muelle(db, items: list[dict]) -> list[dict]:
    """Adjunta el ultimo evento de muelle de cada proveedor (asignado y/o ya
    liberado) para poder mostrar la linea de tiempo completa: cita, llegada,
    ingreso confirmado, salida de muelle y salida final. Copiado tal cual de
    citas-muelles-cedi-r10/backend/routers/proveedores.py (misma base de
    datos compartida vía Supabase) -- lectura pura, sin INSERT/UPDATE."""
    if not items:
        return items
    ids = [r["id"] for r in items]
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": v for i, v in enumerate(ids)}
    rows = db.execute(
        text(f"""
            SELECT DISTINCT ON (e.proveedor_id)
                e.proveedor_id, m.numero AS muelle_numero,
                (e.hora_asignado AT TIME ZONE 'America/Bogota')::time AS hora_muelle_asignado,
                (e.hora_liberado AT TIME ZONE 'America/Bogota')::time AS hora_muelle_liberado
            FROM muelle_eventos e JOIN muelles m ON m.id = e.muelle_id
            WHERE e.proveedor_id IN ({placeholders})
            ORDER BY e.proveedor_id, e.hora_asignado DESC
        """),
        params,
    ).fetchall()
    muelle_map = {str(r.proveedor_id): r for r in rows}
    for item in items:
        info = muelle_map.get(str(item["id"]))
        # muelle_actual depende solo del JOIN (evento real sin liberar) -- no se toca.
        item["muelle_actual"] = info.muelle_numero if (info and info.hora_muelle_liberado is None) else None
        # muelle_numero / hora_muelle_liberado: columnas reales de `proveedores`
        # (ver liberar_muelle) tienen prioridad; el JOIN a muelle_eventos/muelles
        # queda como fallback para datos históricos que no pasaron por ese endpoint.
        # Bug corregido (reportado por Jorge en la migración 2026-08-21): antes
        # se sobreescribía SIEMPRE de forma incondicional con el valor del JOIN
        # a muelle_eventos (dejando en None el valor real de la columna
        # proveedores.hora_muelle_asignado en cuanto info era None), a
        # diferencia de muelle_numero/hora_muelle_liberado, que sí seguían el
        # patrón correcto de abajo. Mismo patrón aplicado aquí ahora.
        item["hora_muelle_asignado"] = item.get("hora_muelle_asignado") or (info.hora_muelle_asignado if info else None)
        item["muelle_numero"] = item.get("muelle_numero") or (info.muelle_numero if info else None)
        item["hora_muelle_liberado"] = item.get("hora_muelle_liberado") or (info.hora_muelle_liberado if info else None)
    return items


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
    _attach_muelle(db, items)
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


@router.get("/citas")
def listar_citas_dia(
    fecha: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "read")),
):
    """Citas programadas de UNA fecha puntual (elegida a mano por el guarda,
    a diferencia del import por archivo -- ver comentario de handleCitasFile
    en el frontend) para la lista de "Citas del día (WMS)" del modal, con
    edición manual de hora. Incluye si ya tiene una llegada registrada con
    el mismo criterio EXISTS que ya usa GET /citas/alertas."""
    if not fecha or not _FECHA_RE.match(fecha) or not fecha_valida(fecha):
        raise HTTPException(400, "Fecha inválida (se espera YYYY-MM-DD)")

    rows = db.execute(
        text("""
            SELECT cp.id, cp.numero_orden_compra, cp.proveedor_nombre,
                   cp.hora_cita_inicio, cp.hora_cita_fin, cp.hora_editada_manualmente,
                   EXISTS (
                       SELECT 1 FROM proveedores_ordenes po WHERE po.cita_id = cp.id
                   ) AS tiene_llegada
            FROM citas_programadas cp
            WHERE cp.fecha = :fecha
            ORDER BY cp.hora_cita_inicio, cp.proveedor_nombre
        """),
        {"fecha": fecha},
    ).fetchall()

    items = []
    for row in rows:
        d = dict(row._mapping)
        hi, hf = d["hora_cita_inicio"], d["hora_cita_fin"]
        items.append({
            "id": d["id"],
            "numero_orden_compra": d["numero_orden_compra"],
            "proveedor_nombre": d["proveedor_nombre"],
            "hora_cita_inicio": f"{hi.hour:02d}:{hi.minute:02d}" if hi else None,
            "hora_cita_fin": f"{hf.hour:02d}:{hf.minute:02d}" if hf else None,
            "hora_editada_manualmente": d["hora_editada_manualmente"],
            "tiene_llegada": d["tiene_llegada"],
        })
    return {"items": items}


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
    _attach_muelle(db, [item])
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
_HORA_HHMM_RE = _re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


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


def _tolerancia_min_default(db) -> int:
    """Copia idéntica de _tolerancia_default() en routers/citas.py (misma
    tabla clave-valor `configuracion`, sin CHECK de formato en `valor` --
    confirmado por Jorge en 2026-08-07_auditoria_fase51_unificacion_citas_qr.sql).
    Se llama UNA vez por corrida de importar_citas(), no por fila: la
    tolerancia vigente al momento de la carga se estampa igual en todo el
    lote, igual que hacía el sistema original de citas-muelles-cedi-r10."""
    row = db.execute(text("SELECT valor FROM configuracion WHERE clave = 'tolerancia_min_default'")).fetchone()
    try:
        return int(row.valor) if row else 30
    except (TypeError, ValueError):
        return 30


def _limpiar_pallets(v) -> str | None:
    """cantidad_pallets es TEXT en la BD real, SIN CHECK numérico (confirmado
    por Jorge: valores muestreados '26','7','24','22', pero la base de datos
    no garantiza ese formato para futuras cargas). Cast defensivo, no
    bloqueante: si el Excel entrega el número como float (celda numérica
    "26.0"), se normaliza a "26"; cualquier otro valor (incluido texto no
    numérico) se guarda tal cual, limpio de espacios -- nunca se descarta la
    fila completa por esto, a diferencia de numero_orden_compra/fecha/franja
    horaria, que sí son obligatorios."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = _str(v)
    if not s:
        return None
    m = _re.fullmatch(r"(\d+)\.0+", s)
    return m.group(1) if m else s


def _fecha_documento_opcional(v) -> str | None:
    """fecha_documento_compra es metadata informativa (a diferencia de
    `fecha`, que sí es obligatoria y parte de la clave de negocio): si viene
    vacía o con un formato que no matchea YYYY-MM-DD, se guarda NULL en vez
    de rechazar la fila entera."""
    s = _str(v)
    if not s or not _FECHA_RE.match(s) or not fecha_valida(s):
        return None
    return s


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

    NO validar proximidad horaria aquí -- decisión de negocio 2026-08-06: ni
    el conductor ni el guarda deben bloquearse por estar fuera del rango de
    hora_cita_inicio/fin. Solo se alerta (GET /proveedores/citas/alertas),
    nunca se bloquea.

    Devuelve `cita_id` (citas_programadas.id) para que el frontend lo lleve
    en la orden que arma el guarda y quede guardado en
    proveedores_ordenes.cita_id al confirmar el ingreso (ver CAMPOS_ORDEN /
    _insert_ordenes) -- así el endpoint de alertas sabe que esta cita ya
    tiene una llegada registrada.
    """
    numero = _extraer_numero_orden(numero_orden_compra)
    if not fecha or not numero:
        return {"encontrado": False}
    row = db.execute(
        text("""
            SELECT id, proveedor_nombre, hora_cita_inicio, hora_cita_fin
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
        "cita_id": r["id"],
        "proveedor_nombre": r["proveedor_nombre"],
        "hora_cita_inicio": str(r["hora_cita_inicio"])[:5] if r["hora_cita_inicio"] else None,
        "hora_cita_fin": str(r["hora_cita_fin"])[:5] if r["hora_cita_fin"] else None,
    }


# Minutos antes de hora_cita_inicio en los que empieza a mostrarse la alerta
# de "por vencer" (ver GET /citas/alertas). El paso de "por vencer" a
# "atrasada" no usa una constante fija: reutiliza tolerancia_min, columna
# NOT NULL (default 30) que ya trae cada fila de citas_programadas.
ALERTA_PREAVISO_MIN = 15


@router.get("/citas/alertas")
def citas_alertas(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "read")),
):
    """Todas las citas programadas de HOY (fecha calculada en el SERVIDOR)
    que todavía no fueron consumidas por el paso de "Ingresado WPS"
    (cp.estado sigue en 'pendiente' -- ver marcar_ingreso_wps, que es quien
    la pasa a 'usada'). Ya puede existir una llegada registrada en
    proveedores_ordenes para esa cita sin que eso la saque de aquí: llegar
    no es lo mismo que quedar procesada en WPS, y la alerta debe seguir
    visible mientras falte ese paso (ver "ya_registrado" más abajo, que
    distingue ambos casos para el frontend). Es el listado completo -- no
    solo las urgentes -- que alimenta la pestaña "Con cita" de Proveedores
    (mismo patrón que "Por confirmar"/"Ingresados WPS"/"En muelle": todo lo
    que está en ese estado, no un subconjunto).

    Clasifica cada cita en 3 grupos según qué tan cerca está su hora:
    - "pendientes": todavía falta más de ALERTA_PREAVISO_MIN minutos.
    - "por_vencer": dentro de la ventana de preaviso o dentro de
      tolerancia_min tras la hora de cita (ya pasó la hora pero aún no se
      considera atraso).
    - "atrasadas": ya superó tolerancia_min tras la hora de cita.

    NO bloquea nada: es solo información para que el guarda decida llamar.
    NO valida proximidad horaria para impedir un registro -- decisión de
    negocio 2026-08-06 (ver también el comentario en GET /citas/buscar):
    este endpoint es la ÚNICA fuente de alertas por horario del módulo de
    proveedores, y su única función es avisar, nunca bloquear.

    Excluye las citas placeholder "todo el día" (00:00:00-23:59:00, ver
    _parsear_franja_horaria) -- no tiene sentido alertar sobre esas, no
    tienen una hora puntual a la que "llegar tarde".
    """
    hoy = datetime.now(_BOG).date().isoformat()
    ahora = datetime.now(_BOG)
    minutos_ahora = ahora.hour * 60 + ahora.minute

    rows = db.execute(
        text("""
            SELECT cp.numero_orden_compra, cp.proveedor_nombre, cp.hora_cita_inicio,
                   cp.tolerancia_min,
                   (
                       -- bd_proveedores.nombre es un catalogo mantenido a mano y
                       -- cp.proveedor_nombre viene del WMS: pueden no calzar exacto
                       -- en mayusculas/espacios, de ahi la comparacion tolerante.
                       -- bd_proveedores.nombre no tiene UNIQUE, asi que se usa un
                       -- subselect con LIMIT 1 (no un LEFT JOIN) para no duplicar
                       -- filas de citas_programadas si hay mas de un match; se
                       -- prioriza el proveedor activo y el mas reciente.
                       SELECT bp.celular
                       FROM bd_proveedores bp
                       WHERE UPPER(btrim(bp.nombre)) = UPPER(btrim(cp.proveedor_nombre))
                       ORDER BY bp.activo DESC, bp.updated_at DESC
                       LIMIT 1
                   ) AS telefono,
                   EXISTS (
                       SELECT 1 FROM proveedores_ordenes po WHERE po.cita_id = cp.id
                   ) AS ya_registrado
            FROM citas_programadas cp
            WHERE cp.fecha = :hoy
              AND NOT (cp.hora_cita_inicio = '00:00:00' AND cp.hora_cita_fin = '23:59:00')
              AND cp.estado = 'pendiente'
            ORDER BY cp.hora_cita_inicio
        """),
        {"hoy": hoy},
    ).fetchall()

    pendientes: list[dict] = []
    por_vencer: list[dict] = []
    atrasadas: list[dict] = []
    for row in rows:
        d = dict(row._mapping)
        hi = d["hora_cita_inicio"]
        if hi is None:
            continue
        minutos_cita = hi.hour * 60 + hi.minute
        tolerancia = d["tolerancia_min"] if d["tolerancia_min"] is not None else 30
        inicio_preaviso = minutos_cita - ALERTA_PREAVISO_MIN
        limite_atraso = minutos_cita + tolerancia

        item = {
            "numero_orden_compra": d["numero_orden_compra"],
            "proveedor_nombre": d["proveedor_nombre"],
            "hora_cita_inicio": f"{hi.hour:02d}:{hi.minute:02d}",
            "telefono": d.get("telefono"),
            "ya_registrado": d["ya_registrado"],
        }

        if minutos_ahora < inicio_preaviso:
            # todavía falta demasiado, ni siquiera preaviso -- antes se
            # descartaba con un "continue"; ahora se reporta como pendiente
            # para la pestaña "Con cita" (no es urgente, solo informativo).
            item["minutos_restantes"] = minutos_cita - minutos_ahora
            pendientes.append(item)
        elif minutos_ahora > limite_atraso:
            item["minutos_atraso"] = minutos_ahora - minutos_cita
            atrasadas.append(item)
        else:
            # minutos_restantes puede ser negativo: significa que ya pasó
            # hora_cita_inicio pero todavía está dentro de tolerancia_min
            # (por eso sigue en "por_vencer" y no en "atrasadas"). Se deja
            # el número real (no se recorta a 0) para que el frontend pueda
            # mostrar ese matiz si quiere.
            item["minutos_restantes"] = minutos_cita - minutos_ahora
            por_vencer.append(item)

    return {"pendientes": pendientes, "por_vencer": por_vencer, "atrasadas": atrasadas}


class EditarCitaBody(BaseModel):
    hora_cita_inicio: str
    hora_cita_fin: str
    motivo: str

    @field_validator("hora_cita_inicio", "hora_cita_fin")
    @classmethod
    def _hora_valida(cls, v: str) -> str:
        v = (v or "").strip()
        if not _HORA_HHMM_RE.match(v):
            raise ValueError('Formato de hora inválido (se espera HH:MM)')
        return v

    @field_validator("motivo")
    @classmethod
    def _motivo_valido(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 5:
            raise ValueError("El motivo es obligatorio (mínimo 5 caracteres)")
        return v

    @model_validator(mode="after")
    def _inicio_antes_de_fin(self):
        # Comparación lexicográfica válida: ambos campos ya están normalizados
        # a "HH:MM" (2+2 dígitos con cero a la izquierda) por _hora_valida.
        if self.hora_cita_inicio >= self.hora_cita_fin:
            raise ValueError("La hora de inicio debe ser anterior a la hora de fin")
        return self


@router.put("/citas/{id}")
def editar_cita(
    id: str,
    body: EditarCitaBody,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "editar_cita")),
):
    """Edición manual puntual de hora_cita_inicio/hora_cita_fin de UNA cita
    (autorizada fuera del WMS, ej. por un ajuste de última hora acordado con
    el proveedor). Marca hora_editada_manualmente = true para que la fila
    sobreviva al próximo reemplazo por lote de POST /citas/importar (ver
    migración 2026-08-06_citas_programadas_hora_editada_manualmente.sql).
    Permiso separado "editar_cita" (no "write"): mismo patrón que
    "control_acceso":"anular", para que quede explícito en el código qué
    acción es -- aunque hoy se otorgue a los mismos roles que ya tienen
    "write" sobre proveedores (ver migración de permisos)."""
    antes = db.execute(
        text("""
            SELECT cp.hora_cita_inicio, cp.hora_cita_fin,
                   EXISTS (
                       SELECT 1 FROM proveedores_ordenes po WHERE po.cita_id = cp.id
                   ) AS tiene_llegada
            FROM citas_programadas cp
            WHERE cp.id = :id
        """),
        {"id": id},
    ).fetchone()
    if not antes:
        raise HTTPException(404, "Cita no encontrada")
    if antes.tiene_llegada:
        raise HTTPException(409, "Esta cita ya tiene una llegada registrada, no se puede editar la hora.")

    hi_db = f"{body.hora_cita_inicio}:00"
    hf_db = f"{body.hora_cita_fin}:00"

    db.execute(
        text("""
            UPDATE citas_programadas
            SET hora_cita_inicio = :hi, hora_cita_fin = :hf,
                hora_editada_manualmente = true, updated_at = NOW()
            WHERE id = :id
        """),
        {"id": id, "hi": hi_db, "hf": hf_db},
    )

    datos_antes = {
        "hora_cita_inicio": str(antes.hora_cita_inicio)[:5] if antes.hora_cita_inicio else None,
        "hora_cita_fin": str(antes.hora_cita_fin)[:5] if antes.hora_cita_fin else None,
    }
    datos_despues = {
        "hora_cita_inicio": body.hora_cita_inicio,
        "hora_cita_fin": body.hora_cita_fin,
        "motivo": body.motivo,
    }
    _audit(db, current_user, "EDITAR_HORA_CITA", "citas_programadas", id, datos_antes, datos_despues)
    db.commit()
    return {
        "message": "Hora de la cita actualizada",
        "hora_cita_inicio": body.hora_cita_inicio,
        "hora_cita_fin": body.hora_cita_fin,
    }


@router.post("/citas/importar")
def importar_citas(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    """Carga por lote del archivo de citas del WMS contra las tablas reales
    citas_programadas/archivos_citas (mismo patrón del sistema original,
    recuperable en git como c4b2a2a~1:backend/routers/citas.py), ampliado en
    Fase 5.2 para traer TODAS las columnas que trae el archivo (paridad con
    cargar_archivo() de citas-muelles-cedi-r10/backend/routers/citas.py) y
    tolerancia configurable:

    1) Cada fila se valida en Python ANTES de tocar la base de datos (número
       de orden de 10 dígitos que empiece en 4, fecha YYYY-MM-DD, franja
       horaria) -- las filas inválidas se reportan en `errores` sin abortar
       el resto del archivo. Los campos adicionales (proveedor_codigo,
       flujo, descripcion_carga, fecha_documento_compra, cantidad_pallets)
       son metadata: si vienen vacíos o mal formados NO tumban la fila,
       simplemente se guardan como NULL/texto limpio (ver
       _fecha_documento_opcional / _limpiar_pallets).
    2) "Fecha Ejec." viene por fila, no una sola fecha elegida a mano: se
       calcula el conjunto de fechas distintas entre las filas válidas y se
       hace DELETE FROM citas_programadas WHERE fecha = :fecha (protegiendo
       hora_editada_manualmente) por cada una antes de insertar -- restaura
       "la foto completa del día" para cada fecha que trae el archivo. El
       UNIQUE(fecha, numero_orden_compra) YA existe en producción
       (confirmado por Jorge, 2026-08-07) pero se mantiene DELETE+INSERT en
       vez de UPSERT (ON CONFLICT DO UPDATE): el DELETE previo por fecha ya
       limpia el terreno para toda fila no protegida, y las filas
       protegidas se excluyen del INSERT antes de llegar a la base de datos
       (no compiten con el DELETE por la misma clave) -- así que dentro de
       una misma corrida no debería haber ningún conflicto real contra ese
       UNIQUE. Si dos cargas concurrentes chocaran igual (carrera entre dos
       requests), el SAVEPOINT por fila de abajo ya lo captura como
       IntegrityError y lo reporta en `errores` -- preferible a un UPSERT
       silencioso, que ocultaría la carrera en vez de dejarla visible para
       reintentar la carga.
    3) Además, cada INSERT válido usa su propio SAVEPOINT: si una fila pasa
       las validaciones de Python pero aun así choca contra un CHECK/FK de
       la base de datos (defensa en profundidad), se reporta en `errores`
       sin perder las filas ya insertadas.
    4) tolerancia_min se lee UNA sola vez por corrida (no por fila) de
       configuracion.tolerancia_min_default y se estampa igual en todas las
       filas del lote -- mismo criterio que usaba el sistema original.
    5) Se registra siempre una fila en archivos_citas con el resumen final
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
            "proveedor_codigo": _str(fila.get("proveedor_codigo")),
            "proveedor_nombre": _str(fila.get("proveedor")) or _str(fila.get("proveedor_nombre")),
            "flujo": _str(fila.get("flujo")),
            "descripcion_carga": _str(fila.get("descripcion_carga")),
            "fecha_documento_compra": _fecha_documento_opcional(fila.get("fecha_documento_compra")),
            "cantidad_pallets": _limpiar_pallets(fila.get("cantidad_pallets")),
            "hora_cita_inicio": hora_inicio,
            "hora_cita_fin": hora_fin,
        }))

    archivo_id = str(uuid.uuid4())
    fechas_afectadas = sorted({v["fecha"] for _, v in validas})
    fecha_principal = Counter(v["fecha"] for _, v in validas).most_common(1)
    tolerancia_min = _tolerancia_min_default(db)
    insertados = 0
    preservadas: list[dict] = []

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

        # Órdenes con hora_editada_manualmente = true para cada fecha afectada:
        # el DELETE de abajo las protege (no las borra), así que hay que
        # calcular el set ANTES de filtrar `validas` para no reinsertar un
        # duplicado de esa misma orden (la tabla no tiene UNIQUE, ver
        # migración 2026-08-06_citas_programadas_hora_editada_manualmente.sql).
        protegidas_por_fecha: dict[str, set[str]] = {}
        for fecha in fechas_afectadas:
            rows_prot = db.execute(
                text("""
                    SELECT numero_orden_compra FROM citas_programadas
                    WHERE fecha = :fecha AND hora_editada_manualmente IS TRUE
                """),
                {"fecha": fecha},
            ).fetchall()
            protegidas_por_fecha[fecha] = {r[0] for r in rows_prot}

            db.execute(
                text("DELETE FROM citas_programadas WHERE fecha = :fecha AND hora_editada_manualmente IS NOT TRUE"),
                {"fecha": fecha},
            )

        for fila_num, vals in validas:
            protegidas = protegidas_por_fecha.get(vals["fecha"], set())
            if vals["numero_orden_compra"] in protegidas:
                preservadas.append({
                    "numero_orden_compra": vals["numero_orden_compra"],
                    "motivo": "tiene una hora editada manualmente, no se actualizó",
                })
                continue

            vals["archivo_id"] = archivo_id
            vals["tolerancia_min"] = tolerancia_min
            try:
                sp = db.begin_nested()
                db.execute(text("""
                    INSERT INTO citas_programadas
                        (id, archivo_id, fecha, numero_orden_compra, proveedor_codigo, proveedor_nombre,
                         flujo, descripcion_carga, fecha_documento_compra, cantidad_pallets,
                         hora_cita_inicio, hora_cita_fin, tolerancia_min)
                    VALUES
                        (:id, :archivo_id, :fecha, :numero_orden_compra, :proveedor_codigo, :proveedor_nombre,
                         :flujo, :descripcion_carga, :fecha_documento_compra, :cantidad_pallets,
                         :hora_cita_inicio, :hora_cita_fin, :tolerancia_min)
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

    return {
        "insertados": insertados,
        "errores": errores,
        "preservadas": preservadas,
        "archivo_id": archivo_id,
        "fechas": fechas_afectadas,
    }


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
    # El alta manual del guarda ("Nuevo ingreso") sigue el mismo ciclo
    # llegada -> confirmación que el autorregistro QR: nace 'pendiente' y
    # sin hora_ingreso_confirmado hasta que se pulse "Confirmar" (endpoint
    # /proveedores/{id}/confirmar-ingreso), que es el único que la puebla.
    vals["estado_confirmacion"] = "pendiente"
    if not (vals.get("nombre_conductor") or "").strip():
        raise HTTPException(400, "El nombre del conductor es obligatorio")
    if not (vals.get("cedula_conductor") or "").strip():
        raise HTTPException(400, "La cédula del conductor es obligatoria")
    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    try:
        db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
        _insert_ordenes(db, rid, ordenes)
        db.commit()
    except IntegrityError as e:
        _raise_error_insercion(db, e)
    except DataError:
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
    try:
        db.execute(text(f"INSERT INTO proveedores_ordenes ({ocols}) VALUES ({opholds})"), ovals)
        db.commit()
    except IntegrityError as e:
        _raise_error_insercion(db, e)
    except DataError:
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa los campos de la orden.")
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
    try:
        db.execute(text(f"UPDATE proveedores_ordenes SET {sets} WHERE id = :oid"), vals)
        db.commit()
    except IntegrityError as e:
        _raise_error_insercion(db, e)
    except DataError:
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa los campos de la orden.")
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
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    antes = db.execute(
        text("SELECT * FROM proveedores WHERE id = :id"), {"id": id}
    ).fetchone()
    if not antes:
        raise HTTPException(404, "Registro no encontrado")
    vals = {c: body[c] for c in CAMPOS_VEHICULO if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    if "nombre_conductor" in vals and not (vals["nombre_conductor"] or "").strip():
        raise HTTPException(400, "El nombre del conductor no puede quedar vacío")
    if "cedula_conductor" in vals and not (vals["cedula_conductor"] or "").strip():
        raise HTTPException(400, "La cédula del conductor no puede quedar vacía")
    vals["id"] = id

    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    try:
        db.execute(text(f"UPDATE proveedores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    except (IntegrityError, DataError):
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa las fechas y los campos de selección (tipo de documento, tipo/formato de carga, quién maneja la carga).")
    try:
        _audit(db, current_user, "UPDATE", "proveedores", id, dict(antes._mapping), vals)
    except Exception:
        pass
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


@router.put("/{id}/marcar-wps")
def marcar_ingreso_wps(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    antes = db.execute(text("SELECT * FROM proveedores WHERE id = :id"), {"id": id}).fetchone()
    if not antes:
        raise HTTPException(404, "Registro no encontrado")
    if antes.estado_confirmacion == "ingresado_wps":
        raise HTTPException(409, "Ya fue ingresado a WPS")
    if antes.estado_confirmacion == "confirmado":
        raise HTTPException(409, "Ya está confirmado en muelle")
    hora = datetime.now(_BOG).strftime("%H:%M:%S")
    db.execute(
        text("""
            UPDATE proveedores
            SET estado_confirmacion = 'ingresado_wps', hora_wps = :hora,
                marcado_wps_por = :user_id, updated_at = NOW()
            WHERE id = :id
        """),
        {"id": id, "hora": hora, "user_id": current_user["id"]},
    )
    # citas_programadas es una tabla compartida con citas-muelles-cedi-r10 (Fase 5.3
    # de la migración a escritor único). Esa app lee su columna `estado` para saber
    # si una cita ya fue usada (dashboard ci_usadas, validaciones propias), pero ya
    # no la escribe: control-vehicular-v2 es ahora el único escritor. Sin este UPDATE
    # en cascada, `estado` se quedaba en 'pendiente' para siempre aunque el guarda ya
    # hubiera marcado el ingreso a WPS aquí (este es ahora el paso que consume la cita,
    # no la confirmación a muelle). El WHERE estado != 'usada' evita escrituras
    # innecesarias si ya estaba marcada; el IN (SELECT ...) no afecta filas (no
    # lanza error) cuando ninguna orden del proveedor tiene cita_id asociado.
    db.execute(
        text("""
            UPDATE citas_programadas
            SET estado = 'usada', updated_at = NOW()
            WHERE id IN (
                SELECT cita_id FROM proveedores_ordenes
                WHERE proveedor_id = :id AND cita_id IS NOT NULL
            )
            AND estado != 'usada'
        """),
        {"id": id},
    )
    try:
        _audit(
            db, current_user, "UPDATE", "proveedores", id,
            dict(antes._mapping),
            {"estado_confirmacion": "ingresado_wps", "hora_wps": hora, "marcado_wps_por": current_user["id"]},
        )
    except Exception:
        pass
    db.commit()
    return {"message": "Ingreso a WPS marcado"}


@router.put("/{id}/deshacer-wps")
def deshacer_ingreso_wps(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("proveedores", "write")),
):
    """Revierte un `marcar-wps` hecho por error: pendiente <- ingresado_wps,
    dentro de una ventana corta (15 min desde hora_wps) para que sea
    claramente "deshacer el clic accidental" y no una forma alterna de editar
    el registro más tarde (para eso ya existe PUT /{id}).

    Salvaguarda pedida por Alejandro: si la cita ligada a este proveedor
    (proveedores_ordenes.cita_id) también está referenciada por una orden de
    OTRO proveedor que ya avanzó a 'ingresado_wps' o 'confirmado', NO se
    reabre esa cita al deshacer -- ese otro proveedor la sigue necesitando
    marcada como 'usada'. Caso raro (una misma cita compartida entre
    proveedores distintos) pero real dado el modelo de datos actual."""
    antes = db.execute(text("SELECT * FROM proveedores WHERE id = :id"), {"id": id}).fetchone()
    if not antes:
        raise HTTPException(404, "Registro no encontrado")
    if antes.estado_confirmacion != "ingresado_wps":
        raise HTTPException(
            409,
            "Solo se puede deshacer mientras el registro está en 'Ingresado WPS'",
        )
    ahora = datetime.now(_BOG)
    if antes.hora_wps:
        minutos_ahora = ahora.hour * 60 + ahora.minute
        minutos_wps = antes.hora_wps.hour * 60 + antes.hora_wps.minute
        transcurridos = minutos_ahora - minutos_wps
        if transcurridos < 0:
            transcurridos += 24 * 60  # cruce de medianoche
        if transcurridos > 15:
            raise HTTPException(
                409,
                "Han pasado más de 15 minutos desde el ingreso a WPS: corrige el registro editándolo manualmente, no con este botón",
            )
    db.execute(
        text("""
            UPDATE proveedores
            SET estado_confirmacion = 'pendiente', hora_wps = NULL,
                marcado_wps_por = NULL, updated_at = NOW()
            WHERE id = :id
        """),
        {"id": id},
    )
    # Reabre la cita consumida por marcar-wps, salvo que esa misma cita_id
    # ya esté en uso por la orden de OTRO proveedor que avanzó más allá de
    # 'pendiente' (ver salvaguarda en el docstring).
    cita_result = db.execute(
        text("""
            UPDATE citas_programadas
            SET estado = 'pendiente', updated_at = NOW()
            WHERE estado = 'usada'
              AND id IN (
                  SELECT cita_id FROM proveedores_ordenes
                  WHERE proveedor_id = :id AND cita_id IS NOT NULL
              )
              AND NOT EXISTS (
                  SELECT 1 FROM proveedores_ordenes po2
                  JOIN proveedores p2 ON p2.id = po2.proveedor_id
                  WHERE po2.cita_id = citas_programadas.id
                    AND po2.proveedor_id != :id
                    AND p2.estado_confirmacion IN ('ingresado_wps', 'confirmado')
              )
            RETURNING id
        """),
        {"id": id},
    )
    citas_reabiertas = [str(r[0]) for r in cita_result.fetchall()]
    try:
        _audit(
            db, current_user, "UPDATE", "proveedores", id,
            dict(antes._mapping),
            {
                "estado_confirmacion": "pendiente",
                "hora_wps": None,
                "marcado_wps_por": None,
                "citas_programadas_reabiertas": citas_reabiertas,
            },
        )
    except Exception:
        pass
    db.commit()
    return {"message": "Ingreso a WPS deshecho: el registro vuelve a 'Por confirmar'"}


@router.put("/{id}/confirmar")
def confirmar_autorregistro(
    id: str,
    body: dict | None = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "write")),
):
    row = db.execute(text("SELECT estado_confirmacion FROM proveedores WHERE id = :id"), {"id": id}).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    if row.estado_confirmacion == "confirmado":
        raise HTTPException(409, "Este registro ya estaba confirmado")
    if row.estado_confirmacion == "pendiente":
        raise HTTPException(409, "Falta marcar ingreso a WPS antes de confirmar a muelle")
    hora = datetime.now(_BOG).strftime("%H:%M:%S")
    # El tablero de muelles del guarda vehicular (ProveedoresPage) puede mandar
    # el muelle elegido en el mismo gesto que confirma el ingreso, para no
    # obligarlo a abrir la tarjeta completa del registro después. Es opcional
    # a propósito: si no viene (o llega vacío), el comportamiento es
    # exactamente el de siempre -- confirma sin tocar muelle_descargue, que
    # bodega puede asignar más tarde desde la pantalla de Muelles. No se
    # valida el rango 1-18 acá: el valor sale de un botón del tablero, no de
    # texto libre (mismo criterio laxo que ya tiene esta columna en el resto
    # del archivo, ver `actualizar` arriba).
    muelle = (body or {}).get("muelle_descargue")
    muelle = str(muelle).strip() if muelle not in (None, "") else None
    if muelle:
        db.execute(
            text("""
                UPDATE proveedores
                SET estado_confirmacion = 'confirmado', hora_ingreso_confirmado = :hora,
                    muelle_descargue = :muelle, updated_at = NOW()
                WHERE id = :id
            """),
            {"id": id, "hora": hora, "muelle": muelle},
        )
    else:
        db.execute(
            text("""
                UPDATE proveedores
                SET estado_confirmacion = 'confirmado', hora_ingreso_confirmado = :hora, updated_at = NOW()
                WHERE id = :id
            """),
            {"id": id, "hora": hora},
        )
    # Red de seguridad defensiva (ya NO es el camino principal: eso se movió a
    # PUT /{id}/marcar-wps, que consume la cita al pasar a 'ingresado_wps'). Este
    # UPDATE sigue siendo necesario porque POST /{id}/ordenes permite agregar una
    # orden nueva con su propio cita_id a un proveedor que YA pasó por WPS (o incluso
    # ya confirmado); sin esta red esa cita quedaría huérfana en estado='pendiente'
    # para siempre. El WHERE estado != 'usada' evita escrituras innecesarias.
    db.execute(
        text("""
            UPDATE citas_programadas
            SET estado = 'usada', updated_at = NOW()
            WHERE id IN (
                SELECT cita_id FROM proveedores_ordenes
                WHERE proveedor_id = :id AND cita_id IS NOT NULL
            )
            AND estado != 'usada'
        """),
        {"id": id},
    )
    db.commit()
    return {"message": "Ingreso confirmado"}


@router.put("/{id}/liberar-muelle")
def liberar_muelle(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("muelles", "liberar")),
):
    """Libera el andén/muelle que tiene asignado un proveedor
    (proveedores.muelle_descargue -> NULL), como paso independiente de
    "Registrar salida" (PUT /{id} con hora_salida): en la operación real el
    vehículo puede desocupar el muelle y seguir un rato más dentro del CEDI
    antes de salir del todo. Gateado con el permiso "muelles":"liberar" que
    ya tiene guarda_bodega en producción (ver
    migrations_manual/2026-08-01_roles_guarda_alta_formal.sql) -- no hace
    falta ninguna migración de permisos nueva para este endpoint.

    muelle_numero / hora_muelle_liberado (columnas reales de `proveedores`
    desde 2026-08-08_proveedores_muelle_liberado_columns.sql) quedan aquí
    como registro histórico de la línea de tiempo del frontend (DetalleTiempos,
    "Salida de muelle"), independiente de que muelle_descargue se anule."""
    row = db.execute(
        text("SELECT estado_confirmacion, muelle_descargue, hora_salida FROM proveedores WHERE id = :id"),
        {"id": id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    if row.estado_confirmacion != "confirmado":
        raise HTTPException(409, "Este proveedor aún no tiene el ingreso confirmado en muelle.")
    if not row.muelle_descargue:
        raise HTTPException(409, "Este proveedor no tiene un muelle asignado para liberar")
    if row.hora_salida is not None:
        raise HTTPException(409, "Este proveedor ya registró salida del CEDI")

    muelle_anterior = row.muelle_descargue
    hora = datetime.now(_BOG).strftime("%H:%M:%S")
    db.execute(
        text("""
            UPDATE proveedores
            SET muelle_descargue = NULL,
                muelle_numero = :muelle_numero,
                hora_muelle_liberado = :hora,
                updated_at = NOW()
            WHERE id = :id
        """),
        {"id": id, "muelle_numero": muelle_anterior, "hora": hora},
    )
    _audit(
        db, current_user, "LIBERAR_MUELLE", "proveedores", id,
        {"muelle_descargue": muelle_anterior},
        {"muelle_descargue": None, "muelle_numero": muelle_anterior, "hora_muelle_liberado": hora},
    )
    db.commit()
    return {"message": "Muelle liberado"}


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
            # Mismo ciclo que crear(): nace 'pendiente', sin hora_ingreso_confirmado
            # (se puebla solo vía /proveedores/{id}/confirmar-ingreso).
            vals["estado_confirmacion"] = "pendiente"
            if not (vals.get("nombre_conductor") or "").strip():
                raise HTTPException(400, "El nombre del conductor es obligatorio")
            if not (vals.get("cedula_conductor") or "").strip():
                raise HTTPException(400, "La cédula del conductor es obligatoria")
            cols = ", ".join(vals.keys())
            placeholders = ", ".join(f":{k}" for k in vals.keys())
            db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
            orden_data = {c: reg.get(c) for c in CAMPOS_ORDEN}
            if any(v for v in orden_data.values()):
                _insert_ordenes(db, rid, [orden_data])
            ids.append(rid)
        db.commit()
    except IntegrityError as e:
        _raise_error_insercion(db, e)
    except DataError:
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa las fechas y los campos de selección (tipo de documento, tipo/formato de carga, quién maneja la carga).")
    return {"ids": ids, "message": f"{len(ids)} registros creados"}
