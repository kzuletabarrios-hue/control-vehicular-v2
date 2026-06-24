# backend/routers/busqueda.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import get_current_user

router = APIRouter()


@router.get("")
def buscar(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    q = (q or "").strip()
    if len(q) < 2:
        return {"items": []}

    permisos = current_user.get("permisos") or {}
    like = f"%{q}%"
    items = []

    if "read" in permisos.get("flota", []):
        rows = db.execute(text("""
            SELECT id, fecha, placa, conductor,
                   hora_salida_cedi, hora_llegada
            FROM flota_propia
            WHERE placa ILIKE :q OR conductor ILIKE :q
            ORDER BY fecha DESC LIMIT 10
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            estado = "Regresó" if d["hora_llegada"] else ("En ruta" if d["hora_salida_cedi"] else "En bodega")
            items.append({
                "modulo": "flota", "modulo_label": "Flota Propia",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["placa"], "detalle": d["conductor"],
                "estado": estado,
            })

    if "read" in permisos.get("proveedores", []):
        rows = db.execute(text("""
            SELECT id, fecha, placa_vehiculo, nombre_conductor, hora_salida
            FROM proveedores
            WHERE placa_vehiculo ILIKE :q OR nombre_conductor ILIKE :q
            ORDER BY fecha DESC LIMIT 10
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            estado = "Salió" if d["hora_salida"] else "Dentro"
            items.append({
                "modulo": "prov", "modulo_label": "Proveedores",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["placa_vehiculo"], "detalle": d["nombre_conductor"],
                "estado": estado,
            })

    if "read" in permisos.get("control_acceso", []):
        rows = db.execute(text("""
            SELECT id, fecha, nombre, contratista, cedula, hora_salida
            FROM control_acceso
            WHERE nombre ILIKE :q OR contratista ILIKE :q OR CAST(cedula AS TEXT) ILIKE :q
            ORDER BY fecha DESC LIMIT 10
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            estado = "Salió" if d["hora_salida"] else "Dentro"
            items.append({
                "modulo": "acceso", "modulo_label": "Control Acceso",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["nombre"], "detalle": d["contratista"],
                "estado": estado,
            })

        rows = db.execute(text("""
            SELECT id, fecha, descripcion, responsable
            FROM sustancias
            WHERE descripcion ILIKE :q OR responsable ILIKE :q
            ORDER BY fecha DESC LIMIT 5
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            items.append({
                "modulo": "sust", "modulo_label": "Sustancias",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["descripcion"], "detalle": d["responsable"],
                "estado": "Registrado",
            })

        rows = db.execute(text("""
            SELECT id, fecha, descripcion, responsable
            FROM herramientas
            WHERE descripcion ILIKE :q OR responsable ILIKE :q
            ORDER BY fecha DESC LIMIT 5
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            items.append({
                "modulo": "herr", "modulo_label": "Herramientas",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["descripcion"], "detalle": d["responsable"],
                "estado": "Registrado",
            })

    if "read" in permisos.get("visita_vehicular", []):
        rows = db.execute(text("""
            SELECT id, fecha, placa, conductor, hora_salida
            FROM visita_vehicular
            WHERE placa ILIKE :q OR conductor ILIKE :q
            ORDER BY fecha DESC LIMIT 10
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            estado = "Salió" if d["hora_salida"] else "Dentro"
            items.append({
                "modulo": "visitavh", "modulo_label": "Visita Vehicular",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["placa"], "detalle": d["conductor"],
                "estado": estado,
            })

    if "read" in permisos.get("visitantes", []):
        rows = db.execute(text("""
            SELECT id, fecha, nombre, empresa, cedula, hora_salida
            FROM visitantes
            WHERE nombre ILIKE :q OR empresa ILIKE :q OR CAST(cedula AS TEXT) ILIKE :q
            ORDER BY fecha DESC LIMIT 10
        """), {"q": like}).fetchall()
        for r in rows:
            d = dict(r._mapping)
            estado = "Salió" if d["hora_salida"] else "Dentro"
            items.append({
                "modulo": "visit", "modulo_label": "Visitantes",
                "id": d["id"], "fecha": d["fecha"],
                "identificador": d["nombre"], "detalle": d["empresa"],
                "estado": estado,
            })

    items.sort(key=lambda x: x["fecha"] or "", reverse=True)
    return {"items": items}
