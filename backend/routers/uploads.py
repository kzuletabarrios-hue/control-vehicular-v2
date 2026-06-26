import base64
import os
import uuid

import requests as req
from fastapi import APIRouter, Body, Depends, HTTPException

from routers.auth import get_current_user

router = APIRouter()

BUCKET = "fotos"


def _storage_upload(img_bytes: bytes, filename: str) -> str:
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key  = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not service_key:
        raise HTTPException(500, "SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")

    upload_url = f"{supabase_url}/storage/v1/object/{BUCKET}/{filename}"
    r = req.post(
        upload_url,
        data=img_bytes,
        headers={
            "Authorization": f"Bearer {service_key}",
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
