"""Alta de conductores por el puesto peatonal (2026-10-08).

Decisión: solo guarda_peatonal y admin crean/editan en el maestro
`conductores`; bodega/vehicular solo eligen de la lista; coordinador solo
lectura. flota exige conductor_id del maestro. Corre contra el Postgres LOCAL
de pruebas con la migración 2026-10-08_conductores_permisos_conductor_id_cedula.sql
aplicada. Cada test limpia lo que crea.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from tests.flota_alta_helper import alta_ok, conductor_qa_id

client = TestClient(app)
PASSWORD = "Test1234!"


def _h(email):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def tok():
    return {
        k: _h(f"{e}@ejemplo.test")
        for k, e in {
            "peatonal": "guarda.peatonal", "bodega": "guarda.bodega", "vehicular": "guarda.vehicular",
            "coordinador": "coordinador", "admin": "admin", "operador": "operador",
        }.items()
    }


@pytest.fixture()
def limpieza():
    ids = []
    yield ids
    db = SessionLocal()
    for cid in ids:
        db.execute(text(
            "DELETE FROM audit_log WHERE tabla='flota_propia' AND registro_id IN "
            "(SELECT CAST(id AS TEXT) FROM flota_propia WHERE conductor_id=:i)"), {"i": cid})
        db.execute(text("DELETE FROM flota_propia WHERE conductor_id=:i"), {"i": cid})
        db.execute(text("DELETE FROM conductores WHERE id=:i"), {"i": cid})
    db.commit()
    db.close()


def _cedula():
    return "8" + str(uuid.uuid4().int)[:8]


def _crear(headers, limpieza, **extra):
    body = {"conductor": "  juan   perez ", "n_cedula": _cedula(), **extra}
    r = client.post("/api/conductores", json=body, headers=headers)
    if r.status_code == 201:
        limpieza.append(r.json()["id"])
    return r, body


def _borrar_flota(rid):
    db = SessionLocal()
    db.execute(text("DELETE FROM audit_log WHERE tabla='flota_propia' AND registro_id=:i"), {"i": rid})
    db.execute(text("DELETE FROM flota_propia WHERE id=:i"), {"i": rid})
    db.commit()
    db.close()


# ── permisos ──
def test_peatonal_crea_201_y_nombre_en_mayusculas(tok, limpieza):
    r, body = _crear(tok["peatonal"], limpieza)
    assert r.status_code == 201, r.text
    got = client.get(f"/api/conductores/{r.json()['id']}", headers=tok["peatonal"]).json()
    assert got["conductor"] == "JUAN PEREZ"
    assert got["n_cedula"] == body["n_cedula"]


def test_admin_crea_201(tok, limpieza):
    r, _ = _crear(tok["admin"], limpieza)
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("rol", ["bodega", "vehicular", "coordinador", "operador"])
def test_otros_roles_403_al_crear(tok, rol):
    r = client.post("/api/conductores", json={"conductor": "X Y", "n_cedula": _cedula()}, headers=tok[rol])
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("rol", ["bodega", "vehicular", "coordinador"])
def test_otros_roles_403_al_editar(tok, rol):
    r = client.put(f"/api/conductores/{conductor_qa_id()}", json={"celular": "3"}, headers=tok[rol])
    assert r.status_code == 403


@pytest.mark.parametrize("rol", ["peatonal", "bodega", "vehicular", "coordinador", "operador", "admin"])
def test_todos_pueden_listar(tok, rol):
    """operador tiene flota.read y no conductores.read; peatonal al revés."""
    r = client.get("/api/conductores?activo=true", headers=tok[rol])
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_peatonal_no_puede_desactivar_403(tok):
    assert client.delete(f"/api/conductores/{conductor_qa_id()}", headers=tok["peatonal"]).status_code == 403


# ── validación de cédula ──
@pytest.mark.parametrize("ced", ["", None, "CC", "12345", "12345678901", "abc"])
def test_cedula_invalida_422(tok, ced):
    r = client.post("/api/conductores", json={"conductor": "Ana Ruiz", "n_cedula": ced}, headers=tok["peatonal"])
    assert r.status_code == 422, r.text


def test_cedula_con_puntos_se_normaliza(tok, limpieza):
    ced = _cedula()
    con_puntos = f"{ced[:1]}.{ced[1:4]}.{ced[4:]}"
    r, _ = _crear(tok["peatonal"], limpieza, n_cedula=con_puntos)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/conductores/{r.json()['id']}", headers=tok["peatonal"]).json()["n_cedula"] == ced


def test_cedula_duplicada_409_incluso_con_otro_formato(tok, limpieza):
    r, body = _crear(tok["peatonal"], limpieza)
    assert r.status_code == 201
    ced = body["n_cedula"]
    r2 = client.post("/api/conductores", json={"conductor": "Otro", "n_cedula": f"CC {ced}"}, headers=tok["peatonal"])
    assert r2.status_code == 409, r2.text
    assert ced in r2.json()["detail"]


def test_editar_a_cedula_ajena_409_y_propia_ok(tok, limpieza):
    a, ba = _crear(tok["peatonal"], limpieza)
    b, _ = _crear(tok["peatonal"], limpieza)
    r = client.put(f"/api/conductores/{b.json()['id']}", json={"n_cedula": ba["n_cedula"]}, headers=tok["peatonal"])
    assert r.status_code == 409
    r = client.put(
        f"/api/conductores/{a.json()['id']}",
        json={"n_cedula": ba["n_cedula"], "conductor": "nuevo  nombre"}, headers=tok["peatonal"],
    )
    assert r.status_code == 200
    assert client.get(f"/api/conductores/{a.json()['id']}", headers=tok["peatonal"]).json()["conductor"] == "NUEVO NOMBRE"


def test_busqueda_por_cedula_exacta(tok, limpieza):
    r, body = _crear(tok["peatonal"], limpieza)
    hit = client.get(f"/api/conductores?cedula={body['n_cedula']}", headers=tok["peatonal"]).json()
    assert [c["id"] for c in hit] == [r.json()["id"]]
    assert client.get("/api/conductores?cedula=1", headers=tok["peatonal"]).json() == []
    assert client.get("/api/conductores?cedula=", headers=tok["peatonal"]).json() == []


# ── flota ──
def test_flota_sin_conductor_id_422(tok):
    r = client.post(
        "/api/flota",
        json={"placa": "QAPEA01", "conductor": "TEXTO LIBRE", **alta_ok(conductor_id=None)},
        headers=tok["bodega"],
    )
    assert r.status_code == 422
    assert "peatonal" in r.json()["detail"]


def test_flota_conductor_id_inexistente_o_inactivo_422(tok, limpieza):
    r = client.post("/api/flota", json={"placa": "QAPEA01", **alta_ok(conductor_id=str(uuid.uuid4()))}, headers=tok["bodega"])
    assert r.status_code == 422
    r = client.post("/api/flota", json={"placa": "QAPEA01", **alta_ok(conductor_id="no-es-uuid")}, headers=tok["bodega"])
    assert r.status_code == 422
    c, _ = _crear(tok["peatonal"], limpieza)
    client.put(f"/api/conductores/{c.json()['id']}", json={"activo": False}, headers=tok["peatonal"])
    r = client.post("/api/flota", json={"placa": "QAPEA01", **alta_ok(conductor_id=c.json()["id"])}, headers=tok["bodega"])
    assert r.status_code == 422


def test_flota_con_conductor_id_201_copia_nombre_del_maestro(tok, limpieza):
    c, _ = _crear(tok["peatonal"], limpieza, conductor="maria   lopez")
    r = client.post(
        "/api/flota",
        json={"fecha": "2026-10-08", "placa": "QAPEA02", "conductor": "nombre que no cuenta", **alta_ok(conductor_id=c.json()["id"])},
        headers=tok["bodega"],
    )
    assert r.status_code == 201, r.text
    row = client.get(f"/api/flota/{r.json()['id']}", headers=tok["bodega"]).json()
    assert row["conductor"] == "MARIA LOPEZ"
    assert row["conductor_id"] == c.json()["id"]


def test_salida_historica_con_texto_sin_conductor_id_200(tok):
    rid = str(uuid.uuid4())
    db = SessionLocal()
    db.execute(
        text("INSERT INTO flota_propia (id, fecha, placa, conductor, sello, temperatura) "
             "VALUES (:i, CURRENT_DATE, 'QAPEA03', 'Pedro Historico', '123456', '4')"),
        {"i": rid},
    )
    db.commit()
    db.close()
    try:
        r = client.put(
            f"/api/flota/{rid}",
            json={"hora_salida_cedi": "10:00", "fecha_salida": "2026-10-08", "tipo_sello": "Digital"},
            headers=tok["vehicular"],
        )
        assert r.status_code == 200, r.text
    finally:
        _borrar_flota(rid)


def test_put_edicion_suelta_no_revalida_conductor(tok):
    rid = str(uuid.uuid4())
    db = SessionLocal()
    db.execute(text("INSERT INTO flota_propia (id, fecha, placa) VALUES (:i, CURRENT_DATE, 'QAPEA04')"), {"i": rid})
    db.commit()
    db.close()
    try:
        r = client.put(f"/api/flota/{rid}", json={"observacion": "x", "conductor": "ignorado"}, headers=tok["vehicular"])
        assert r.status_code == 200, r.text
        assert client.get(f"/api/flota/{rid}", headers=tok["vehicular"]).json()["conductor"] in (None, "")
    finally:
        _borrar_flota(rid)
