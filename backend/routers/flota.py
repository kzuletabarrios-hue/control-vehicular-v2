# backend/routers/flota.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import get_current_user, require_permiso
from utils_placas import normalizar_placa

router = APIRouter()


# ── Validaciones de campos obligatorios (auditoría de datos faltantes) ──
# Viven en el endpoint (no en la BD) para no romper cargas masivas ni
# correcciones históricas: solo aplican al crear un registro y al CERRAR
# la salida del CEDI o la llegada (transición de vacío -> con hora).
TEMP_MIN, TEMP_MAX = -30.0, 30.0

# Obligatorios en el ALTA (POST). El 0 es válido en pallets/contenedores
# ("N/A" se guarda como 0 porque la columna es INT). No aplica a duplicar ni
# a cargas masivas, que no pasan por este endpoint.
CAMPOS_ALTA_OBLIGATORIOS = [
    ("muelle_cargue", "muelle de cargue"),
    ("n_pallets", "N° pallets"),
    ("n_contenedores", "N° contenedores"),
    ("cant_volumen_externo", "volumen externo"),
    ("tienda_1", "tienda 1"),
    ("protocolo", "protocolo"),
    ("observacion", "observación"),
]


def _vacio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _sello_invalido(v) -> bool:
    """Vacío o compuesto solo de ceros ('0', '0000')."""
    if _vacio(v):
        return True
    s = str(v).strip()
    return s.strip("0") == ""


def _valor(body: dict, antes, campo: str):
    """Valor del body si viene en la petición; si no, el ya guardado."""
    if campo in body:
        return body[campo]
    return antes._mapping.get(campo) if antes is not None else None


def _validar_temperatura(v):
    if _vacio(v):
        raise HTTPException(422, "La temperatura es obligatoria para registrar la salida del CEDI (usa N/A si no aplica)")
    if str(v).strip().upper() == "N/A":
        return  # "No aplica" declarado explícitamente por el guarda
    try:
        t = float(str(v).strip().replace(",", "."))
    except (ValueError, TypeError):
        raise HTTPException(422, "La temperatura debe ser un número válido")
    if t != t or not (TEMP_MIN <= t <= TEMP_MAX):
        raise HTTPException(422, f"La temperatura debe estar entre {TEMP_MIN:g} y {TEMP_MAX:g} °C")


def _tiene_conductor(texto, codigo, db) -> bool:
    if not _vacio(texto):
        return True
    if _vacio(codigo):
        return False
    try:
        return db.execute(
            text("SELECT 1 FROM conductores WHERE codigo = :c"), {"c": int(codigo)}
        ).fetchone() is not None
    except (ValueError, TypeError):
        return False



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

    where_sql = ' AND '.join(where)
    rows = db.execute(text(f"""
        WITH base AS (
            SELECT f.*, c.conductor AS nombre_conductor_bd,
                   (f.placa IS NOT NULL AND v.placa IS NULL) AS placa_no_verificada
            FROM flota_propia f
            LEFT JOIN conductores c ON f.codigo_conductor = c.codigo
            LEFT JOIN vehiculos v ON v.placa = f.placa AND v.activo = TRUE
            WHERE {where_sql}
        )
        SELECT * FROM base WHERE hora_llegada IS NULL
        UNION ALL
        SELECT * FROM (
            SELECT * FROM base WHERE hora_llegada IS NOT NULL
            ORDER BY fecha DESC, created_at DESC
            LIMIT :limit OFFSET :offset
        ) cerrados
        ORDER BY fecha DESC, created_at DESC
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM flota_propia f
        WHERE {' AND '.join(where)}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "items": [dict(r._mapping) for r in rows]}


# Lista de placas del maestro para el selector del formulario de Flota.
# Va antes de "/{id}" para que la ruta no se interprete como un id. Usa
# flota:read (no maestros:read) porque la necesitan los guardas que
# registran salidas, que no tienen acceso a Base de Datos.
@router.get("/vehiculos")
def vehiculos_activos(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    rows = db.execute(text(
        "SELECT placa, tipo FROM vehiculos WHERE activo = TRUE ORDER BY placa"
    )).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/{id}")
def obtener(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    row = db.execute(
        text("""
            SELECT f.*, (f.placa IS NOT NULL AND v.placa IS NULL) AS placa_no_verificada
            FROM flota_propia f
            LEFT JOIN vehiculos v ON v.placa = f.placa AND v.activo = TRUE
            WHERE f.id = :id
        """),
        {"id": id},
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
        "protocolo", "sello", "tipo_sello", "sello_entrada", "tipo_sello_entrada",
        "hora_salida_muelle", "temperatura", "hora_salida_cedi", "hora_llegada",
        "fecha_salida", "fecha_llegada",
        "observacion", "foto_url",
        "obs_salida", "foto_salida", "obs_llegada", "foto_llegada",
    ]
    vals = {c: body.get(c) for c in campos}
    if not _tiene_conductor(vals.get("conductor"), vals.get("codigo_conductor"), db):
        raise HTTPException(422, "El conductor es obligatorio (selecciónalo o escribe su nombre)")
    faltan = [
        nombre for campo, nombre in CAMPOS_ALTA_OBLIGATORIOS if _vacio(vals.get(campo))
    ]
    if faltan:
        raise HTTPException(
            422,
            "Campos obligatorios sin completar (usa N/A si no aplica): " + ", ".join(faltan),
        )
    vals["placa"] = normalizar_placa(vals.get("placa"))
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
        "protocolo", "sello", "tipo_sello", "sello_entrada", "tipo_sello_entrada",
        "hora_salida_muelle", "temperatura", "hora_salida_cedi", "hora_llegada",
        "fecha_salida", "fecha_llegada",
        "observacion", "foto_url",
        "obs_salida", "foto_salida", "obs_llegada", "foto_llegada",
    ]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    if "placa" in vals:
        vals["placa"] = normalizar_placa(vals["placa"])
    vals["id"] = id

    # Cierre de salida CEDI: solo cuando este PUT la registra por primera vez.
    if not _vacio(vals.get("hora_salida_cedi")) and _vacio(antes._mapping.get("hora_salida_cedi")):
        _validar_temperatura(_valor(vals, antes, "temperatura"))
        temp_final = _valor(vals, antes, "temperatura")
        # El motivo debe escribirse al cerrar la salida: una observación que ya
        # estaba guardada (p.ej. "carga con golpe") no cuenta como motivo.
        if str(temp_final).strip().upper() == "N/A":
            motivo = vals.get("obs_salida")
            previa = antes._mapping.get("obs_salida")
            if _vacio(motivo) or str(motivo).strip() == str(previa or "").strip():
                raise HTTPException(422, "Si la temperatura es N/A debes escribir el motivo en las observaciones de salida")
        if _sello_invalido(_valor(vals, antes, "sello")):
            raise HTTPException(422, "El N° de sello de salida es obligatorio y no puede ser solo ceros")
        if _vacio(_valor(vals, antes, "tipo_sello")):
            raise HTTPException(422, "El tipo de sello de salida es obligatorio (usa N/A si no aplica)")
        if not _tiene_conductor(_valor(vals, antes, "conductor"), _valor(vals, antes, "codigo_conductor"), db):
            raise HTTPException(422, "El conductor es obligatorio para registrar la salida del CEDI")
    # Cierre de llegada: solo cuando este PUT la registra por primera vez.
    if not _vacio(vals.get("hora_llegada")) and _vacio(antes._mapping.get("hora_llegada")):
        if _sello_invalido(_valor(vals, antes, "sello_entrada")):
            raise HTTPException(422, "El N° de sello de entrada es obligatorio y no puede ser solo ceros")
        if _vacio(_valor(vals, antes, "tipo_sello_entrada")):
            raise HTTPException(422, "El tipo de sello de entrada es obligatorio (usa N/A si no aplica)")

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
    from datetime import datetime, timedelta, timezone
    _BOG = timezone(timedelta(hours=-5))
    original = db.execute(
        text("SELECT * FROM flota_propia WHERE id = :id"), {"id": id}
    ).fetchone()
    if not original:
        raise HTTPException(404, "Registro no encontrado")

    d = dict(original._mapping)
    nuevo_id = str(uuid.uuid4())
    d["id"] = nuevo_id
    d["fecha"] = datetime.now(_BOG).date().isoformat()
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
