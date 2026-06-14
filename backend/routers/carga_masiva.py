# backend/routers/carga_masiva.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()


def _str(v) -> str | None:
    if v is None or v == "":
        return None
    return str(v).strip()


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ── CONDUCTORES ───────────────────────────────────────────────────

@router.post("/conductores")
def importar_conductores(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "write")),
):
    filas = body.get("filas", [])
    if not filas:
        raise HTTPException(400, "Sin filas para importar")

    insertados = actualizados = 0
    errores = []

    for i, fila in enumerate(filas):
        try:
            conductor = _str(fila.get("conductor"))
            if not conductor:
                errores.append({"fila": i + 2, "error": "Nombre del conductor requerido"})
                continue

            codigo = _int(fila.get("codigo"))

            existe = None
            if codigo is not None:
                existe = db.execute(
                    text("SELECT id FROM conductores WHERE codigo = :c"), {"c": codigo}
                ).fetchone()

            if existe:
                db.execute(text("""
                    UPDATE conductores
                    SET conductor=:conductor, n_cedula=:cedula, celular=:celular,
                        tipo=:tipo, updated_at=NOW()
                    WHERE codigo=:codigo
                """), {
                    "conductor": conductor,
                    "cedula": _str(fila.get("n_cedula")),
                    "celular": _str(fila.get("celular")),
                    "tipo": _str(fila.get("tipo")) or "Propio",
                    "codigo": codigo,
                })
                actualizados += 1
            else:
                db.execute(text("""
                    INSERT INTO conductores (id, codigo, conductor, n_cedula, celular, tipo)
                    VALUES (:id, :codigo, :conductor, :cedula, :celular, :tipo)
                """), {
                    "id": str(uuid.uuid4()),
                    "codigo": codigo,
                    "conductor": conductor,
                    "cedula": _str(fila.get("n_cedula")),
                    "celular": _str(fila.get("celular")),
                    "tipo": _str(fila.get("tipo")) or "Propio",
                })
                insertados += 1
        except Exception as e:
            db.rollback()
            errores.append({"fila": i + 2, "error": str(e)[:120]})

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

    return {"insertados": insertados, "actualizados": actualizados, "errores": errores}


# ── VEHÍCULOS ─────────────────────────────────────────────────────

@router.post("/vehiculos")
def importar_vehiculos(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "write")),
):
    filas = body.get("filas", [])
    if not filas:
        raise HTTPException(400, "Sin filas para importar")

    insertados = actualizados = 0
    errores = []

    for i, fila in enumerate(filas):
        try:
            placa = _str(fila.get("placa"))
            if not placa:
                errores.append({"fila": i + 2, "error": "Placa requerida"})
                continue
            placa = placa.upper().replace(" ", "")

            existe = db.execute(
                text("SELECT id FROM vehiculos WHERE placa = :p"), {"p": placa}
            ).fetchone()

            params = {
                "placa": placa,
                "marca": _str(fila.get("marca")),
                "modelo": _str(fila.get("modelo")),
                "color": _str(fila.get("color")),
                "anio": _int(fila.get("anio")),
                "tipo": _str(fila.get("tipo")),
                "capacidad": _str(fila.get("capacidad")),
            }

            if existe:
                db.execute(text("""
                    UPDATE vehiculos
                    SET marca=:marca, modelo=:modelo, color=:color, anio=:anio,
                        tipo=:tipo, capacidad=:capacidad, updated_at=NOW()
                    WHERE placa=:placa
                """), params)
                actualizados += 1
            else:
                params["id"] = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO vehiculos (id, placa, marca, modelo, color, anio, tipo, capacidad)
                    VALUES (:id, :placa, :marca, :modelo, :color, :anio, :tipo, :capacidad)
                """), params)
                insertados += 1
        except Exception as e:
            db.rollback()
            errores.append({"fila": i + 2, "error": str(e)[:120]})

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

    return {"insertados": insertados, "actualizados": actualizados, "errores": errores}


# ── EMPLEADOS (bd_control_acceso) ─────────────────────────────────

@router.post("/empleados")
def importar_empleados(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "write")),
):
    filas = body.get("filas", [])
    if not filas:
        raise HTTPException(400, "Sin filas para importar")

    insertados = actualizados = 0
    errores = []

    for i, fila in enumerate(filas):
        try:
            cedula_raw = fila.get("cedula")
            nombre = _str(fila.get("nombre"))
            if not cedula_raw or not nombre:
                errores.append({"fila": i + 2, "error": "Cédula y nombre requeridos"})
                continue

            try:
                cedula = int(str(cedula_raw).replace(".", "").replace(",", "").strip())
            except Exception:
                errores.append({"fila": i + 2, "error": f"Cédula inválida: {cedula_raw}"})
                continue

            estado = (_str(fila.get("estado")) or "ACTIVO").upper()
            if estado not in ("ACTIVO", "INACTIVO"):
                estado = "ACTIVO"

            existe = db.execute(
                text("SELECT cedula FROM bd_control_acceso WHERE cedula = :c"), {"c": cedula}
            ).fetchone()

            if existe:
                db.execute(text("""
                    UPDATE bd_control_acceso
                    SET nombre=:nombre, contratista=:contratista, estado=:estado, updated_at=NOW()
                    WHERE cedula=:cedula
                """), {
                    "nombre": nombre,
                    "contratista": _str(fila.get("contratista")),
                    "estado": estado,
                    "cedula": cedula,
                })
                actualizados += 1
            else:
                db.execute(text("""
                    INSERT INTO bd_control_acceso (cedula, nombre, contratista, estado)
                    VALUES (:cedula, :nombre, :contratista, :estado)
                """), {
                    "cedula": cedula,
                    "nombre": nombre,
                    "contratista": _str(fila.get("contratista")),
                    "estado": estado,
                })
                insertados += 1
        except Exception as e:
            db.rollback()
            errores.append({"fila": i + 2, "error": str(e)[:120]})

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

    return {"insertados": insertados, "actualizados": actualizados, "errores": errores}


# ── TIENDAS / DISTRIBUCIÓN ───────────────────────────────────────

@router.post("/tiendas")
def importar_tiendas(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("maestros", "write")),
):
    filas = body.get("filas", [])
    if not filas:
        raise HTTPException(400, "Sin filas para importar")

    insertados = actualizados = 0
    errores = []

    for i, fila in enumerate(filas):
        try:
            nombre = _str(fila.get("nombre") or fila.get("tienda") or fila.get("name"))
            if not nombre:
                errores.append({"fila": i + 2, "error": "Nombre requerido"})
                continue

            existe = db.execute(
                text("SELECT id FROM distribucion WHERE name = :n"), {"n": nombre}
            ).fetchone()

            if existe:
                actualizados += 1
            else:
                db.execute(
                    text("INSERT INTO distribucion (id, name) VALUES (uuid_generate_v4(), :n)"),
                    {"n": nombre}
                )
                insertados += 1
        except Exception as e:
            db.rollback()
            errores.append({"fila": i + 2, "error": str(e)[:120]})

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

    return {"insertados": insertados, "actualizados": actualizados, "errores": errores}


# ── LISTAR para verificación ──────────────────────────────────────

@router.get("/vehiculos")
def listar_vehiculos(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "read")),
):
    rows = db.execute(text("""
        SELECT * FROM vehiculos WHERE activo = TRUE ORDER BY placa ASC
    """)).fetchall()
    return [dict(r._mapping) for r in rows]
