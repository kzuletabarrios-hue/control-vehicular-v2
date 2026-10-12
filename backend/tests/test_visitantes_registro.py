"""Caracterización y regla nueva de /api/visitantes (2026-10-12).

Decisión de la usuaria: al CREAR un visitante son obligatorios nombre, cédula
(o pasaporte: alfanumérico, >= 5 caracteres, sin espacios), empresa a la que
pertenece ("Particular" si ninguna), a quién visita (columna `empresa`),
actividad a desarrollar y quién autoriza. `observaciones` es opcional.

Cuerpos reales del frontend (frontend/js/pages/VisitantesPage.js):
  - Alta (handleSave): form sin vacíos + fecha/hora_ingreso de /api/tiempo.
  - Salida ("Confirmar salida"): {hora_salida, fecha_salida[, observaciones, foto_url]}.
    No manda ningún obligatorio: debe funcionar también en históricos incompletos.
  - Edición: el form completo sin los campos vacíos.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app

client = TestClient(app)
PASSWORD = "Test1234!"
BOG = timezone(timedelta(hours=-5))
OBLIGATORIOS = ["nombre", "cedula", "empresa_pertenece", "empresa",
                "actividad_a_desarrollar", "dependencia_autoriza"]


@pytest.fixture(scope="module", autouse=True)
def _columna_fecha_salida():
    """DRIFT: el router y el botón Salida usan visitantes.fecha_salida, pero
    ninguna migración de supabase/migrations la crea para esta tabla (en
    producción existe). Se agrega SOLO en la BD de pruebas."""
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE visitantes ADD COLUMN IF NOT EXISTS fecha_salida DATE"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="module")
def guarda():
    r = client.post("/api/auth/login", json={"email": "guarda.peatonal@ejemplo.test", "password": PASSWORD})
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(autouse=True)
def _limpiar():
    def borrar():
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM visitantes WHERE nombre LIKE 'QA-VIS %'"))
            db.commit()
        finally:
            db.close()
    borrar()
    yield
    borrar()


def _ahora():
    n = datetime.now(BOG)
    return n.strftime("%Y-%m-%d"), n.strftime("%H:%M")


def _body(**extra):
    fecha, hora = _ahora()
    b = {"fecha": fecha, "hora_ingreso": hora, "nombre": f"QA-VIS {uuid.uuid4().hex[:6]}",
         "cedula": "1234567890", "empresa_pertenece": "Particular", "empresa": "Recursos Humanos",
         "actividad_a_desarrollar": "Entrevista", "dependencia_autoriza": "Gerencia"}
    b.update(extra)
    return b


def _fila(rid):
    db = SessionLocal()
    try:
        r = db.execute(text("SELECT * FROM visitantes WHERE id = :i"), {"i": rid}).fetchone()
        return dict(r._mapping) if r else None
    finally:
        db.close()


def _historico(**campos):
    """Inserta directo un registro histórico (incompleto) que el alta ya no permite."""
    rid = str(uuid.uuid4())
    vals = {"id": rid, "nombre": f"QA-VIS {uuid.uuid4().hex[:6]}", "fecha": _ahora()[0],
            "hora_ingreso": "08:00"}
    vals.update(campos)
    cols = ", ".join(vals)
    ph = ", ".join(f":{k}" for k in vals)
    db = SessionLocal()
    try:
        db.execute(text(f"INSERT INTO visitantes ({cols}) VALUES ({ph})"), vals)
        db.commit()
    finally:
        db.close()
    return rid


# ── A) Caracterización ─────────────────────────────────────────────

def test_alta_completa(guarda):
    b = _body(observaciones="Trae portátil")
    r = client.post("/api/visitantes", json=b, headers=guarda)
    assert r.status_code == 201, r.text
    f = _fila(r.json()["id"])
    assert f["nombre"] == b["nombre"] and f["cedula"] == "1234567890"
    assert f["empresa"] == "Recursos Humanos" and f["empresa_pertenece"] == "Particular"
    assert f["actividad_a_desarrollar"] == "Entrevista" and f["dependencia_autoriza"] == "Gerencia"
    assert f["observaciones"] == "Trae portátil" and f["hora_salida"] is None


def test_observaciones_opcional(guarda):
    r = client.post("/api/visitantes", json=_body(), headers=guarda)
    assert r.status_code == 201, r.text
    assert _fila(r.json()["id"])["observaciones"] is None


def test_salida_con_body_real(guarda):
    rid = client.post("/api/visitantes", json=_body(), headers=guarda).json()["id"]
    fecha, hora = _ahora()
    r = client.put(f"/api/visitantes/{rid}", json={"hora_salida": hora, "fecha_salida": fecha,
                                                   "observaciones": "Salió bien"}, headers=guarda)
    assert r.status_code == 200, r.text
    f = _fila(rid)
    assert f["hora_salida"] is not None and str(f["fecha_salida"]) == fecha
    assert f["observaciones"] == "Salió bien"


def test_salida_de_historico_incompleto(guarda):
    rid = _historico()  # solo nombre: sin cédula, empresa, actividad ni autoriza
    fecha, hora = _ahora()
    r = client.put(f"/api/visitantes/{rid}", json={"hora_salida": hora, "fecha_salida": fecha}, headers=guarda)
    assert r.status_code == 200, r.text
    assert _fila(rid)["hora_salida"] is not None


def test_editar_otro_campo_en_historico_con_cedula_corta(guarda):
    rid = _historico(cedula="123")
    r = client.put(f"/api/visitantes/{rid}", json={"cedula": "123", "observaciones": "nota"}, headers=guarda)
    assert r.status_code == 200, r.text
    assert _fila(rid)["observaciones"] == "nota"


# ── B) Regla nueva ─────────────────────────────────────────────────

@pytest.mark.parametrize("campo", OBLIGATORIOS)
@pytest.mark.parametrize("modo", ["ausente", "vacio", "espacios"])
def test_alta_sin_obligatorio_400(guarda, campo, modo):
    b = _body()
    if modo == "ausente":
        del b[campo]
    else:
        b[campo] = "" if modo == "vacio" else "   "
    r = client.post("/api/visitantes", json=b, headers=guarda)
    assert r.status_code == 400, r.text
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]


@pytest.mark.parametrize("cedula", ["1234", "12-3", "   ", "123 456", "12345.6", "ab#cde", 123456, None])
def test_cedula_invalida_400(guarda, cedula):
    r = client.post("/api/visitantes", json=_body(cedula=cedula), headers=guarda)
    assert r.status_code == 400, r.text
    assert "cédula" in r.json()["detail"].lower()


@pytest.mark.parametrize("cedula,esperada", [("AB123456", "AB123456"), ("  98765432  ", "98765432"),
                                              ("12-3456", "12-3456")])
def test_cedula_pasaporte_aceptada(guarda, cedula, esperada):
    r = client.post("/api/visitantes", json=_body(cedula=cedula), headers=guarda)
    assert r.status_code == 201, r.text
    assert _fila(r.json()["id"])["cedula"] == esperada


def test_sello_fecha_y_hora_bogota(guarda):
    b = _body()
    del b["fecha"], b["hora_ingreso"]
    antes = datetime.now(BOG)
    r = client.post("/api/visitantes", json=b, headers=guarda)
    assert r.status_code == 201, r.text
    f = _fila(r.json()["id"])
    assert str(f["fecha"]) in (antes.strftime("%Y-%m-%d"), datetime.now(BOG).strftime("%Y-%m-%d"))
    assert re.fullmatch(r"\d\d:\d\d:\d\d", str(f["hora_ingreso"]))
    delta = abs(datetime.combine(antes.date(), f["hora_ingreso"]) - antes.replace(tzinfo=None))
    assert delta < timedelta(minutes=2)


@pytest.mark.parametrize("campo,valor", [("fecha", "12/10/2026"), ("fecha", "2026-13-40"),
                                          ("hora_ingreso", "25:99"), ("hora_ingreso", "8am"),
                                          ("hora_salida", "99:00"), ("fecha_salida", "ayer")])
def test_fecha_hora_mal_formada_400(guarda, campo, valor):
    r = client.post("/api/visitantes", json=_body(**{campo: valor}), headers=guarda)
    assert r.status_code == 400, r.text


@pytest.mark.parametrize("campo", OBLIGATORIOS)
@pytest.mark.parametrize("valor", ["", "   ", None])
def test_put_no_puede_vaciar_obligatorio(guarda, campo, valor):
    rid = client.post("/api/visitantes", json=_body(), headers=guarda).json()["id"]
    antes = _fila(rid)[campo]
    r = client.put(f"/api/visitantes/{rid}", json={campo: valor}, headers=guarda)
    assert r.status_code == 400, r.text
    assert _fila(rid)[campo] == antes


def test_put_cedula_nueva_invalida_400_y_valida_ok(guarda):
    rid = client.post("/api/visitantes", json=_body(), headers=guarda).json()["id"]
    assert client.put(f"/api/visitantes/{rid}", json={"cedula": "12"}, headers=guarda).status_code == 400
    r = client.put(f"/api/visitantes/{rid}", json={"cedula": " PA-98765 "}, headers=guarda)
    assert r.status_code == 200, r.text
    assert _fila(rid)["cedula"] == "PA-98765"


def test_put_fecha_hora_mal_formada_400(guarda):
    rid = client.post("/api/visitantes", json=_body(), headers=guarda).json()["id"]
    assert client.put(f"/api/visitantes/{rid}", json={"hora_salida": "99:99"}, headers=guarda).status_code == 400
    assert client.put(f"/api/visitantes/{rid}", json={"fecha": ""}, headers=guarda).status_code == 400


def test_put_registro_inexistente_404(guarda):
    r = client.put(f"/api/visitantes/{uuid.uuid4()}", json={"observaciones": "x"}, headers=guarda)
    assert r.status_code == 404
