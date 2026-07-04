# backend/routers/proveedores_publico.py
# Endpoints PUBLICOS (sin autenticacion) para que el conductor de un
# proveedor se autorregistre al llegar, escaneando el QR de la porteria.
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.proveedores import (
    CAMPOS_VEHICULO, CAMPOS_ORDEN, _clean, _insert_ordenes,
    validar_token_ingreso_qr,
)

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))

CAMPOS_VEHICULO_PUBLICOS = [
    "placa_vehiculo", "nombre_conductor", "cedula_conductor",
    "telefono_conductor", "tipo_vehiculo",
]
# Nota: muelle_descargue NO lo llena el conductor — el guarda lo asigna al
# confirmar el ingreso (ver PUT /api/proveedores/{id}).


@router.get("/token-info")
def token_info(token: str):
    validar_token_ingreso_qr(token)
    return {"valido": True}


@router.post("/autorregistro", status_code=201)
def autorregistro(
    body: dict,
    db: Session = Depends(get_db),
):
    token = body.get("token")
    validar_token_ingreso_qr(token)

    vehiculo = body.get("vehiculo") or {}
    ordenes  = body.get("ordenes") or []

    placa      = (vehiculo.get("placa_vehiculo") or "").strip().upper()
    conductor  = (vehiculo.get("nombre_conductor") or "").strip()
    cedula     = (vehiculo.get("cedula_conductor") or "").strip()
    telefono   = (vehiculo.get("telefono_conductor") or "").strip()
    tipo_veh   = (vehiculo.get("tipo_vehiculo") or "").strip()
    if not placa:
        raise HTTPException(400, "La placa es obligatoria")
    if not cedula:
        raise HTTPException(400, "La cédula del conductor es obligatoria")
    if not conductor:
        raise HTTPException(400, "El nombre del conductor es obligatorio")
    if not telefono:
        raise HTTPException(400, "El teléfono del conductor es obligatorio")
    if not tipo_veh:
        raise HTTPException(400, "El tipo de vehículo es obligatorio")
    if not ordenes:
        raise HTTPException(400, "Agrega al menos un proveedor/orden a la que vienes a entregar")
    for o in ordenes:
        if not (o.get("empresa") or "").strip():
            raise HTTPException(400, "Cada proveedor/orden debe tener nombre")
        if not (o.get("numero_orden_compra") or "").strip():
            raise HTTPException(400, "Cada proveedor/orden debe tener número de orden de compra")

    ahora = datetime.now(_BOG)
    rid = str(uuid.uuid4())
    vals = {c: _clean(vehiculo.get(c)) for c in CAMPOS_VEHICULO if c in CAMPOS_VEHICULO_PUBLICOS}
    vals["id"] = rid
    vals["placa_vehiculo"] = placa
    vals["nombre_conductor"] = conductor
    vals["fecha"] = ahora.date().isoformat()
    vals["hora_ingreso"] = ahora.strftime("%H:%M:%S")
    vals["estado_confirmacion"] = "pendiente"
    vals["origen"] = "autorregistro"
    vals["creado_por"] = None

    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
    _insert_ordenes(db, rid, ordenes)
    db.commit()
    return {"id": rid, "message": "Registro enviado. El guarda confirmará tu ingreso en un momento."}
