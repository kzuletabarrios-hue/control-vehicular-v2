"""Campos obligatorios de Flota Propia (auditoría de datos faltantes).

POST: conductor obligatorio (texto o codigo_conductor válido).
PUT que CIERRA la salida del CEDI (primera vez que llega hora_salida_cedi):
temperatura numérica en [-30, 30], sello no vacío ni solo ceros, conductor.
PUT que CIERRA la llegada: sello_entrada no vacío ni solo ceros.
Ediciones sueltas (sin cerrar salida/llegada) y registros históricos ya
cerrados NO deben fallar.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app

client = TestClient(app)
ADMIN = "admin@ejemplo.test"


@pytest.fixture()
def headers():
    r = client.post("/api/auth/login", json={"email": ADMIN, "password": "Test1234!"})
    if r.status_code != 200:
        pytest.skip("usuario admin de seed no disponible")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _borrar(rid):
    db = SessionLocal()
    db.execute(text("DELETE FROM audit_log WHERE tabla='flota_propia' AND registro_id=:i"), {"i": rid})
    db.execute(text("DELETE FROM flota_propia WHERE id=:i"), {"i": rid})
    db.commit()
    db.close()


@pytest.fixture()
def mk():
    """Inserta registros por SQL directo (sin pasar por el POST validado)
    para simular datos históricos / lo que dejó bodega."""
    ids = []

    def _mk(**cols):
        rid = str(uuid.uuid4())
        extra_cols = "".join(f", {c}" for c in cols)
        extra_vals = "".join(f", :{c}" for c in cols)
        db = SessionLocal()
        db.execute(
            text(f"INSERT INTO flota_propia (id, fecha, placa{extra_cols}) VALUES (:id, CURRENT_DATE, :placa{extra_vals})"),
            {"id": rid, "placa": "QAOBLIG01", **cols},
        )
        db.commit()
        db.close()
        ids.append(rid)
        return rid

    yield _mk
    for rid in ids:
        _borrar(rid)


def _salida(**extra):
    return {"hora_salida_cedi": "10:00", "fecha_salida": "2026-10-07", **extra}


# ── POST ──
def test_post_sin_conductor_422(headers):
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG02"}, headers=headers)
    assert r.status_code == 422 and "conductor" in r.json()["detail"].lower()


def test_post_conductor_en_blanco_422(headers):
    r = client.post("/api/flota", json={"placa": "QAOBLIG02", "conductor": "   "}, headers=headers)
    assert r.status_code == 422


def test_post_con_conductor_texto_201(headers):
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG02", "conductor": "Juan Perez - CC 123"}, headers=headers)
    assert r.status_code == 201, r.text
    _borrar(r.json()["id"])


def test_post_codigo_conductor_inexistente_422(headers):
    r = client.post("/api/flota", json={"placa": "QAOBLIG02", "codigo_conductor": 99999999}, headers=headers)
    assert r.status_code == 422


def test_post_codigo_conductor_valido_201(headers):
    db = SessionLocal()
    row = db.execute(text("SELECT codigo FROM conductores WHERE codigo IS NOT NULL LIMIT 1")).fetchone()
    db.close()
    if not row:
        pytest.skip("no hay conductores en el seed")
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG02", "codigo_conductor": row.codigo}, headers=headers)
    assert r.status_code == 201, r.text
    _borrar(r.json()["id"])


# ── PUT salida CEDI ──
def test_salida_sin_temperatura_422(headers, mk):
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(), headers=headers)
    assert r.status_code == 422 and "temperatura" in r.json()["detail"].lower()


@pytest.mark.parametrize("t", ["abc", "31", "-30.5", "", "nan"])
def test_salida_temperatura_invalida_422(headers, mk, t):
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura=t), headers=headers)
    assert r.status_code == 422


@pytest.mark.parametrize("t", ["0", "4.5", "-30", "30", "-18,5"])
def test_salida_temperatura_valida_200(headers, mk, t):
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura=t), headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("sello", ["", "   ", "0", "0000", None])
def test_salida_sello_invalido_422(headers, mk, sello):
    rid = mk(conductor="C")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="4", sello=sello), headers=headers)
    assert r.status_code == 422 and "sello" in r.json()["detail"].lower()


def test_salida_usa_sello_y_temperatura_existentes(headers, mk):
    rid = mk(conductor="C", sello="778899", temperatura="3")
    r = client.put(f"/api/flota/{rid}", json=_salida(), headers=headers)
    assert r.status_code == 200, r.text


def test_salida_sin_conductor_422(headers, mk):
    rid = mk(sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="4"), headers=headers)
    assert r.status_code == 422 and "conductor" in r.json()["detail"].lower()


def test_salida_completa_conductor_a_mano_200(headers, mk):
    rid = mk(sello="123456")
    r = client.put(
        f"/api/flota/{rid}", json=_salida(temperatura="4", conductor="Pedro Gomez"), headers=headers
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/flota/{rid}", headers=headers).json()["conductor"] == "Pedro Gomez"


# ── PUT llegada ──
@pytest.mark.parametrize("sello", ["", "000", None])
def test_llegada_sello_entrada_invalido_422(headers, mk, sello):
    rid = mk(conductor="C", hora_salida_cedi="09:00")
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "12:00", "sello_entrada": sello}, headers=headers)
    assert r.status_code == 422 and "sello" in r.json()["detail"].lower()


def test_llegada_sin_sello_entrada_422(headers, mk):
    rid = mk(conductor="C", hora_salida_cedi="09:00")
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "12:00"}, headers=headers)
    assert r.status_code == 422


def test_llegada_con_sello_200(headers, mk):
    rid = mk(conductor="C", hora_salida_cedi="09:00")
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "12:00", "sello_entrada": "654321"}, headers=headers)
    assert r.status_code == 200, r.text


# ── No romper históricos / ediciones sueltas ──
def test_edicion_suelta_en_registro_sin_datos_no_falla(headers, mk):
    rid = mk()
    r = client.put(f"/api/flota/{rid}", json={"observacion": "corrección"}, headers=headers)
    assert r.status_code == 200, r.text


def test_reenviar_registro_historico_cerrado_no_falla(headers, mk):
    """El formulario de edición reenvía hora_salida_cedi/hora_llegada ya
    guardadas: no es un cierre nuevo, no debe exigir campos."""
    rid = mk(hora_salida_cedi="08:00", hora_llegada="11:00")
    r = client.put(
        f"/api/flota/{rid}",
        json={"hora_salida_cedi": "08:00", "hora_llegada": "11:00", "observacion": "x"},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_duplicar_registro_sin_conductor_sigue_funcionando(headers, mk):
    rid = mk()
    r = client.post(f"/api/flota/{rid}/duplicar", headers=headers)
    assert r.status_code == 201, r.text
    _borrar(r.json()["id"])
