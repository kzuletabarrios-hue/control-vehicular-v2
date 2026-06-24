# backend/routers/novedades.py
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import get_current_user

router = APIRouter()

ROLES_GESTION = ('admin', 'supervisor')
MODULOS_VALIDOS   = ('flota', 'proveedores', 'acceso', 'visitantes', 'ronda', 'general')
CATEGORIAS_VALIDAS = ('seguridad', 'mantenimiento', 'logistica', 'otro')
ESTADOS_VALIDOS    = ('abierta', 'en_revision', 'cerrada')


@router.get("")
def listar(
    estado: str = None,
    modulo: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    where  = ["1=1"]
    params = {"limit": limit}

    if user['rol'] not in ROLES_GESTION:
        where.append("n.usuario_id = :uid")
        params["uid"] = user["id"]
    if estado:
        where.append("n.estado = :estado")
        params["estado"] = estado
    if modulo:
        where.append("n.modulo_origen = :modulo")
        params["modulo"] = modulo

    rows = db.execute(text(f"""
        SELECT n.*, u.nombre AS usuario_nombre
        FROM novedades n
        JOIN usuarios u ON u.id = n.usuario_id
        WHERE {' AND '.join(where)}
        ORDER BY n.created_at DESC
        LIMIT :limit
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("", status_code=201)
def crear(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    descripcion = (body.get("descripcion") or "").strip()
    if not descripcion:
        raise HTTPException(400, "La descripción es requerida")

    modulo    = body.get("modulo_origen", "general")
    categoria = body.get("categoria", "otro")

    if modulo not in MODULOS_VALIDOS:
        modulo = "general"
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "otro"

    rid  = str(uuid.uuid4())
    hora = datetime.now().strftime("%H:%M:%S")

    db.execute(text("""
        INSERT INTO novedades
            (id, usuario_id, modulo_origen, categoria, descripcion, fotografia, fecha, hora)
        VALUES
            (:id, :usuario_id, :modulo_origen, :categoria, :descripcion, :fotografia, CURRENT_DATE, :hora)
    """), {
        "id": rid,
        "usuario_id":    user["id"],
        "modulo_origen": modulo,
        "categoria":     categoria,
        "descripcion":   descripcion,
        "fotografia":    body.get("fotografia") or None,
        "hora":          hora,
    })
    db.commit()
    return {"id": rid, "message": "Novedad registrada"}


@router.patch("/{id}/estado")
def cambiar_estado(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user['rol'] not in ROLES_GESTION:
        raise HTTPException(403, "Solo admin/supervisor pueden cambiar el estado")

    nuevo = body.get("estado")
    if nuevo not in ESTADOS_VALIDOS:
        raise HTTPException(400, f"Estado inválido. Valores permitidos: {', '.join(ESTADOS_VALIDOS)}")

    existe = db.execute(text("SELECT 1 FROM novedades WHERE id = :id"), {"id": id}).fetchone()
    if not existe:
        raise HTTPException(404, "Novedad no encontrada")

    db.execute(
        text("UPDATE novedades SET estado = :estado WHERE id = :id"),
        {"estado": nuevo, "id": id}
    )
    db.commit()
    return {"message": "Estado actualizado"}
