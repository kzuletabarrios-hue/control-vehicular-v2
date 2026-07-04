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
    "telefono_conductor", "tipo_vehiculo", "muelle_descargue",
]


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

    placa     = (vehiculo.get("placa_vehiculo") or "").strip().upper()
    conductor = (vehiculo.get("nombre_conductor") or "").strip()
    if not placa:
        raise HTTPException(400, "La placa es obligatoria")
    if not conductor:
        raise HTTPException(400, "El nombre del conductor es obligatorio")
    if not ordenes or not any((o.get("empresa") or "").strip() for o in ordenes):
        raise HTTPException(400, "Agrega al menos una empresa/orden a la que vienes a entregar")

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
