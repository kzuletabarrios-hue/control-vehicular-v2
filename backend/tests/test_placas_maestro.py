"""Tests de la validación de placas de flota propia (2026-10-03).

Contexto: el campo placa era texto libre y se acumularon placas mal
digitadas. Ahora:
  - El backend normaliza la placa al guardar (mayúsculas, sin espacios ni
    guiones) -- utils_placas.normalizar_placa.
  - Una placa fuera del maestro `vehiculos` se guarda igual (decisión de la
    usuaria: nunca bloquear la portería) y las lecturas la exponen con
    placa_no_verificada = true.
  - GET /api/flota/vehiculos da a quien tiene flota:read la lista de placas
    activas para el selector del formulario.
  - Admin administra el maestro desde /api/maestros/vehiculos.

Corre contra el Postgres LOCAL de pruebas (ver backend/conftest.py).
Cada test limpia lo que crea.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from utils_placas import normalizar_placa

client = TestClient(app)
PASSWORD = "Test1234!"


def _token(email):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin():
    return _token("admin@ejemplo.test")


@pytest.fixture()
def guarda():
    return _token("guarda.vehicular@ejemplo.test")


@pytest.fixture()
def placa_maestro():
    """Vehículo activo temporal en el maestro."""
    placa = "QA" + uuid.uuid4().hex[:4].upper()
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO vehiculos (placa, tipo, activo) VALUES (:p, 'SENCILLO', TRUE)"), {"p": placa})
        db.commit()
        yield placa
    finally:
        db.execute(text("DELETE FROM flota_propia WHERE placa = :p"), {"p": placa})
        db.execute(text("DELETE FROM vehiculos WHERE placa = :p"), {"p": placa})
        db.commit()
        db.close()


def _borrar_flota(fid):
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM audit_log WHERE registro_id = :i"), {"i": fid})
        db.execute(text("DELETE FROM flota_propia WHERE id = :i"), {"i": fid})
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("raw,esperado", [
    ("abc-123", "ABC123"),
    ("  ABC 123 ", "ABC123"),
    ("Kol330", "KOL330"),
    ("", None),
    ("   ", None),
    (None, None),
])
def test_normalizar_placa(raw, esperado):
    assert normalizar_placa(raw) == esperado


def test_guarda_puede_listar_placas_del_maestro(guarda, placa_maestro):
    r = client.get("/api/flota/vehiculos", headers=guarda)
    assert r.status_code == 200, r.text
    placas = [v["placa"] for v in r.json()]
    assert placa_maestro in placas


def test_crear_normaliza_y_marca_placa_del_maestro_como_verificada(admin, placa_maestro):
    escrita = placa_maestro[:2].lower() + " - " + placa_maestro[2:]
    r = client.post("/api/flota", headers=admin, json={"placa": escrita, "fecha": "2026-10-03"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    try:
        d = client.get(f"/api/flota/{fid}", headers=admin).json()
        assert d["placa"] == placa_maestro
        assert d["placa_no_verificada"] is False
    finally:
        _borrar_flota(fid)


def test_placa_fuera_del_maestro_se_guarda_y_queda_no_verificada(admin):
    placa = "ZZ" + uuid.uuid4().hex[:4].upper()
    r = client.post("/api/flota", headers=admin, json={"placa": placa.lower(), "fecha": "2026-10-03"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    try:
        d = client.get(f"/api/flota/{fid}", headers=admin).json()
        assert d["placa"] == placa
        assert d["placa_no_verificada"] is True
    finally:
        _borrar_flota(fid)


def test_actualizar_normaliza_placa(admin, placa_maestro):
    r = client.post("/api/flota", headers=admin, json={"placa": "TEMP1", "fecha": "2026-10-03"})
    fid = r.json()["id"]
    try:
        u = client.put(f"/api/flota/{fid}", headers=admin, json={"placa": " " + placa_maestro.lower() + " "})
        assert u.status_code == 200, u.text
        d = client.get(f"/api/flota/{fid}", headers=admin).json()
        assert d["placa"] == placa_maestro
        assert d["placa_no_verificada"] is False
    finally:
        _borrar_flota(fid)


def test_admin_alta_edicion_y_duplicado_de_vehiculo(admin):
    placa = "QB" + uuid.uuid4().hex[:4].upper()
    try:
        r = client.post("/api/maestros/vehiculos", headers=admin, json={"placa": placa.lower()[:2] + "-" + placa[2:]})
        assert r.status_code == 201, r.text
        vid = r.json()["id"]
        lista = client.get("/api/maestros/vehiculos?activo=true", headers=admin).json()
        assert any(v["placa"] == placa and v["tipo"] is None for v in lista)

        dup = client.post("/api/maestros/vehiculos", headers=admin, json={"placa": placa})
        assert dup.status_code == 409

        u = client.put(f"/api/maestros/vehiculos/{vid}", headers=admin, json={"tipo": "BITREN"})
        assert u.status_code == 200, u.text

        d = client.delete(f"/api/maestros/vehiculos/{vid}", headers=admin)
        assert d.status_code == 200
        lista = client.get("/api/maestros/vehiculos?activo=true", headers=admin).json()
        assert all(v["placa"] != placa for v in lista)
    finally:
        db = SessionLocal()
        db.execute(text("DELETE FROM vehiculos WHERE placa = :p"), {"p": placa})
        db.commit(); db.close()


def test_guarda_no_puede_dar_de_alta_vehiculos(guarda):
    r = client.post("/api/maestros/vehiculos", headers=guarda, json={"placa": "QC0001"})
    assert r.status_code == 403
