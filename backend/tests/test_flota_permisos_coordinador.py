"""Tests del invariante "coordinador ve la flota propia en solo-lectura"
(tarea de habilitación del rol coordinador para GET /api/flota, 2026-09-26).

Corren contra el Postgres LOCAL de pruebas levantado con
`bash scripts/dev_test_db.sh reset` (backend/.env.test) -- el guardrail de
backend/conftest.py aborta TODA la sesión de pytest si DATABASE_URL
apuntara a producción, así que no hace falta repetir esa protección aquí.

Usa los usuarios y datos ya sembrados por supabase/seed.sql
(coordinador@ejemplo.test / admin@ejemplo.test, contraseña común
'Test1234!' para todos los usuarios de seed) y el rol 'coordinador' dado
de alta formalmente en
supabase/migrations/20260804110000_alta_formal_coordinador_retroactivo.sql
(permisos reales en BD: {"flota": ["read"], ...}).

Cubre exactamente el contrato dejado en backend/routers/auth.py
(ROLES_SOLO_LECTURA_EN_ESTA_APP, _clamp_permisos_solo_lectura) y
backend/routers/flota.py (require_permiso por módulo/acción):

  1. Coordinador: GET /api/flota -> 200; GET /api/flota/{id} -> 200 (o 404
     si no existe, pero NUNCA 403); POST/PUT/DELETE de flota -> 403.
  2. El clamp: aunque el rol coordinador tuviera "write"/"delete" en
     roles.permisos (hoy no los tiene, pero la app no debe confiar en eso
     -- ver advertencia de
     20260807134610_verifica_rol_coordinador_solo_lectura.sql sobre que
     esta fila es compartida con citas-muelles-cedi-r10 y puede cambiar
     sin que esta app se entere), login y /me devuelven solo "read"
     (salvo la excepción puntual y documentada de citas:export).
     Se prueba primero de forma unitaria (_clamp_permisos_solo_lectura
     aislada) y luego de punta a punta ampliando temporalmente -- y
     restaurando siempre -- el JSONB roles.permisos de 'coordinador' en
     la BD LOCAL de pruebas.
  3. Control: el rol 'admin' (flota: ["read","write","delete","export"])
     no se ve afectado por el clamp (no está en
     ROLES_SOLO_LECTURA_EN_ESTA_APP) y puede operar el CRUD completo de
     flota de punta a punta.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from routers import auth as auth_router

client = TestClient(app)

# Contraseña común de TODOS los usuarios de supabase/seed.sql (ver
# comentario de cabecera de ese archivo).
SEED_PASSWORD = "Test1234!"
COORDINADOR_EMAIL = "coordinador@ejemplo.test"
ADMIN_EMAIL = "admin@ejemplo.test"


def _login(email: str, password: str = SEED_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _requiere_usuario_seed(email: str):
    """Precondición explícita: si el usuario de seed no existe, el
    entorno de pruebas no está sembrado correctamente -- se salta con un
    mensaje claro en vez de fallar de forma confusa más abajo (por
    ejemplo, 'coordinador' solo se siembra si la migración de alta
    formal de ese rol fue aplicada, ver cabecera de este archivo)."""
    db = SessionLocal()
    row = db.execute(text("SELECT 1 FROM usuarios WHERE email = :e"), {"e": email}).fetchone()
    db.close()
    if not row:
        pytest.skip(
            f"El usuario de seed '{email}' no existe en la BD de pruebas -- "
            "corre `bash scripts/dev_test_db.sh reset` para aplicar "
            "supabase/migrations/ + supabase/seed.sql."
        )


@pytest.fixture()
def token_coordinador():
    _requiere_usuario_seed(COORDINADOR_EMAIL)
    resp = _login(COORDINADOR_EMAIL)
    assert resp.status_code == 200, f"login de coordinador falló: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture()
def token_admin():
    _requiere_usuario_seed(ADMIN_EMAIL)
    resp = _login(ADMIN_EMAIL)
    assert resp.status_code == 200, f"login de admin falló: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture()
def registro_flota():
    """Crea directamente por SQL (sin pasar por el endpoint, para no
    depender del permiso de escritura que este mismo archivo prueba) un
    registro aislado de flota_propia y lo borra al final -- no depende
    de los 2 registros de ejemplo del seed (TST-001/TST-002) ni deja
    rastro entre tests."""
    db = SessionLocal()
    rid = str(uuid.uuid4())
    db.execute(
        text("INSERT INTO flota_propia (id, fecha, placa) VALUES (:id, CURRENT_DATE, :placa)"),
        {"id": rid, "placa": "QA-COORD-001"},
    )
    db.commit()
    db.close()

    yield rid

    db = SessionLocal()
    db.execute(text("DELETE FROM audit_log WHERE tabla = 'flota_propia' AND registro_id = :id"), {"id": rid})
    db.execute(text("DELETE FROM flota_propia WHERE id = :id"), {"id": rid})
    db.commit()
    db.close()


@pytest.fixture()
def permisos_coordinador_ampliados():
    """Amplía temporalmente (solo en la BD LOCAL de pruebas) el JSONB
    roles.permisos del rol 'coordinador' con acciones de escritura en
    varios módulos -- simula el escenario de riesgo documentado en
    20260807134610_verifica_rol_coordinador_solo_lectura.sql (esta fila
    es compartida con citas-muelles-cedi-r10 y puede ganar permisos de
    escritura sin que esta app se entere) -- y restaura el valor
    original al finalizar, pase lo que pase."""
    db = SessionLocal()
    row = db.execute(text("SELECT id, permisos FROM roles WHERE nombre = 'coordinador'")).fetchone()
    db.close()
    assert row, "El rol 'coordinador' debería existir (ver migración de alta formal 20260804110000)."

    rol_id = row.id
    permisos_originales = row.permisos

    permisos_ampliados = {
        "flota": ["read", "write", "delete", "export"],
        "citas": ["read", "write", "export"],
        "muelles": ["read", "asignar", "eliminar"],
    }

    db = SessionLocal()
    db.execute(
        text("UPDATE roles SET permisos = CAST(:p AS jsonb) WHERE id = :id"),
        {"p": json.dumps(permisos_ampliados), "id": rol_id},
    )
    db.commit()
    db.close()

    try:
        yield permisos_ampliados
    finally:
        db = SessionLocal()
        db.execute(
            text("UPDATE roles SET permisos = CAST(:p AS jsonb) WHERE id = :id"),
            {"p": json.dumps(permisos_originales), "id": rol_id},
        )
        db.commit()
        db.close()


# ── 1) Coordinador: lectura de flota permitida, escritura bloqueada ──


def test_coordinador_lista_flota_200(token_coordinador):
    resp = client.get("/api/flota", headers=_bearer(token_coordinador))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body


def test_coordinador_obtiene_registro_existente_200(token_coordinador, registro_flota):
    resp = client.get(f"/api/flota/{registro_flota}", headers=_bearer(token_coordinador))
    assert resp.status_code == 200
    assert resp.json()["id"] == registro_flota


def test_coordinador_obtiene_registro_inexistente_404_nunca_403(token_coordinador):
    resp = client.get(f"/api/flota/{uuid.uuid4()}", headers=_bearer(token_coordinador))
    assert resp.status_code == 404, (
        "Un id inexistente debe responder 404 (no encontrado), nunca 403: "
        "el permiso de lectura ya fue concedido, lo que falla es la búsqueda."
    )


def test_coordinador_no_puede_crear_flota_403(token_coordinador):
    resp = client.post(
        "/api/flota",
        json={"fecha": "2026-01-01", "placa": "QA-COORD-POST"},
        headers=_bearer(token_coordinador),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Sin permiso para 'write' en 'flota'"

    # Y no debió crear nada.
    db = SessionLocal()
    row = db.execute(text("SELECT 1 FROM flota_propia WHERE placa = 'QA-COORD-POST'")).fetchone()
    db.close()
    assert row is None


def test_coordinador_no_puede_editar_flota_403(token_coordinador, registro_flota):
    resp = client.put(
        f"/api/flota/{registro_flota}",
        json={"observacion": "intento de edición por coordinador"},
        headers=_bearer(token_coordinador),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Sin permiso para 'write' en 'flota'"

    # El registro no debió modificarse.
    db = SessionLocal()
    row = db.execute(text("SELECT observacion FROM flota_propia WHERE id = :id"), {"id": registro_flota}).fetchone()
    db.close()
    assert row.observacion is None


def test_coordinador_no_puede_duplicar_flota_403(token_coordinador, registro_flota):
    resp = client.post(f"/api/flota/{registro_flota}/duplicar", headers=_bearer(token_coordinador))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Sin permiso para 'write' en 'flota'"


def test_coordinador_no_puede_eliminar_flota_403(token_coordinador, registro_flota):
    resp = client.delete(f"/api/flota/{registro_flota}", headers=_bearer(token_coordinador))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Sin permiso para 'delete' en 'flota'"

    # El registro debió sobrevivir intacto.
    db = SessionLocal()
    row = db.execute(text("SELECT 1 FROM flota_propia WHERE id = :id"), {"id": registro_flota}).fetchone()
    db.close()
    assert row is not None


def test_coordinador_403_incluso_sin_token_no_es_lo_mismo_que_401():
    """Caso límite: sin Authorization header, GET /api/flota debe ser 401
    (no autenticado), no 403 -- distingue "no identificado" de
    "identificado pero sin permiso", que es lo que prueban los tests
    anteriores."""
    resp = client.get("/api/flota")
    assert resp.status_code == 401


# ── 2) Unit: _clamp_permisos_solo_lectura aislada ────────────────────


def test_clamp_reduce_write_y_delete_a_solo_read():
    entrada = {"flota": ["read", "write", "delete", "export"]}
    assert auth_router._clamp_permisos_solo_lectura(entrada) == {"flota": ["read"]}


def test_clamp_respeta_la_excepcion_puntual_de_citas_export():
    entrada = {"citas": ["read", "write", "export"]}
    salida = auth_router._clamp_permisos_solo_lectura(entrada)
    assert sorted(salida["citas"]) == ["export", "read"]


def test_clamp_no_generaliza_la_excepcion_a_otros_modulos():
    """La excepción de 'export' en ACCIONES_ADICIONALES_COORDINADOR es
    module-scoped (ver comentario de esa constante en auth.py): 'export'
    en un módulo que no sea 'citas' NO debe colarse."""
    entrada = {"proveedores": ["read", "write", "export", "editar_cita"]}
    assert auth_router._clamp_permisos_solo_lectura(entrada) == {"proveedores": ["read"]}


def test_clamp_con_permisos_vacios_o_none_no_falla():
    assert auth_router._clamp_permisos_solo_lectura({}) == {}
    assert auth_router._clamp_permisos_solo_lectura(None) == {}


def test_clamp_no_muta_el_diccionario_original():
    original = {"flota": ["read", "write"]}
    resultado = auth_router._clamp_permisos_solo_lectura(original)
    resultado["flota"].append("delete")
    assert original["flota"] == ["read", "write"], "el clamp debe devolver listas nuevas, no alias del original"


def test_coordinador_esta_en_roles_solo_lectura_de_esta_app():
    assert "coordinador" in auth_router.ROLES_SOLO_LECTURA_EN_ESTA_APP


def test_admin_no_esta_en_roles_solo_lectura_de_esta_app():
    assert "admin" not in auth_router.ROLES_SOLO_LECTURA_EN_ESTA_APP


# ── 2b) Integración: el clamp actúa incluso si roles.permisos cambiara ──


def test_login_coordinador_clampa_permisos_ampliados_en_bd(permisos_coordinador_ampliados):
    resp = _login(COORDINADOR_EMAIL)
    assert resp.status_code == 200
    permisos = resp.json()["usuario"]["permisos"]

    assert permisos["flota"] == ["read"], (
        "Aunque roles.permisos.flota tuviera write/delete/export, el login "
        "de un rol solo-lectura-en-esta-app debe devolver únicamente 'read'."
    )
    assert sorted(permisos["citas"]) == ["export", "read"]
    assert permisos["muelles"] == ["read"]


def test_me_coordinador_clampa_permisos_ampliados_en_bd(permisos_coordinador_ampliados):
    login_resp = _login(COORDINADOR_EMAIL)
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/auth/me", headers=_bearer(token))
    assert me_resp.status_code == 200
    permisos = me_resp.json()["permisos"]

    assert permisos["flota"] == ["read"]
    assert sorted(permisos["citas"]) == ["export", "read"]
    assert permisos["muelles"] == ["read"]


def test_coordinador_con_permisos_ampliados_sigue_sin_poder_escribir_flota(
    permisos_coordinador_ampliados, registro_flota
):
    """Cierra el círculo end-to-end: aunque la fila compartida `roles`
    le diera 'write'/'delete' a coordinador en flota, el propio login
    ya se lo recorta, y por lo tanto require_permiso también lo bloquea
    en el endpoint real -- no es solo un detalle del payload de /login."""
    login_resp = _login(COORDINADOR_EMAIL)
    token = login_resp.json()["access_token"]

    resp_post = client.post(
        "/api/flota", json={"fecha": "2026-01-01", "placa": "QA-COORD-AMPLIADO"}, headers=_bearer(token)
    )
    assert resp_post.status_code == 403

    resp_delete = client.delete(f"/api/flota/{registro_flota}", headers=_bearer(token))
    assert resp_delete.status_code == 403


# ── 3) Control: admin no se ve afectado por el clamp ─────────────────


def test_admin_login_conserva_permisos_completos_de_flota(token_admin):
    resp = _login(ADMIN_EMAIL)
    assert resp.status_code == 200
    permisos = resp.json()["usuario"]["permisos"]
    assert set(permisos["flota"]) >= {"read", "write", "delete"}, (
        "El rol 'admin' no está en ROLES_SOLO_LECTURA_EN_ESTA_APP: su "
        "permiso de flota no debe ser recortado."
    )


def test_admin_me_conserva_permisos_completos_de_flota(token_admin):
    resp = client.get("/api/auth/me", headers=_bearer(token_admin))
    assert resp.status_code == 200
    permisos = resp.json()["permisos"]
    assert set(permisos["flota"]) >= {"read", "write", "delete"}


def test_admin_puede_editar_y_eliminar_flota(token_admin, registro_flota):
    """Control funcional (no solo de permisos declarados): admin
    efectivamente puede editar y eliminar un registro de flota, a
    diferencia de coordinador en los tests de la sección 1.

    Nota: el registro se crea aquí por SQL directo (fixture
    `registro_flota`), no vía POST /api/flota -- ver
    `test_crear_flota_falla_por_bug_preexistente_de_columnas_inexistentes`
    más abajo: ese endpoint tiene un bug preexistente, no relacionado con
    el clamp de coordinador, que lo rompe para CUALQUIER rol (incluido
    admin)."""
    headers = _bearer(token_admin)

    resp_editar = client.put(
        f"/api/flota/{registro_flota}", json={"observacion": "editado por admin en test"}, headers=headers
    )
    assert resp_editar.status_code == 200, resp_editar.text

    resp_obtener = client.get(f"/api/flota/{registro_flota}", headers=headers)
    assert resp_obtener.status_code == 200
    assert resp_obtener.json()["observacion"] == "editado por admin en test"

    resp_eliminar = client.delete(f"/api/flota/{registro_flota}", headers=headers)
    assert resp_eliminar.status_code == 200, resp_eliminar.text

    resp_confirmar = client.get(f"/api/flota/{registro_flota}", headers=headers)
    assert resp_confirmar.status_code == 404


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG PREEXISTENTE en backend/routers/flota.py::crear (no relacionado "
        "con el clamp de coordinador de esta tarea): la lista `campos` incluye "
        "'tipo_sello', 'tipo_sello_entrada', 'obs_salida', 'foto_salida', "
        "'obs_llegada', 'foto_llegada', columnas que NO existen en "
        "flota_propia (ver supabase/migrations/20260601101420_schema_base.sql "
        "+ 20260626114921_fecha_salida_llegada.sql -- ningún ALTER TABLE las "
        "agrega). vals = {c: body.get(c) for c in campos} las incluye SIEMPRE "
        "(aunque sea None), así que el INSERT falla con UndefinedColumn "
        "(500) para CUALQUIER rol, incluido admin -- no es un problema de "
        "permisos. Reportado a María/Jorge; este test debe pasar a xfail "
        "resuelto (y perder este marcador) el día que se corrija la lista "
        "`campos` o se agreguen esas columnas al esquema."
    ),
)
def test_crear_flota_falla_por_bug_preexistente_de_columnas_inexistentes(token_admin):
    resp = client.post(
        "/api/flota", json={"fecha": "2026-01-01", "placa": "QA-ADMIN-BUG-COLUMNAS"}, headers=_bearer(token_admin)
    )
    assert resp.status_code == 201, resp.text
