"""Muelle OBLIGATORIO al confirmar el ingreso de proveedores (2026-10-16).

Contrato verificado contra backend/routers/proveedores.py:
  - PUT /api/proveedores/{id}/confirmar: 409 (ya confirmado / pendiente) gana
    sobre 422; 422 si falta o viene vacio el muelle; 422 si no es un entero
    1-19 ("07" -> "7"); un solo UPDATE; audit_log.datos_despues trae muelle.
  - PUT /api/proveedores/{id} (actualizar): con registro confirmado, sin
    hora_salida y sin hora_muelle_liberado NO se puede vaciar ni invalidar
    muelle_descargue (salvo que el valor no cambie). Liberado / con salida /
    otro estado / payload sin el campo: no se valida.
Inserta filas por SQL directo (fecha 2031, placas QA-MUE-*) y limpia en teardown.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from routers.proveedores import _normalizar_muelle_descargue

client = TestClient(app)
PASSWORD = "Test1234!"
FECHA = "2031-03-03"
PLACA = "QA-MUE-01"


@pytest.fixture(scope="module")
def hdr():
    r = client.post("/api/auth/login", json={"email": "admin@ejemplo.test", "password": PASSWORD})
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _borrar():
    db = SessionLocal()
    try:
        ids = [str(r[0]) for r in db.execute(
            text("SELECT id FROM proveedores WHERE placa_vehiculo LIKE 'QA-MUE-%'")).fetchall()]
        for i in ids:
            db.execute(text("DELETE FROM audit_log WHERE tabla = 'proveedores' AND registro_id = :i"), {"i": i})
            db.execute(text("DELETE FROM proveedores_ordenes WHERE proveedor_id = :i"), {"i": i})
        db.execute(text("DELETE FROM proveedores WHERE placa_vehiculo LIKE 'QA-MUE-%'"))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _limpiar():
    _borrar()
    yield
    _borrar()


def _crear(estado="ingresado_wps", muelle=None, hora_salida=None, liberado=False):
    pid = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO proveedores (id, fecha, placa_vehiculo, estado_confirmacion, hora_ingreso,
                                     muelle_descargue, hora_salida, hora_muelle_liberado)
            VALUES (:id, :f, :p, :e, '08:00:00', :m, :hs, :hl)
        """), {"id": pid, "f": FECHA, "p": PLACA, "e": estado, "m": muelle, "hs": hora_salida,
               "hl": "09:00:00" if liberado else None})
        db.commit()
    finally:
        db.close()
    return pid


def _fila(pid):
    db = SessionLocal()
    try:
        return db.execute(text("SELECT * FROM proveedores WHERE id = :i"), {"i": pid}).fetchone()
    finally:
        db.close()


def _confirmar(hdr, pid, body=None):
    if body is None:
        return client.put(f"/api/proveedores/{pid}/confirmar", headers=hdr)
    return client.put(f"/api/proveedores/{pid}/confirmar", headers=hdr, json=body)


# -- Helper puro ---------------------------------------------------------
@pytest.mark.parametrize("entrada,esperado", [
    (1, "1"), (19, "19"), ("1", "1"), ("19", "19"), ("07", "7"), (" 7 ", "7"), ("007", "7"), (7, "7"),
    (0, None), (20, None), (-1, None), ("0", None), ("20", None), ("abc", None), ("7 y 8", None),
    ("", None), ("  ", None), (None, None), (True, None), (False, None), (7.0, None), (7.5, None),
    ("7.0", None), ("-3", None), ("١٢", None), ([7], None), ({"a": 1}, None),
])
def test_helper_normalizar(entrada, esperado):
    assert _normalizar_muelle_descargue(entrada) == esperado


# -- /confirmar ----------------------------------------------------------
@pytest.mark.parametrize("enviado,guardado", [
    (1, "1"), (19, "19"), ("1", "1"), ("19", "19"), ("07", "7"), (" 12 ", "12"),
])
def test_confirmar_con_muelle_valido(hdr, enviado, guardado):
    pid = _crear()
    r = _confirmar(hdr, pid, {"muelle_descargue": enviado})
    assert r.status_code == 200, r.text
    f = _fila(pid)
    assert f.estado_confirmacion == "confirmado"
    assert f.muelle_descargue == guardado
    assert f.hora_ingreso_confirmado is not None


@pytest.mark.parametrize("body", [None, {}, {"muelle_descargue": None}, {"muelle_descargue": ""},
                                  {"muelle_descargue": "   "}])
def test_confirmar_sin_muelle_422_y_no_cambia_estado(hdr, body):
    pid = _crear()
    r = _confirmar(hdr, pid, body)
    assert r.status_code == 422, r.text
    assert "obligatorio" in r.json()["detail"]
    f = _fila(pid)
    assert f.estado_confirmacion == "ingresado_wps"
    assert f.muelle_descargue is None and f.hora_ingreso_confirmado is None


@pytest.mark.parametrize("malo", [0, 20, "0", "20", "abc", "7 y 8", -1, True, 7.5, "7.0", [7]])
def test_confirmar_muelle_invalido_422(hdr, malo):
    pid = _crear()
    r = _confirmar(hdr, pid, {"muelle_descargue": malo})
    assert r.status_code == 422, r.text
    assert "inválido" in r.json()["detail"]
    assert _fila(pid).estado_confirmacion == "ingresado_wps"


def test_confirmar_pendiente_sin_muelle_es_409_no_422(hdr):
    pid = _crear(estado="pendiente")
    for body in (None, {}, {"muelle_descargue": "abc"}):
        assert _confirmar(hdr, pid, body).status_code == 409
    assert _fila(pid).estado_confirmacion == "pendiente"


def test_confirmar_ya_confirmado_es_409_incluso_sin_muelle(hdr):
    pid = _crear(estado="confirmado", muelle="5")
    assert _confirmar(hdr, pid, {"muelle_descargue": 6}).status_code == 409
    assert _confirmar(hdr, pid).status_code == 409
    assert _confirmar(hdr, pid, {"muelle_descargue": "abc"}).status_code == 409
    assert _fila(pid).muelle_descargue == "5"


def test_confirmar_inexistente_404(hdr):
    assert _confirmar(hdr, str(uuid.uuid4()), {"muelle_descargue": 3}).status_code == 404


def test_confirmar_sin_token_401_o_403():
    pid = _crear()
    r = client.put(f"/api/proveedores/{pid}/confirmar", json={"muelle_descargue": 3})
    assert r.status_code in (401, 403)
    assert _fila(pid).estado_confirmacion == "ingresado_wps"


def test_confirmar_deshacer_reconfirmar_exige_muelle(hdr):
    pid = _crear()
    assert _confirmar(hdr, pid, {"muelle_descargue": "04"}).status_code == 200
    assert _fila(pid).muelle_descargue == "4"
    r = client.put(f"/api/proveedores/{pid}/deshacer-confirmacion", headers=hdr)
    assert r.status_code == 200, r.text
    f = _fila(pid)
    assert f.estado_confirmacion == "ingresado_wps" and f.muelle_descargue is None
    assert _confirmar(hdr, pid).status_code == 422
    assert _confirmar(hdr, pid, {"muelle_descargue": ""}).status_code == 422
    assert _fila(pid).estado_confirmacion == "ingresado_wps"
    assert _confirmar(hdr, pid, {"muelle_descargue": 9}).status_code == 200
    assert _fila(pid).muelle_descargue == "9"


def test_confirmar_audit_incluye_muelle(hdr):
    pid = _crear()
    assert _confirmar(hdr, pid, {"muelle_descargue": "07"}).status_code == 200
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT datos_despues FROM audit_log
            WHERE tabla = 'proveedores' AND registro_id = :i ORDER BY created_at DESC LIMIT 1
        """), {"i": pid}).fetchone()
    finally:
        db.close()
    assert row is not None, "no hubo fila de audit_log"
    d = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    assert d["muelle_descargue"] == "7"
    assert d["estado_confirmacion"] == "confirmado"


# -- actualizar (PUT /{id}) ----------------------------------------------
def _put(hdr, pid, body):
    return client.put(f"/api/proveedores/{pid}", headers=hdr, json=body)


@pytest.mark.parametrize("valor", ["", "   ", None])
def test_actualizar_vaciar_muelle_en_confirmado_ocupado_422(hdr, valor):
    pid = _crear(estado="confirmado", muelle="5")
    r = _put(hdr, pid, {"muelle_descargue": valor})
    assert r.status_code == 422, r.text
    assert _fila(pid).muelle_descargue == "5"


@pytest.mark.parametrize("malo", ["abc", "7 y 8", "0", "20", 20])
def test_actualizar_muelle_invalido_en_confirmado_ocupado_422(hdr, malo):
    pid = _crear(estado="confirmado", muelle="5")
    r = _put(hdr, pid, {"muelle_descargue": malo})
    assert r.status_code == 422, r.text
    assert _fila(pid).muelle_descargue == "5"


def test_actualizar_cambia_a_muelle_valido_normaliza(hdr):
    pid = _crear(estado="confirmado", muelle="5")
    assert _put(hdr, pid, {"muelle_descargue": "08"}).status_code == 200
    assert _fila(pid).muelle_descargue == "8"


def test_actualizar_mismo_valor_viejo_no_estandar_pasa(hdr):
    pid = _crear(estado="confirmado", muelle="7 y 8")
    r = _put(hdr, pid, {"muelle_descargue": "7 y 8", "observaciones": "QA"})
    assert r.status_code == 200, r.text
    f = _fila(pid)
    assert f.muelle_descargue == "7 y 8" and f.observaciones == "QA"


def test_actualizar_sin_campo_muelle_no_valida(hdr):
    pid = _crear(estado="confirmado", muelle="7 y 8")
    assert _put(hdr, pid, {"observaciones": "solo obs"}).status_code == 200
    assert _fila(pid).muelle_descargue == "7 y 8"


def test_actualizar_registro_liberado_con_muelle_vacio_pasa(hdr):
    pid = _crear(estado="confirmado", muelle=None, liberado=True)
    r = _put(hdr, pid, {"muelle_descargue": ""})
    assert r.status_code == 200, r.text


def test_actualizar_registro_con_salida_pasa(hdr):
    pid = _crear(estado="confirmado", muelle="5", hora_salida="10:00:00")
    assert _put(hdr, pid, {"muelle_descargue": ""}).status_code == 200


def test_actualizar_ingresado_wps_sin_muelle_pasa(hdr):
    pid = _crear(estado="ingresado_wps")
    assert _put(hdr, pid, {"muelle_descargue": ""}).status_code == 200
    assert _put(hdr, pid, {"muelle_descargue": "abc"}).status_code == 200
