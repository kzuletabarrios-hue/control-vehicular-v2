"""Tests funcionales de POST /api/auth/login: bloqueo temporal por fuerza
bruta (hallazgo CRÍTICO de la revisión de seguridad 2026-09-14, ver
docs/revision_seguridad_2026-09.md).

Corren contra el Postgres LOCAL de pruebas levantado con
`bash scripts/dev_test_db.sh reset` (backend/.env.test) -- el guardrail de
backend/conftest.py aborta TODA la sesión de pytest si DATABASE_URL
apuntara a producción, así que no hace falta repetir esa protección aquí.

Requiere que la migración supabase/migrations/
20260914150000_usuarios_bloqueo_login_columns.sql ya esté aplicada contra
la BD de pruebas (columnas usuarios.intentos_fallidos / bloqueado_hasta).

Cubre exactamente el contrato dejado por Jorge en esa migración y pedido
por Alejandro:
  1. Login exitoso resetea intentos_fallidos/bloqueado_hasta.
  2. Login fallido (password incorrecta, email existente) incrementa
     intentos_fallidos.
  3. El 5º fallido consecutivo bloquea la cuenta (bloqueado_hasta futuro).
  4. Un login durante el bloqueo se rechaza con 423 SIN llamar a
     verify_password() -- ni siquiera con la contraseña correcta.
  5. El bloqueo expira solo pasados los 15 minutos (sin job de limpieza):
     si bloqueado_hasta ya quedó en el pasado, el siguiente login exitoso
     funciona normal y resetea el contador.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from routers import auth as auth_router

client = TestClient(app)

TEST_EMAIL = "maria.test.bruteforce@example.test"
TEST_PASSWORD = "ClaveCorrecta123"
TEST_PASSWORD_MALA = "ClaveIncorrecta999"


@pytest.fixture()
def usuario_test():
    """Crea un usuario de prueba aislado (rol 'admin', sembrado por
    supabase/seed.sql) y lo borra al final -- no deja rastro entre tests
    ni depende de datos de otros usuarios."""
    db = SessionLocal()
    rol = db.execute(text("SELECT id FROM roles WHERE nombre = 'admin'")).fetchone()
    assert rol, "supabase/seed.sql debería traer sembrado el rol 'admin'"

    uid = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO usuarios (id, nombre, email, password_hash, rol_id, activo)
            VALUES (:id, 'María Test Bruteforce', :email, :ph, :rid, TRUE)
        """),
        {
            "id": uid,
            "email": TEST_EMAIL,
            "ph": auth_router.hash_password(TEST_PASSWORD),
            "rid": rol.id,
        },
    )
    db.commit()
    db.close()

    yield uid

    db = SessionLocal()
    db.execute(text("DELETE FROM sesiones WHERE usuario_id = :id"), {"id": uid})
    db.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": uid})
    db.commit()
    db.close()


def _estado_usuario(uid: str):
    db = SessionLocal()
    row = db.execute(
        text("SELECT intentos_fallidos, bloqueado_hasta FROM usuarios WHERE id = :id"),
        {"id": uid},
    ).fetchone()
    db.close()
    return row.intentos_fallidos, row.bloqueado_hasta


def _set_estado_usuario(uid: str, intentos_fallidos: int, bloqueado_hasta):
    db = SessionLocal()
    db.execute(
        text("UPDATE usuarios SET intentos_fallidos = :n, bloqueado_hasta = :b WHERE id = :id"),
        {"n": intentos_fallidos, "b": bloqueado_hasta, "id": uid},
    )
    db.commit()
    db.close()


def _login(email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_exitoso_resetea_contador(usuario_test):
    _set_estado_usuario(usuario_test, intentos_fallidos=3, bloqueado_hasta=None)

    resp = _login(TEST_EMAIL, TEST_PASSWORD)

    assert resp.status_code == 200
    intentos, bloqueado_hasta = _estado_usuario(usuario_test)
    assert intentos == 0
    assert bloqueado_hasta is None


def test_login_fallido_incrementa_contador(usuario_test):
    intentos_antes, _ = _estado_usuario(usuario_test)
    assert intentos_antes == 0

    resp = _login(TEST_EMAIL, TEST_PASSWORD_MALA)

    assert resp.status_code == 401
    intentos_despues, bloqueado_hasta = _estado_usuario(usuario_test)
    assert intentos_despues == 1
    assert bloqueado_hasta is None  # todavía no llega al umbral


def test_quinto_fallido_consecutivo_bloquea_la_cuenta(usuario_test):
    for i in range(1, auth_router.LOGIN_INTENTOS_MAX + 1):
        resp = _login(TEST_EMAIL, TEST_PASSWORD_MALA)
        assert resp.status_code == 401, f"intento {i} debería seguir respondiendo 401 (no 423)"

    intentos, bloqueado_hasta = _estado_usuario(usuario_test)
    assert intentos == auth_router.LOGIN_INTENTOS_MAX
    assert bloqueado_hasta is not None
    assert bloqueado_hasta > datetime.now(timezone.utc)

    # Un intento adicional, ya con la cuenta bloqueada, debe rechazarse con 423.
    resp_bloqueado = _login(TEST_EMAIL, TEST_PASSWORD_MALA)
    assert resp_bloqueado.status_code == 423
    assert "Retry-After" in resp_bloqueado.headers


def test_login_durante_bloqueo_se_rechaza_sin_llamar_verify_password(usuario_test):
    futuro = datetime.now(timezone.utc) + timedelta(minutes=10)
    _set_estado_usuario(usuario_test, intentos_fallidos=auth_router.LOGIN_INTENTOS_MAX, bloqueado_hasta=futuro)

    with patch.object(auth_router, "verify_password") as mock_verify:
        # Contraseña CORRECTA a propósito: aunque el password sea válido,
        # el bloqueo debe rechazar el intento antes de siquiera verificarlo.
        resp = _login(TEST_EMAIL, TEST_PASSWORD)

    assert resp.status_code == 423
    mock_verify.assert_not_called()

    # El bloqueo no debió alterarse por este intento rechazado.
    intentos, bloqueado_hasta = _estado_usuario(usuario_test)
    assert intentos == auth_router.LOGIN_INTENTOS_MAX
    assert bloqueado_hasta == futuro


def test_bloqueo_expira_solo_tras_los_15_minutos(usuario_test):
    pasado = datetime.now(timezone.utc) - timedelta(seconds=1)
    _set_estado_usuario(usuario_test, intentos_fallidos=auth_router.LOGIN_INTENTOS_MAX, bloqueado_hasta=pasado)

    # bloqueado_hasta ya quedó en el pasado -> se trata como no-bloqueada,
    # sin ningún job de limpieza de por medio.
    resp = _login(TEST_EMAIL, TEST_PASSWORD)

    assert resp.status_code == 200
    intentos, bloqueado_hasta = _estado_usuario(usuario_test)
    assert intentos == 0
    assert bloqueado_hasta is None


def test_login_email_inexistente_sigue_respondiendo_401_generico_sin_tocar_bd():
    resp = _login("no-existe-en-ningun-lado@example.test", "cualquier-cosa")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenciales incorrectas"
