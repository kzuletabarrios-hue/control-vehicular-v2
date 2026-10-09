"""Huecos de regresion operativa del cambio 'conductores' (2026-10-08).

Cubre lo que el cambio podia romper en la operacion diaria: permisos en
/auth/login y /auth/me (los usa puede() en el frontend), registros abiertos
historicos sin conductor_id (cierre de salida y llegada), duplicar,
conductor desactivado con un registro abierto y reutilizacion de cedula.
Postgres LOCAL de pruebas con la migracion 2026-10-08 aplicada.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from tests.flota_alta_helper import alta_ok

client = TestClient(app)
PASSWORD = "Test1234!"
EMAILS = {
    "peatonal": "guarda.peatonal", "bodega": "guarda.bodega", "vehicular": "guarda.vehicular",
    "coordinador": "coordinador", "admin": "admin", "operador": "operador",
}


def _login(rol):
    r = client.post("/api/auth/login", json={"email": f"{EMAILS[rol]}@ejemplo.test", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def sesion():
    return {k: _login(k) for k in EMAILS}


def _h(sesion, rol):
    return {"Authorization": f"Bearer {sesion[rol]['access_token']}"}


def _cedula():
    return "7" + str(uuid.uuid4().int)[:8]


def _sql(q, **p):
    db = SessionLocal()
    try:
        db.execute(text(q), p)
        db.commit()
    finally:
        db.close()


def _abierto_historico(**cols):
    """Registro abierto como los de produccion: conductor en texto, sin conductor_id."""
    rid = str(uuid.uuid4())
    base = {"id": rid, "placa": "QAREG01", "conductor": "Pedro Historico", "sello": "123456", "temperatura": "4"}
    base.update(cols)
    nombres = ", ".join(base)
    marcas = ", ".join(f":{k}" for k in base)
    _sql(f"INSERT INTO flota_propia (fecha, {nombres}) VALUES (CURRENT_DATE, {marcas})", **base)
    return rid


def _borrar_flota(*ids):
    for rid in ids:
        _sql("DELETE FROM audit_log WHERE tabla='flota_propia' AND registro_id=:i", i=rid)
        _sql("DELETE FROM flota_propia WHERE id=:i", i=rid)


@pytest.fixture()
def conductor(sesion):
    r = client.post("/api/conductores", json={"conductor": "qa regresion", "n_cedula": _cedula()},
                    headers=_h(sesion, "peatonal"))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    yield cid
    _sql("DELETE FROM audit_log WHERE tabla='flota_propia' AND registro_id IN "
         "(SELECT CAST(id AS TEXT) FROM flota_propia WHERE conductor_id=:i)", i=cid)
    _sql("DELETE FROM flota_propia WHERE conductor_id=:i", i=cid)
    _sql("DELETE FROM conductores WHERE id=:i", i=cid)


# ── permisos que consume el frontend: puede(user,'conductores',...) ──
@pytest.mark.parametrize("rol,esperado", [
    ("admin", {"read", "write", "delete"}),
    ("peatonal", {"read", "write"}),
    ("bodega", {"read"}),
    ("vehicular", {"read"}),
    ("coordinador", {"read"}),
])
def test_login_y_me_exponen_permisos_conductores(sesion, rol, esperado):
    login_perm = sesion[rol]["usuario"]["permisos"].get("conductores", [])
    me = client.get("/api/auth/me", headers=_h(sesion, rol)).json()
    assert set(login_perm) == esperado
    assert set(me["permisos"].get("conductores", [])) == esperado


def test_operador_sin_permiso_conductores_pero_si_lista_y_crea_flota(sesion):
    assert "conductores" not in sesion["operador"]["usuario"]["permisos"]
    h = _h(sesion, "operador")
    assert client.get("/api/conductores?activo=true", headers=h).status_code == 200
    r = client.post("/api/flota", json={"fecha": "2026-10-08", "placa": "QAREG02", **alta_ok()}, headers=h)
    assert r.status_code == 201, r.text
    _borrar_flota(r.json()["id"])


# ── registros abiertos de produccion (sin conductor_id) deben cerrar ──
def test_llegada_de_registro_historico_sin_conductor_id_200(sesion):
    rid = _abierto_historico(hora_salida_cedi="08:00")
    try:
        r = client.put(f"/api/flota/{rid}",
                       json={"hora_llegada": "14:00", "sello_entrada": "654321", "tipo_sello_entrada": "Digital"},
                       headers=_h(sesion, "vehicular"))
        assert r.status_code == 200, r.text
    finally:
        _borrar_flota(rid)


def test_salida_historica_sin_ningun_conductor_sigue_exigiendolo_422(sesion):
    rid = _abierto_historico(conductor=None)
    try:
        r = client.put(f"/api/flota/{rid}",
                       json={"hora_salida_cedi": "10:00", "tipo_sello": "Digital"},
                       headers=_h(sesion, "vehicular"))
        assert r.status_code == 422
        assert "conductor" in r.json()["detail"].lower()
    finally:
        _borrar_flota(rid)


def test_salida_historica_con_conductor_id_del_picker_200_y_copia_nombre(sesion, conductor):
    rid = _abierto_historico(conductor=None)
    try:
        r = client.put(f"/api/flota/{rid}",
                       json={"hora_salida_cedi": "10:00", "tipo_sello": "Digital",
                             "conductor_id": conductor, "conductor": "lo que mande el cliente"},
                       headers=_h(sesion, "vehicular"))
        assert r.status_code == 200, r.text
        row = client.get(f"/api/flota/{rid}", headers=_h(sesion, "vehicular")).json()
        assert row["conductor"] == "QA REGRESION"
        assert row["conductor_id"] == conductor
    finally:
        _borrar_flota(rid)


def test_conductor_desactivado_con_registro_abierto_puede_cerrar_salida_y_llegada(sesion, conductor):
    """Escenario: el peatonal desactiva al conductor mientras su camion esta en ruta."""
    r = client.post("/api/flota", json={"fecha": "2026-10-08", "placa": "QAREG03", **alta_ok(conductor_id=conductor)},
                    headers=_h(sesion, "bodega"))
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    try:
        assert client.put(f"/api/conductores/{conductor}", json={"activo": False},
                          headers=_h(sesion, "peatonal")).status_code == 200
        s = client.put(f"/api/flota/{rid}",
                       json={"hora_salida_cedi": "10:00", "sello": "111222", "tipo_sello": "Digital", "temperatura": "4"},
                       headers=_h(sesion, "vehicular"))
        assert s.status_code == 200, s.text
        ll = client.put(f"/api/flota/{rid}",
                        json={"hora_llegada": "15:00", "sello_entrada": "333444", "tipo_sello_entrada": "Digital"},
                        headers=_h(sesion, "vehicular"))
        assert ll.status_code == 200, ll.text
    finally:
        _borrar_flota(rid)


# ── duplicar ──
def test_duplicar_copia_conductor_id_y_nombre(sesion, conductor):
    r = client.post("/api/flota", json={"fecha": "2026-10-08", "placa": "QAREG04", **alta_ok(conductor_id=conductor)},
                    headers=_h(sesion, "bodega"))
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    d = client.post(f"/api/flota/{rid}/duplicar", headers=_h(sesion, "bodega"))
    assert d.status_code == 201, d.text
    try:
        copia = client.get(f"/api/flota/{d.json()['id']}", headers=_h(sesion, "bodega")).json()
        assert copia["conductor_id"] == conductor
        assert copia["conductor"] == "QA REGRESION"
    finally:
        _borrar_flota(rid, d.json()["id"])


def test_duplicar_registro_historico_sin_conductor_id_no_falla(sesion):
    rid = _abierto_historico()
    d = client.post(f"/api/flota/{rid}/duplicar", headers=_h(sesion, "bodega"))
    try:
        assert d.status_code == 201, d.text
        assert client.get(f"/api/flota/{d.json()['id']}", headers=_h(sesion, "bodega")).json()["conductor_id"] is None
    finally:
        _borrar_flota(rid, *([d.json()["id"]] if d.status_code == 201 else []))


# ── listado de flota con registros nuevos y viejos mezclados ──
def test_listado_flota_mezcla_registros_con_y_sin_conductor_id(sesion, conductor):
    viejo = _abierto_historico(placa="QAREG05")
    r = client.post("/api/flota", json={"fecha": "2026-10-08", "placa": "QAREG06", **alta_ok(conductor_id=conductor)},
                    headers=_h(sesion, "bodega"))
    nuevo = r.json()["id"]
    try:
        lst = client.get("/api/flota?placa=QAREG0", headers=_h(sesion, "vehicular"))
        assert lst.status_code == 200
        por_id = {x["id"]: x for x in lst.json()["items"]}
        assert por_id[viejo]["conductor"] == "Pedro Historico"
        assert por_id[nuevo]["conductor_id"] == conductor
    finally:
        _borrar_flota(viejo, nuevo)


# ── maestro: bordes que usa la pantalla ──
def test_peatonal_desactiva_con_put_activo_false_y_sale_de_la_lista_activa(sesion, conductor):
    h = _h(sesion, "peatonal")
    assert client.put(f"/api/conductores/{conductor}", json={"activo": False}, headers=h).status_code == 200
    ids = [c["id"] for c in client.get("/api/conductores?activo=true", headers=h).json()]
    assert conductor not in ids


def test_cedula_de_conductor_desactivado_sigue_bloqueando_409(sesion, conductor):
    """Documenta el comportamiento actual: la cedula de un inactivo no se puede
    reusar; la pantalla solo lista activos, asi que el peatonal vera
    'Ya registrado' sin poder reactivar al conductor."""
    h = _h(sesion, "peatonal")
    ced = client.get(f"/api/conductores/{conductor}", headers=h).json()["n_cedula"]
    client.put(f"/api/conductores/{conductor}", json={"activo": False}, headers=h)
    r = client.post("/api/conductores", json={"conductor": "otro", "n_cedula": ced}, headers=h)
    if r.status_code == 201:
        _sql("DELETE FROM conductores WHERE id=:i", i=r.json()["id"])
    assert r.status_code == 409


def test_editar_solo_celular_de_conductor_con_cedula_basura_no_exige_cedula(sesion):
    cid = str(uuid.uuid4())
    _sql("INSERT INTO conductores (id, conductor, n_cedula, activo) VALUES (:i, 'LEGADO', 'CC', TRUE)", i=cid)
    try:
        r = client.put(f"/api/conductores/{cid}", json={"celular": "3001234567"}, headers=_h(sesion, "peatonal"))
        assert r.status_code == 200, r.text
        r = client.put(f"/api/conductores/{cid}", json={"n_cedula": _cedula()}, headers=_h(sesion, "peatonal"))
        assert r.status_code == 200, r.text
    finally:
        _sql("DELETE FROM conductores WHERE id=:i", i=cid)


def test_carga_masiva_conductores_exige_conductores_write(sesion):
    body = {"filas": [{"conductor": "X", "n_cedula": "1234567"}]}
    for rol in ("bodega", "vehicular", "operador", "coordinador"):
        r = client.post("/api/carga/conductores", json=body, headers=_h(sesion, rol))
        assert r.status_code == 403, (rol, r.status_code)
