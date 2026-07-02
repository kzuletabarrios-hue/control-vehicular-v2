# backend/routers/auth.py
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db

router = APIRouter()

SECRET_KEY     = os.getenv("SECRET_KEY", "CAMBIAR_EN_PRODUCCION_clave_muy_larga_y_aleatoria")
ACCESS_EXPIRE  = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))      # 1 hora
REFRESH_EXPIRE = int(os.getenv("REFRESH_TOKEN_DAYS",   "30"))      # 30 días
ALGORITHM      = "HS256"


# ── HELPERS ──────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        # $2a$ (Supabase crypt) y $2b$ son el mismo algoritmo; bcrypt de Python solo acepta $2b$
        normalized = hashed.replace("$2a$", "$2b$", 1)
        return bcrypt.checkpw(plain.encode(), normalized.encode())
    except Exception:
        return False


def create_access_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE)
    data["type"] = "access"
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    return str(uuid.uuid4()) + str(uuid.uuid4()).replace("-", "")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ── DEPENDENCY: usuario autenticado ──────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = auth.split(" ", 1)[1]
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Tipo de token inválido")

    user = db.execute(
        text("""
            SELECT u.id, u.nombre, u.email, u.activo, r.nombre AS rol, r.permisos
            FROM usuarios u JOIN roles r ON u.rol_id = r.id
            WHERE u.id = :uid
        """),
        {"uid": payload["sub"]}
    ).fetchone()

    if not user or not user.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo o no encontrado")

    return dict(user._mapping)


def require_permiso(modulo: str, accion: str):
    """Factoría de dependencia para verificar permisos."""
    def check(current_user: dict = Depends(get_current_user)):
        permisos = current_user.get("permisos") or {}
        acciones = permisos.get(modulo, [])
        if accion not in acciones:
            raise HTTPException(
                status_code=403,
                detail=f"Sin permiso para '{accion}' en '{modulo}'"
            )
        return current_user
    return check


# ── ENDPOINTS ────────────────────────────────────────────────────

@router.post("/login")
def login(body: dict, request: Request, db: Session = Depends(get_db)):
    """
    Body: { "email": "...", "password": "..." }
    """
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email y contraseña requeridos")

    user = db.execute(
        text("""
            SELECT u.id, u.nombre, u.email, u.password_hash, u.activo,
                   r.nombre AS rol, r.permisos
            FROM usuarios u JOIN roles r ON u.rol_id = r.id
            WHERE u.email = :email
        """),
        {"email": email}
    ).fetchone()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not user.activo:
        raise HTTPException(status_code=403, detail="Usuario desactivado")

    access_token  = create_access_token({"sub": str(user.id), "rol": user.rol})
    refresh_token = create_refresh_token()

    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE)
    db.execute(
        text("""
            INSERT INTO sesiones (id, usuario_id, refresh_token, ip_address, user_agent, expires_at)
            VALUES (:id, :uid, :rt, :ip, :ua, :exp)
        """),
        {
            "id":  str(uuid.uuid4()),
            "uid": str(user.id),
            "rt":  refresh_token,
            "ip":  request.client.host if request.client else None,
            "ua":  request.headers.get("User-Agent"),
            "exp": expires,
        }
    )
    db.execute(
        text("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = :id"),
        {"id": str(user.id)}
    )
    db.commit()

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "expires_in":    ACCESS_EXPIRE * 60,
        "usuario": {
            "id":     str(user.id),
            "nombre": user.nombre,
            "email":  user.email,
            "rol":    user.rol,
        }
    }


@router.post("/refresh")
def refresh(body: dict, db: Session = Depends(get_db)):
    """
    Body: { "refresh_token": "..." }
    Devuelve un nuevo access_token sin requerir contraseña.
    """
    rt = body.get("refresh_token", "")
    if not rt:
        raise HTTPException(status_code=400, detail="refresh_token requerido")

    sesion = db.execute(
        text("""
            SELECT s.usuario_id, s.expires_at, s.revocada,
                   u.activo, u.nombre, u.email, r.nombre AS rol
            FROM sesiones s
            JOIN usuarios u ON s.usuario_id = u.id
            JOIN roles    r ON u.rol_id = r.id
            WHERE s.refresh_token = :rt
        """),
        {"rt": rt}
    ).fetchone()

    if not sesion:
        raise HTTPException(status_code=401, detail="Sesión no encontrada")
    if sesion.revocada:
        raise HTTPException(status_code=401, detail="Sesión revocada")
    if sesion.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sesión expirada")
    if not sesion.activo:
        raise HTTPException(status_code=403, detail="Usuario desactivado")

    new_token = create_access_token({
        "sub": str(sesion.usuario_id),
        "rol": sesion.rol
    })
    return {"access_token": new_token, "token_type": "bearer"}


@router.post("/logout")
def logout(body: dict, db: Session = Depends(get_db)):
    """Body: { "refresh_token": "..." }"""
    rt = body.get("refresh_token", "")
    db.execute(
        text("UPDATE sesiones SET revocada = TRUE WHERE refresh_token = :rt"),
        {"rt": rt}
    )
    db.commit()
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    """Retorna los datos del usuario autenticado."""
    current_user.pop("permisos", None)
    return current_user


# ── GESTIÓN DE USUARIOS (solo admin) ─────────────────────────────

@router.get("/usuarios")
def listar_usuarios(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("usuarios", "read"))
):
    result = db.execute(text("""
        SELECT u.id, u.nombre, u.email, u.activo, u.ultimo_acceso,
               u.created_at, r.nombre AS rol
        FROM usuarios u JOIN roles r ON u.rol_id = r.id
        ORDER BY u.created_at DESC
    """))
    return [dict(r._mapping) for r in result]


@router.post("/usuarios", status_code=201)
def crear_usuario(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("usuarios", "write"))
):
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    nombre   = body.get("nombre") or ""
    rol      = body.get("rol") or "operador"

    if not email or not password or not nombre:
        raise HTTPException(status_code=400, detail="nombre, email y contraseña requeridos")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    rol_row = db.execute(
        text("SELECT id FROM roles WHERE nombre = :r"), {"r": rol}
    ).fetchone()
    if not rol_row:
        raise HTTPException(status_code=400, detail=f"Rol '{rol}' no existe")

    existente = db.execute(
        text("SELECT 1 FROM usuarios WHERE email = :e"), {"e": email}
    ).fetchone()
    if existente:
        raise HTTPException(status_code=409, detail="Email ya registrado")

    uid = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO usuarios (id, nombre, email, password_hash, rol_id, creado_por)
            VALUES (:id, :n, :e, :ph, :rid, :cp)
        """),
        {
            "id":  uid,
            "n":   nombre,
            "e":   email,
            "ph":  hash_password(password),
            "rid": rol_row.id,
            "cp":  current_user["id"],
        }
    )
    db.commit()
    return {"id": uid, "message": f"Usuario '{nombre}' creado con rol '{rol}'"}


# IMPORTANTE: esta ruta debe ir ANTES de /usuarios/{uid} para que FastAPI
# no capture "cambiar-password" como un valor de {uid}.
@router.put("/usuarios/cambiar-password")
def cambiar_password(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    actual = body.get("password_actual") or ""
    nueva  = body.get("password_nueva") or ""

    if len(nueva) < 8:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres")

    row = db.execute(
        text("SELECT password_hash FROM usuarios WHERE id = :id"),
        {"id": current_user["id"]}
    ).fetchone()

    if not row or not verify_password(actual, row.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    db.execute(
        text("UPDATE usuarios SET password_hash = :ph, updated_at = NOW() WHERE id = :id"),
        {"ph": hash_password(nueva), "id": current_user["id"]}
    )
    db.execute(
        text("UPDATE sesiones SET revocada = TRUE WHERE usuario_id = :id"),
        {"id": current_user["id"]}
    )
    db.commit()
    return {"message": "Contraseña actualizada. Vuelve a iniciar sesión."}


@router.put("/usuarios/{uid}")
def editar_usuario(
    uid: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("usuarios", "write"))
):
    campos = {}
    if "nombre" in body and body["nombre"]:
        campos["nombre"] = body["nombre"]
    if "email" in body and body["email"]:
        campos["email"] = body["email"].lower().strip()
    if "rol" in body and body["rol"]:
        rol_row = db.execute(
            text("SELECT id FROM roles WHERE nombre = :r"), {"r": body["rol"]}
        ).fetchone()
        if not rol_row:
            raise HTTPException(status_code=400, detail=f"Rol '{body['rol']}' no existe")
        campos["rol_id"] = rol_row.id
    if "password" in body and body["password"]:
        pw = body["password"]
        if len(pw) < 8:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
        campos["password_hash"] = hash_password(pw)

    if not campos:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")

    set_clause = ", ".join(f"{k} = :{k}" for k in campos)
    campos["id"] = uid
    db.execute(text(f"UPDATE usuarios SET {set_clause}, updated_at = NOW() WHERE id = :id"), campos)
    db.commit()
    return {"message": "Usuario actualizado"}


@router.put("/usuarios/{uid}/rol")
def cambiar_rol(
    uid: str,
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("usuarios", "write"))
):
    rol = body.get("rol") or ""
    rol_row = db.execute(
        text("SELECT id FROM roles WHERE nombre = :r"), {"r": rol}
    ).fetchone()
    if not rol_row:
        raise HTTPException(status_code=400, detail=f"Rol '{rol}' no existe")

    db.execute(
        text("UPDATE usuarios SET rol_id = :rid, updated_at = NOW() WHERE id = :id"),
        {"rid": rol_row.id, "id": uid}
    )
    db.commit()
    return {"message": "Rol actualizado"}


@router.put("/usuarios/{uid}/toggle")
def activar_desactivar(
    uid: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("usuarios", "write"))
):
    db.execute(
        text("UPDATE usuarios SET activo = NOT activo, updated_at = NOW() WHERE id = :id"),
        {"id": uid}
    )
    db.commit()
    return {"message": "Estado del usuario actualizado"}
