"""Caracterización y regla nueva de /api/control-acceso (2026-10-11).

Contexto: hoy `crear` (POST) y `actualizar` (PUT /{id}) BORRAN la cédula si no
está en `bd_control_acceso` y guardan el ingreso sin cédula. Decisión de la
usuaria: la persona se registra igual y su cédula se guarda aunque no esté en
el maestro. Además el servidor debe exigir cédula y nombre al CREAR (no al dar
la salida) y sellar fecha/hora de ingreso (Bogotá) si el cliente no las manda.

Dos grupos:
  A) Caracterización: pasan HOY y deben seguir pasando tras el cambio.
  B) Regla nueva: marcadas xfail(strict=True) "pendiente fix cedula
     control_acceso". Cuando María corrija el router, XPASS estricto hará
     fallar la suite y obligará a quitar el marcador (es lo deseado).

Cuerpos reales del frontend (frontend/js/pages/AccesoPage.js):
  - Alta (handleSave): form sin vacíos + fecha/hora_ingreso de /api/tiempo;
    cedula como int. {fecha, cedula, nombre, contratista, hora_ingreso[, observaciones]}
  - Salida (botón "Confirmar salida"): {hora_salida:"HH:MM", fecha_salida:"YYYY-MM-DD"
    [, observaciones, foto_url]}. No manda cédula ni nombre.
  - Edición: mismo cuerpo del alta pero con todos los campos del registro.
  - La cola offline (App.js) reenvía tal cual lo que le pasen por addOffline;
    AccesoPage no la usa para el alta, así que no hay reenvíos de altas viejas.

FK cedula -> bd_control_acceso: los tests de "cédula fuera del maestro" la
quitan SOLO en la BD local de pruebas (DROP CONSTRAINT IF EXISTS
control_acceso_cedula_fkey) y la restauran al terminar. En producción lo
cubrirá la migración de Jorge; estos tests no la reemplazan.

Corre contra el Postgres LOCAL de pruebas (ver backend/conftest.py).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app

client = TestClient(app)
PASSWORD = "Test1234!"
CED_MAESTRO = 970000001          # presente en el maestro durante el test
CED_FUERA = 970000999            # NUNCA en el maestro
NOMBRE_MAESTRO = "QA Maestro Acceso"
FK = "control_acceso_cedula_fkey"
BOG = timezone(timedelta(hours=-5))


@pytest.fixture(scope="module", autouse=True)
def _columna_fecha_salida():
    """DRIFT detectado: el router (POST/PUT) y el botón Salida usan
    control_acceso.fecha_salida, pero NINGUNA migración de supabase/migrations
    la crea para esa tabla (sí para flota_propia, proveedores, etc.). En
    producción existe (se creó a mano); en la BD local migrada no, y el alta y
    la salida dan 500. Aquí se agrega SOLO en la BD de pruebas para poder
    caracterizar; Jorge debe crear la migración idempotente
    ALTER TABLE control_acceso ADD COLUMN IF NOT EXISTS fecha_salida DATE."""
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE control_acceso ADD COLUMN IF NOT EXISTS fecha_salida DATE"))
        db.commit()
    finally:
        db.close()
    yield


def _token(email):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def guarda():
    # guarda_peatonal opera el control de acceso de personas (permiso write).
    return _token("guarda.peatonal@ejemplo.test")


def _limpiar():
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM control_acceso WHERE nombre LIKE 'QA-CA %' "
                        "OR nombre = :n OR cedula IN (:a, :b)"),
                   {"n": NOMBRE_MAESTRO, "a": CED_MAESTRO, "b": CED_FUERA})
        db.execute(text("DELETE FROM bd_control_acceso WHERE cedula IN (:a, :b)"),
                   {"a": CED_MAESTRO, "b": CED_FUERA})
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def maestro():
    """Persona del maestro bd_control_acceso (cédula CED_MAESTRO)."""
    _limpiar()
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO bd_control_acceso (cedula, nombre, contratista, estado) "
                        "VALUES (:c, :n, 'QA Contratista', 'ACTIVO')"),
                   {"c": CED_MAESTRO, "n": NOMBRE_MAESTRO})
        db.commit()
    finally:
        db.close()
    yield CED_MAESTRO
    _limpiar()


@pytest.fixture()
def sin_fk():
    """Quita la FK cedula->maestro SOLO en la BD local de pruebas y la
    restaura al final. Lo cubrirá la migración de Jorge en producción."""
    _limpiar()
    db = SessionLocal()
    existia = db.execute(text("SELECT 1 FROM pg_constraint WHERE conname = :n"), {"n": FK}).fetchone()
    db.execute(text(f"ALTER TABLE control_acceso DROP CONSTRAINT IF EXISTS {FK}"))
    db.commit()
    db.close()
    yield
    _limpiar()
    if existia:
        db = SessionLocal()
        try:
            db.execute(text(f"ALTER TABLE control_acceso ADD CONSTRAINT {FK} FOREIGN KEY (cedula) "
                            "REFERENCES bd_control_acceso(cedula) ON DELETE SET NULL"))
            db.commit()
        finally:
            db.close()


def _ahora_bog():
    n = datetime.now(BOG)
    return n.strftime("%Y-%m-%d"), n.strftime("%H:%M")


def _alta_body(cedula, nombre=None, **extra):
    """Cuerpo idéntico al de handleSave del frontend (alta)."""
    fecha, hora = _ahora_bog()
    body = {"fecha": fecha, "hora_ingreso": hora, "contratista": "QA Contratista",
            "nombre": nombre or f"QA-CA {uuid.uuid4().hex[:6]}"}
    if cedula is not None:
        body["cedula"] = cedula
    body.update(extra)
    return body


def _fila(rid):
    db = SessionLocal()
    try:
        r = db.execute(text("SELECT * FROM control_acceso WHERE id = :i"), {"i": rid}).fetchone()
        return dict(r._mapping) if r else None
    finally:
        db.close()


def _insertar_historico(cedula=None, nombre="QA-CA historico", fecha="2026-01-15", hora="08:30"):
    rid = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO control_acceso (id, fecha, cedula, nombre, contratista, hora_ingreso) "
                        "VALUES (:i, :f, :c, :n, 'QA Contratista', :h)"),
                   {"i": rid, "f": fecha, "c": cedula, "n": nombre, "h": hora})
        db.commit()
    finally:
        db.close()
    return rid


# ═════════════ A) CARACTERIZACIÓN: pasan hoy y después del cambio ═════════════

def test_alta_con_cedula_del_maestro_guarda_cedula(guarda, maestro):
    r = client.post("/api/control-acceso", json=_alta_body(maestro, NOMBRE_MAESTRO), headers=guarda)
    assert r.status_code == 201, r.text
    fila = _fila(r.json()["id"])
    assert fila["cedula"] == CED_MAESTRO
    assert fila["nombre"] == NOMBRE_MAESTRO
    assert fila["hora_salida"] is None
    assert fila["anulado"] is False


def test_boton_salida_con_cuerpo_real_del_frontend(guarda, maestro):
    rid = client.post("/api/control-acceso", json=_alta_body(maestro, NOMBRE_MAESTRO),
                      headers=guarda).json()["id"]
    fecha, hora = _ahora_bog()
    # Cuerpo exacto del botón "Confirmar salida": solo hora/fecha de salida.
    r = client.put(f"/api/control-acceso/{rid}",
                   json={"hora_salida": hora, "fecha_salida": fecha}, headers=guarda)
    assert r.status_code == 200, r.text
    fila = _fila(rid)
    assert fila["hora_salida"] is not None
    assert fila["cedula"] == CED_MAESTRO          # la salida no toca la cédula
    assert fila["nombre"] == NOMBRE_MAESTRO


def test_listado_por_defecto_excluye_anulados(guarda, maestro):
    ok = client.post("/api/control-acceso", json=_alta_body(maestro, "QA-CA activo"), headers=guarda).json()["id"]
    anulado = client.post("/api/control-acceso", json=_alta_body(maestro, "QA-CA anulado"), headers=guarda).json()["id"]
    r = client.put(f"/api/control-acceso/{anulado}/anular", json={"motivo": "prueba QA"},
                   headers=_token("admin@ejemplo.test"))
    assert r.status_code == 200, r.text

    ids = {i["id"] for i in client.get("/api/control-acceso?limit=500", headers=guarda).json()["items"]}
    assert ok in ids and anulado not in ids
    ids_all = {i["id"] for i in client.get("/api/control-acceso?limit=500&incluir_anulados=true",
                                           headers=guarda).json()["items"]}
    assert ok in ids_all and anulado in ids_all


def test_listado_trae_estado_bd_para_cedula_del_maestro(guarda, maestro):
    rid = client.post("/api/control-acceso", json=_alta_body(maestro, NOMBRE_MAESTRO), headers=guarda).json()["id"]
    items = client.get("/api/control-acceso?limit=500", headers=guarda).json()["items"]
    fila = next(i for i in items if i["id"] == rid)
    assert fila["estado_bd"] == "ACTIVO"


# ═════════════ B) REGLA NUEVA (xfail hasta el fix de María) ═════════════

def test_alta_con_cedula_fuera_del_maestro_guarda_la_cedula(guarda, sin_fk):
    r = client.post("/api/control-acceso", json=_alta_body(CED_FUERA), headers=guarda)
    assert r.status_code == 201, r.text
    assert _fila(r.json()["id"])["cedula"] == CED_FUERA
    # Y el listado la devuelve (estado_bd nulo: no está en el maestro).
    items = client.get("/api/control-acceso?limit=500", headers=guarda).json()["items"]
    fila = next(i for i in items if i["id"] == r.json()["id"])
    assert fila["cedula"] == CED_FUERA and fila["estado_bd"] is None


def test_alta_sin_cedula_es_400(guarda, sin_fk):
    r = client.post("/api/control-acceso", json=_alta_body(None), headers=guarda)
    assert r.status_code == 400, r.text


def test_alta_sin_nombre_es_400(guarda, sin_fk):
    body = _alta_body(CED_FUERA)
    del body["nombre"]
    r = client.post("/api/control-acceso", json=body, headers=guarda)
    assert r.status_code == 400, r.text


# Hoy PASA (la salida no valida cédula). Se deja SIN xfail como guarda de
# regresión: el fix de "exigir cédula/nombre al crear" no debe romperla.
def test_salida_a_registro_historico_sin_cedula_sigue_funcionando(guarda, sin_fk):
    """Registros viejos quedaron con cédula NULL: la salida (solo manda
    hora/fecha de salida) no debe exigir cédula ni nombre."""
    rid = _insertar_historico(cedula=None)
    fecha, hora = _ahora_bog()
    r = client.put(f"/api/control-acceso/{rid}",
                   json={"hora_salida": hora, "fecha_salida": fecha}, headers=guarda)
    assert r.status_code == 200, r.text
    fila = _fila(rid)
    assert fila["hora_salida"] is not None and fila["cedula"] is None


def test_put_que_cambia_cedula_a_una_fuera_del_maestro_la_guarda(guarda, sin_fk):
    rid = _insertar_historico(cedula=None)
    r = client.put(f"/api/control-acceso/{rid}", json={"cedula": CED_FUERA}, headers=guarda)
    assert r.status_code == 200, r.text
    assert _fila(rid)["cedula"] == CED_FUERA


def test_alta_sin_fecha_ni_hora_se_sella_con_hora_del_servidor_bogota(guarda, sin_fk):
    antes = datetime.now(BOG)
    body = {"cedula": CED_FUERA, "nombre": "QA-CA sin reloj", "contratista": "QA Contratista"}
    r = client.post("/api/control-acceso", json=body, headers=guarda)
    despues = datetime.now(BOG)
    assert r.status_code == 201, r.text
    fila = _fila(r.json()["id"])
    assert fila["fecha"] in (antes.date(), despues.date())
    assert fila["hora_ingreso"] is not None
    ingreso = datetime.combine(fila["fecha"], fila["hora_ingreso"], tzinfo=BOG)
    assert antes - timedelta(minutes=1) <= ingreso <= despues + timedelta(minutes=1)


# ═════════════ C) VALIDACIÓN DE CÉDULA / NOMBRE / CONTRATISTA / FORMATOS ═════════════

@pytest.mark.parametrize("cedula", ["0", 0, "", "   ", "abc", "12a45", "-5", -5, "1.5",
                                    99999999999999999999, "9223372036854775808", True])
def test_alta_con_cedula_invalida_es_400(guarda, sin_fk, cedula):
    r = client.post("/api/control-acceso", json=_alta_body(cedula), headers=guarda)
    assert r.status_code == 400, r.text
    assert "cédula" in r.json()["detail"].lower()


def test_alta_acepta_cedula_como_string_numerico(guarda, sin_fk):
    r = client.post("/api/control-acceso", json=_alta_body(f" {CED_FUERA} "), headers=guarda)
    assert r.status_code == 201, r.text
    assert _fila(r.json()["id"])["cedula"] == CED_FUERA


@pytest.mark.parametrize("nombre", ["", "   "])
def test_alta_con_nombre_vacio_es_400(guarda, sin_fk, nombre):
    body = _alta_body(CED_FUERA)
    body["nombre"] = nombre
    assert client.post("/api/control-acceso", json=body, headers=guarda).status_code == 400


@pytest.mark.parametrize("contratista", [None, "", "  "])
def test_alta_sin_contratista_es_400(guarda, sin_fk, contratista):
    body = _alta_body(CED_FUERA)
    if contratista is None:
        del body["contratista"]
    else:
        body["contratista"] = contratista
    assert client.post("/api/control-acceso", json=body, headers=guarda).status_code == 400


@pytest.mark.parametrize("campo,valor", [("hora_ingreso", "25:99"), ("hora_ingreso", "abc"),
                                         ("fecha", "2026-13-45"), ("fecha", "ayer"),
                                         ("hora_salida", "8"), ("fecha_salida", "2026/01/01")])
def test_alta_con_fecha_u_hora_mal_formada_es_400(guarda, sin_fk, campo, valor):
    r = client.post("/api/control-acceso", json=_alta_body(CED_FUERA, **{campo: valor}), headers=guarda)
    assert r.status_code == 400, r.text


@pytest.mark.parametrize("cuerpo", [{"cedula": ""}, {"cedula": "  "}, {"cedula": 0}, {"cedula": "0"},
                                    {"cedula": "abc"}, {"cedula": None}, {"nombre": ""}, {"nombre": "  "},
                                    {"nombre": None}, {"hora_salida": "99:99"}, {"fecha_salida": "x"}])
def test_put_que_vacia_o_invalida_cedula_nombre_es_400(guarda, sin_fk, cuerpo):
    rid = client.post("/api/control-acceso", json=_alta_body(CED_FUERA, "QA-CA original"),
                      headers=guarda).json()["id"]
    r = client.put(f"/api/control-acceso/{rid}", json=cuerpo, headers=guarda)
    assert r.status_code == 400, r.text
    fila = _fila(rid)
    assert fila["cedula"] == CED_FUERA and fila["nombre"] == "QA-CA original"


def test_put_edicion_completa_como_el_formulario_sigue_funcionando(guarda, sin_fk):
    """El formulario de edición reenvía el registro entero (horas con segundos)."""
    rid = client.post("/api/control-acceso", json=_alta_body(CED_FUERA, "QA-CA edit"), headers=guarda).json()["id"]
    f = _fila(rid)
    body = {"fecha": str(f["fecha"]), "cedula": str(CED_FUERA), "nombre": "QA-CA edit",
            "contratista": "QA Contratista", "hora_ingreso": str(f["hora_ingreso"]),
            "observaciones": "nota"}
    r = client.put(f"/api/control-acceso/{rid}", json=body, headers=guarda)
    assert r.status_code == 200, r.text
    assert _fila(rid)["observaciones"] == "nota"
