import base64
import os
import uuid

import requests as req
from fastapi import APIRouter, Body, Depends, HTTPException

from routers.auth import get_current_user

router = APIRouter()

BUCKET = "fotos"


# Fallback de desarrollo solo para la URL del proyecto: NO es secreta (el
# navegador la ve en cualquier request a Supabase), asi que si falta la env
# var se advierte explicitamente en logs y se sigue con el fallback para no
# fallar en silencio con un proyecto que no es el de produccion.
#
# La service role key SI es un secreto real: bypassa RLS y las politicas de
# Storage (el bucket "fotos" solo permite INSERT/DELETE con esta key). Nunca
# debe hardcodearse en el codigo fuente ni loguearse; vive unicamente en la
# variable de entorno SUPABASE_SERVICE_ROLE_KEY del servidor.
_SUPABASE_URL_FALLBACK = "https://vhzxtgrpnztwntoqhfaf.supabase.co"


def _get_service_role_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno SUPABASE_SERVICE_ROLE_KEY. "
            "Es requerida para subir/borrar objetos en el bucket 'fotos' de "
            "Supabase Storage y no tiene (ni debe tener) fallback hardcodeado "
            "por ser un secreto con privilegios de escritura/borrado."
        )
    return key


def _storage_upload(img_bytes: bytes, filename: str) -> str:
    if not os.environ.get("SUPABASE_URL"):
        print(
            "ADVERTENCIA: SUPABASE_URL no está definida en las variables de "
            "entorno, usando fallback de desarrollo hardcodeado."
        )
    supabase_url = os.environ.get("SUPABASE_URL", _SUPABASE_URL_FALLBACK).rstrip("/")

    try:
        service_role_key = _get_service_role_key()
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))

    upload_url = f"{supabase_url}/storage/v1/object/{BUCKET}/{filename}"
    r = req.post(
        upload_url,
        data=img_bytes,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "image/jpeg",
        },
        timeout=30,
    )
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"Error Supabase Storage: {r.text}")

    return f"{supabase_url}/storage/v1/object/public/{BUCKET}/{filename}"


@router.post("/upload-foto")
def upload_foto(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    data = body.get("data", "")
    if not data:
        raise HTTPException(400, "Sin imagen")

    if "," in data:
        data = data.split(",", 1)[1]

    try:
        img_bytes = base64.b64decode(data)
    except Exception:
        raise HTTPException(400, "Imagen inválida (base64 malformado)")

    filename = f"{uuid.uuid4()}.jpg"
    url = _storage_upload(img_bytes, filename)
    return {"url": url}
