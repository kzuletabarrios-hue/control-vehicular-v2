# backend/routers/bd_maestros.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database import get_db
from routers.auth import require_permiso
from utils_placas import normalizar_placa

router = APIRouter()


# ── DISTRIBUCIÓN (tiendas) ────────────────────────────────────────

@router.get("/distribucion")
def listar_distribucion(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    rows = db.execute(text("SELECT * FROM distribucion ORDER BY codigo ASC NULLS LAST, name ASC")).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/distribucion", status_code=201)
def crear_distribucion(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "El nombre es requerido")
    codigo = body.get("codigo")
    codigo = int(codigo) if codigo not in (None, "") else None
    direccion = (body.get("direccion") or "").strip() or None

    if codigo is not None:
        existe = db.execute(text("SELECT id FROM distribucion WHERE codigo = :c"), {"c": codigo}).fetchone()
        if existe:
            db.execute(text("""
                UPDATE distribucion SET name = :name, direccion = :direccion WHERE codigo = :codigo
            """), {"name": name, "direccion": direccion, "codigo": codigo})
            db.commit()
            return {"id": str(existe.id), "message": "Tienda actualizada"}

    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO distribucion (id, codigo, name, direccion) VALUES (:id, :codigo, :name, :direccion)
    """), {"id": rid, "codigo": codigo, "name": name, "direccion": direccion})
    db.commit()
    return {"id": rid, "message": "Tienda creada"}


@router.put("/distribucion/{id}")
def actualizar_distribucion(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "El nombre es requerido")
    codigo = body.get("codigo")
    codigo = int(codigo) if codigo not in (None, "") else None
    direccion = (body.get("direccion") or "").strip() or None

    db.execute(text("""
        UPDATE distribucion SET codigo = :codigo, name = :name, direccion = :direccion WHERE id = :id
    """), {"id": id, "codigo": codigo, "name": name, "direccion": direccion})
    db.commit()
    return {"message": "Tienda actualizada"}


@router.delete("/distribucion/{id}")
def eliminar_distribucion(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("DELETE FROM distribucion WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Tienda eliminada"}


# ── BD PROVEEDORES ────────────────────────────────────────────────

@router.get("/proveedores")
def listar_bd_proveedores(
    q: str = None,
    activo: bool = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    where = ["1=1"]
    params = {}
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = activo
    if q:
        where.append("(nombre ILIKE :q OR nit ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM bd_proveedores
        WHERE {' AND '.join(where)}
        ORDER BY nombre ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/proveedores", status_code=201)
def crear_bd_proveedor(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre es requerido")
    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO bd_proveedores (id, nombre, nit, contacto, celular, activo)
        VALUES (:id, :nombre, :nit, :contacto, :celular, :activo)
    """), {
        "id": rid,
        "nombre": nombre,
        "nit": body.get("nit"),
        "contacto": body.get("contacto"),
        "celular": body.get("celular"),
        "activo": body.get("activo", True),
    })
    db.commit()
    return {"id": rid, "message": "Proveedor creado"}


@router.put("/proveedores/{id}")
def actualizar_bd_proveedor(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    campos = ["nombre", "nit", "contacto", "celular", "activo"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE bd_proveedores SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Proveedor actualizado"}


@router.delete("/proveedores/{id}")
def eliminar_bd_proveedor(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("UPDATE bd_proveedores SET activo = FALSE, updated_at = NOW() WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Proveedor desactivado"}


# ── BD CONTROL ACCESO ─────────────────────────────────────────────

@router.get("/control-acceso")
def listar_bd_ca(
    q: str = None,
    estado: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    where = ["1=1"]
    params = {}
    if estado:
        where.append("estado = :estado")
        params["estado"] = estado
    if q:
        where.append("(nombre ILIKE :q OR CAST(cedula AS TEXT) ILIKE :q OR contratista ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM bd_control_acceso
        WHERE {' AND '.join(where)}
        ORDER BY nombre ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/control-acceso", status_code=201)
def crear_bd_ca(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    cedula = body.get("cedula")
    nombre = (body.get("nombre") or "").strip()
    if not cedula or not nombre:
        raise HTTPException(400, "Cédula y nombre son requeridos")
    db.execute(text("""
        INSERT INTO bd_control_acceso (cedula, nombre, contratista, estado)
        VALUES (:cedula, :nombre, :contratista, :estado)
        ON CONFLICT (cedula) DO UPDATE SET nombre = EXCLUDED.nombre, contratista = EXCLUDED.contratista
    """), {
        "cedula": int(cedula),
        "nombre": nombre,
        "contratista": body.get("contratista"),
        "estado": body.get("estado", "ACTIVO"),
    })
    db.commit()
    return {"cedula": cedula, "message": "Persona registrada en BD"}


@router.put("/control-acceso/{cedula}")
def actualizar_bd_ca(
    cedula: int,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    campos = ["nombre", "contratista", "estado"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["cedula"] = cedula
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "cedula")
    db.execute(text(f"UPDATE bd_control_acceso SET {sets}, updated_at = NOW() WHERE cedula = :cedula"), vals)
    db.commit()
    return {"message": "Registro actualizado"}


@router.delete("/control-acceso/{cedula}")
def eliminar_bd_ca(
    cedula: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("UPDATE bd_control_acceso SET estado = 'INACTIVO', updated_at = NOW() WHERE cedula = :cedula"), {"cedula": cedula})
    db.commit()
    return {"message": "Persona marcada como inactiva"}


# ── CONDUCTORES FRECUENTES ────────────────────────────────────────

@router.get("/conductores-frecuentes")
def listar_conductores_frecuentes(
    cedula: str = None,
    q: str = None,
    activo: bool = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    where = ["1=1"]
    params = {}
    if cedula:
        where.append("cedula = :cedula")
        params["cedula"] = cedula
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = activo
    if q:
        where.append("(nombre_conductor ILIKE :q OR cedula ILIKE :q OR empresa_principal ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM conductores_frecuentes
        WHERE {' AND '.join(where)}
        ORDER BY ultima_visita DESC NULLS LAST, nombre_conductor ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/conductores-frecuentes", status_code=201)
def crear_conductor_frecuente(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    cedula = (body.get("cedula") or "").strip()
    nombre = (body.get("nombre_conductor") or "").strip()
    if not cedula or not nombre:
        raise HTTPException(400, "Cédula y nombre son requeridos")

    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO conductores_frecuentes
            (id, cedula, nombre_conductor, empresa_principal, tipo_vehiculo, telefono, activo, ultima_visita)
        VALUES (:id, :cedula, :nombre, :empresa, :tipo, :telefono, TRUE, :ultima_visita)
        ON CONFLICT (cedula) DO UPDATE SET
            nombre_conductor  = EXCLUDED.nombre_conductor,
            empresa_principal = COALESCE(EXCLUDED.empresa_principal, conductores_frecuentes.empresa_principal),
            tipo_vehiculo     = COALESCE(EXCLUDED.tipo_vehiculo, conductores_frecuentes.tipo_vehiculo),
            telefono          = COALESCE(EXCLUDED.telefono, conductores_frecuentes.telefono),
            activo            = TRUE,
            ultima_visita     = EXCLUDED.ultima_visita,
            updated_at        = NOW()
    """), {
        "id": rid,
        "cedula": cedula,
        "nombre": nombre,
        "empresa": body.get("empresa_principal") or None,
        "tipo": body.get("tipo_vehiculo") or None,
        "telefono": body.get("telefono") or None,
        "ultima_visita": body.get("ultima_visita") or None,
    })
    db.commit()
    row = db.execute(text("SELECT id FROM conductores_frecuentes WHERE cedula = :c"), {"c": cedula}).fetchone()
    return {"id": str(row.id), "message": "Conductor frecuente guardado"}


@router.put("/conductores-frecuentes/{id}")
def actualizar_conductor_frecuente(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    campos = ["nombre_conductor", "empresa_principal", "tipo_vehiculo", "telefono", "activo", "ultima_visita"]
    vals = {c: body[c] for c in campos if c in body}
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    db.execute(text(f"UPDATE conductores_frecuentes SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
    db.commit()
    return {"message": "Conductor frecuente actualizado"}


@router.delete("/conductores-frecuentes/{id}")
def desactivar_conductor_frecuente(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    db.execute(text("UPDATE conductores_frecuentes SET activo = FALSE, updated_at = NOW() WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Conductor marcado como inactivo"}


# ── MAESTRO DE VEHÍCULOS (alta individual) ───────────────────────
# Pestaña "Vehículos" de Base de Datos (decisión de la usuaria 2026-10-02,
# punto 3): admin/supervisor agregan, editan tipo/marca y desactivan
# vehículos del maestro `vehiculos` -- la misma tabla que ya alimenta la
# carga masiva (routers/carga_masiva.py) y que backend/routers/flota.py
# usa para calcular `placa_no_verificada`. No se agregan columnas: la
# tabla ya tiene placa UNIQUE (supabase/migrations/20260607112557_vehiculos.sql).
#
# Permiso: se reutiliza "maestros" (igual que el resto de este archivo)
# en vez de crear un módulo nuevo -- es exactamente la misma naturaleza
# de dato (catálogo de referencia administrado por admin/supervisor) que
# distribución/proveedores/control-acceso ya gestionados aquí. `admin` ya
# tenía maestros:write/delete; a `supervisor` (antes solo maestros:read)
# se le amplía con la migración
# supabase/migrations/20261002090000_permiso_maestros_write_supervisor.sql
# para que de verdad pueda agregar/editar/desactivar, no solo ver la lista.

CAMPOS_VEHICULO = ["placa", "marca", "modelo", "color", "anio", "tipo", "capacidad"]


def _normalizar_body_vehiculo(body: dict, requerir_placa: bool) -> dict:
    vals = {c: body[c] for c in CAMPOS_VEHICULO if c in body}
    if "placa" in vals:
        placa = normalizar_placa(vals["placa"])
        if not placa and requerir_placa:
            raise HTTPException(400, "La placa es requerida")
        vals["placa"] = placa
    elif requerir_placa:
        raise HTTPException(400, "La placa es requerida")
    if "anio" in vals and vals["anio"] not in (None, ""):
        try:
            vals["anio"] = int(vals["anio"])
        except (TypeError, ValueError):
            raise HTTPException(400, "El año debe ser un número")
    for c in ("marca", "modelo", "color", "tipo", "capacidad"):
        if c in vals and vals[c] is not None:
            vals[c] = str(vals[c]).strip() or None
    return vals


def _raise_error_vehiculo(db: Session, e: IntegrityError):
    db.rollback()
    if "vehiculos_placa_key" in str(e.orig) or "placa" in str(e.orig).lower():
        raise HTTPException(409, "Ya existe un vehículo con esa placa en el maestro")
    raise HTTPException(400, "No se pudo guardar el vehículo: revisa los datos")


@router.get("/vehiculos")
def listar_vehiculos_maestro(
    q: str = None,
    activo: bool = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "read")),
):
    where = ["1=1"]
    params = {}
    if activo is not None:
        where.append("activo = :activo")
        params["activo"] = activo
    if q:
        where.append("(placa ILIKE :q OR marca ILIKE :q OR tipo ILIKE :q)")
        params["q"] = f"%{q}%"

    rows = db.execute(text(f"""
        SELECT * FROM vehiculos
        WHERE {' AND '.join(where)}
        ORDER BY activo DESC, (tipo IS NULL OR tipo = '') DESC, placa ASC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/vehiculos", status_code=201)
def crear_vehiculo_maestro(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    vals = _normalizar_body_vehiculo(body, requerir_placa=True)
    rid = str(uuid.uuid4())
    vals["id"] = rid
    vals["activo"] = body.get("activo", True)
    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    try:
        db.execute(text(f"INSERT INTO vehiculos ({cols}) VALUES ({placeholders})"), vals)
        db.commit()
    except IntegrityError as e:
        _raise_error_vehiculo(db, e)
    return {"id": rid, "message": "Vehículo agregado al maestro"}


@router.put("/vehiculos/{id}")
def actualizar_vehiculo_maestro(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    existe = db.execute(text("SELECT id FROM vehiculos WHERE id = :id"), {"id": id}).fetchone()
    if not existe:
        raise HTTPException(404, "Vehículo no encontrado")

    vals = _normalizar_body_vehiculo(body, requerir_placa=False)
    if "activo" in body:
        vals["activo"] = bool(body["activo"])
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")
    vals["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in vals if c != "id")
    try:
        db.execute(text(f"UPDATE vehiculos SET {sets}, updated_at = NOW() WHERE id = :id"), vals)
        db.commit()
    except IntegrityError as e:
        _raise_error_vehiculo(db, e)
    return {"message": "Vehículo actualizado"}


@router.delete("/vehiculos/{id}")
def desactivar_vehiculo_maestro(
    id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "delete")),
):
    existe = db.execute(text("SELECT id FROM vehiculos WHERE id = :id"), {"id": id}).fetchone()
    if not existe:
        raise HTTPException(404, "Vehículo no encontrado")
    db.execute(text("UPDATE vehiculos SET activo = FALSE, updated_at = NOW() WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Vehículo desactivado"}
