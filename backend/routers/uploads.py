import base64
import os
import uuid

import requests as req
from fastapi import APIRouter, Body, Depends, HTTPException

from routers.auth import get_current_user

router = APIRouter()

BUCKET = "fotos"


# Fallbacks de desarrollo. La publishable key NO es secreta (solo da acceso
# al bucket "fotos", publico; las tablas siguen protegidas con RLS), pero si
# falta la env var se advierte explicitamente en logs para no fallar en
# silencio con un proyecto de Supabase que no es el de produccion.
_SUPABASE_URL_FALLBACK = "https://vhzxtgrpnztwntoqhfaf.supabase.co"
_SUPABASE_KEY_FALLBACK = "sb_publishable_2uJ9BDV4zSRAE7z24Ow4ag_xfKHdZXM"


def _storage_upload(img_bytes: bytes, filename: str) -> str:
    if not os.environ.get("SUPABASE_URL"):
        print(
            "ADVERTENCIA: SUPABASE_URL no está definida en las variables de "
            "entorno, usando fallback de desarrollo hardcodeado."
        )
    supabase_url = os.environ.get("SUPABASE_URL", _SUPABASE_URL_FALLBACK).rstrip("/")

    if not os.environ.get("SUPABASE_PUBLISHABLE_KEY"):
        print(
            "ADVERTENCIA: SUPABASE_PUBLISHABLE_KEY no está definida en las "
            "variables de entorno, usando fallback de desarrollo hardcodeado."
        )
    publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", _SUPABASE_KEY_FALLBACK)

    upload_url = f"{supabase_url}/storage/v1/object/{BUCKET}/{filename}"
    r = req.post(
        upload_url,
        data=img_bytes,
        headers={
            "apikey": publishable_key,
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
