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

from tests.flota_alta_helper import alta_ok
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
    return {"hora_salida_cedi": "10:00", "fecha_salida": "2026-10-07", "tipo_sello": "Digital", **extra}


# ── POST ──
def test_post_sin_conductor_422(headers):
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG02"}, headers=headers)
    assert r.status_code == 422 and "conductor" in r.json()["detail"].lower()


def test_post_conductor_en_blanco_422(headers):
    r = client.post("/api/flota", json={"placa": "QAOBLIG02", "conductor": "   "}, headers=headers)
    assert r.status_code == 422


def test_post_con_conductor_texto_201(headers):
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG02", "conductor": "Juan Perez - CC 123", **alta_ok()}, headers=headers)
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
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG02", "codigo_conductor": row.codigo, **alta_ok()}, headers=headers)
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
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "12:00", "sello_entrada": "654321", "tipo_sello_entrada": "Plástico"}, headers=headers)
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


# ═══ Revisión independiente QA (Diego Torres, 2026-10-07) ═══
def _login(email):
    r = client.post("/api/auth/login", json={"email": email, "password": "Test1234!"})
    if r.status_code != 200:
        pytest.skip(f"usuario {email} no disponible en el seed")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_coordinador_no_puede_cerrar_salida_403(mk):
    """El coordinador es solo lectura: la validación nueva no debe cambiar eso."""
    rid = mk(conductor="C", sello="123456", temperatura="4")
    r = client.put(f"/api/flota/{rid}", json=_salida(), headers=_login("coordinador@ejemplo.test"))
    assert r.status_code == 403


def test_salida_temperatura_numero_json_y_cero(headers, mk):
    """Temperatura enviada como número JSON (no string); 0 es válido."""
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura=0), headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("t", [True, "inf", "-inf", "1e5", "4..5", [4], {"a": 1}])
def test_salida_temperatura_basura_nunca_500(headers, mk, t):
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura=t), headers=headers)
    assert r.status_code in (422, 200), r.text  # jamás 500


def test_salida_temperatura_con_coma_aceptada(headers, mk):
    """'4,5' pasa la validación (el frontend la acepta); se guarda tal cual."""
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="4,5"), headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("sello", [" ", "\t", "  000  ", 0, "0"])
def test_salida_sello_espacios_o_ceros_422(headers, mk, sello):
    rid = mk(conductor="C", temperatura="4")
    r = client.put(f"/api/flota/{rid}", json=_salida(sello=sello), headers=headers)
    assert r.status_code == 422, r.text


def test_salida_sello_con_espacios_alrededor_valido(headers, mk):
    rid = mk(conductor="C", temperatura="4")
    r = client.put(f"/api/flota/{rid}", json=_salida(sello="  123456 "), headers=headers)
    assert r.status_code == 200, r.text


def test_put_hora_salida_null_no_valida_ni_rompe(headers, mk):
    """hora_salida_cedi=null no es transición a salida: no exige campos."""
    rid = mk()
    r = client.put(f"/api/flota/{rid}", json={"hora_salida_cedi": None, "observacion": "x"}, headers=headers)
    assert r.status_code == 200, r.text


@pytest.mark.xfail(reason="PREEXISTENTE (no de este cambio): hora_salida_cedi='' en PUT da 500 por columna TIME; el frontend filtra vacios", strict=True)
def test_put_hora_salida_vacia_no_exige_campos_ni_valida(headers, mk):
    """'' tampoco es transición. Documenta el comportamiento real (TIME en BD)."""
    rid = mk()
    r = client.put(f"/api/flota/{rid}", json={"hora_salida_cedi": "", "observacion": "x"}, headers=headers)
    assert r.status_code == 200, r.text


def test_registro_abierto_de_bodega_sin_conductor_sale_con_conductor_en_el_put(headers, mk):
    """Escenario CEDI: bodega dejó el registro sin conductor; el guarda
    vehicular lo completa en el mismo PUT de la salida."""
    rid = mk(sello="123456", temperatura="3")
    r = client.put(f"/api/flota/{rid}", json=_salida(conductor="Pedro Gómez"), headers=headers)
    assert r.status_code == 200, r.text


def test_guarda_vehicular_cierra_salida_y_llegada(mk):
    h = _login("guarda.vehicular@ejemplo.test")
    rid = mk(conductor="C")
    r = client.put(f"/api/flota/{rid}", json=_salida(sello="777001", temperatura="2"), headers=h)
    assert r.status_code == 200, r.text
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "18:00", "fecha_llegada": "2026-10-07", "sello_entrada": "777001", "tipo_sello_entrada": "Digital"}, headers=h)
    assert r.status_code == 200, r.text


def test_llegada_con_sello_en_cero_aun_con_salida_ya_cerrada(headers, mk):
    rid = mk(conductor="C", sello="123456", temperatura="4", hora_salida_cedi="10:00")
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "18:00", "sello_entrada": "0000"}, headers=headers)
    assert r.status_code == 422


def test_reintento_tras_422_no_deja_estado_a_medias(headers, mk):
    """Un PUT rechazado no debe persistir nada (cola offline descarta fallidos)."""
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(observacion="no debe guardarse"), headers=headers)
    assert r.status_code == 422
    db = SessionLocal()
    row = db.execute(text("SELECT hora_salida_cedi, observacion FROM flota_propia WHERE id=:i"), {"i": rid}).fetchone()
    db.close()
    assert row.hora_salida_cedi is None and row.observacion != "no debe guardarse"


# ═══ N/A y tipo de sello obligatorio (pedido de la usuaria, 2026-10-07) ═══
def test_salida_sin_tipo_sello_422(headers, mk):
    rid = mk(conductor="C", sello="123456", temperatura="4")
    body = _salida()
    body.pop("tipo_sello")
    r = client.put(f"/api/flota/{rid}", json=body, headers=headers)
    assert r.status_code == 422 and "tipo de sello" in r.json()["detail"].lower()


def test_salida_con_tipo_sello_ya_guardado_200(headers, mk):
    rid = mk(conductor="C", sello="123456", temperatura="4", tipo_sello="Digital")
    body = _salida()
    body.pop("tipo_sello")
    assert client.put(f"/api/flota/{rid}", json=body, headers=headers).status_code == 200


def test_salida_todo_na_200(headers, mk):
    """Si nada aplica, el guarda marca N/A en temperatura, sello y tipo."""
    rid = mk(conductor="C")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="N/A", sello="N/A", tipo_sello="N/A", obs_salida="Carga seca, no requiere frio"), headers=headers)
    assert r.status_code == 200, r.text
    g = client.get(f"/api/flota/{rid}", headers=headers).json()
    assert (g["temperatura"], g["sello"], g["tipo_sello"]) == ("N/A", "N/A", "N/A")


def test_llegada_sin_tipo_sello_entrada_422(headers, mk):
    rid = mk(conductor="C", hora_salida_cedi="09:00")
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "12:00", "sello_entrada": "654321"}, headers=headers)
    assert r.status_code == 422 and "tipo de sello" in r.json()["detail"].lower()


def test_llegada_todo_na_200(headers, mk):
    rid = mk(conductor="C", hora_salida_cedi="09:00")
    r = client.put(f"/api/flota/{rid}", json={"hora_llegada": "12:00", "sello_entrada": "N/A", "tipo_sello_entrada": "N/A"}, headers=headers)
    assert r.status_code == 200, r.text


# ═══ Registro inicial: campos obligatorios en el servidor ═══
@pytest.mark.parametrize("campo", ["muelle_cargue", "n_pallets", "n_contenedores", "cant_volumen_externo", "tienda_1", "protocolo", "observacion"])
def test_alta_sin_campo_obligatorio_422(headers, campo):
    body = {"fecha": "2026-10-07", "placa": "QAOBLIG03", "conductor": "C", **alta_ok()}
    body.pop(campo)
    r = client.post("/api/flota", json=body, headers=headers)
    assert r.status_code == 422, r.text
    assert "obligatorios" in r.json()["detail"].lower()


def test_alta_completa_con_na_y_ceros_201(headers):
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG03", "conductor": "C", **alta_ok()}, headers=headers)
    assert r.status_code == 201, r.text
    _borrar(r.json()["id"])


def test_alta_campo_en_blanco_cuenta_como_faltante(headers):
    r = client.post("/api/flota", json={"fecha": "2026-10-07", "placa": "QAOBLIG03", "conductor": "C", **alta_ok(protocolo="   ")}, headers=headers)
    assert r.status_code == 422


def test_salida_temperatura_na_sin_motivo_422(headers, mk):
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="N/A"), headers=headers)
    assert r.status_code == 422 and "motivo" in r.json()["detail"].lower()


def test_salida_temperatura_na_motivo_en_blanco_422(headers, mk):
    rid = mk(conductor="C", sello="123456")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="N/A", obs_salida="   "), headers=headers)
    assert r.status_code == 422


def test_salida_temperatura_na_con_motivo_ya_guardado_200(headers, mk):
    rid = mk(conductor="C", sello="123456", obs_salida="Carga seca")
    r = client.put(f"/api/flota/{rid}", json=_salida(temperatura="N/A"), headers=headers)
    assert r.status_code == 200, r.text


def test_salida_con_temperatura_numerica_no_exige_motivo(headers, mk):
    rid = mk(conductor="C", sello="123456")
    assert client.put(f"/api/flota/{rid}", json=_salida(temperatura="4"), headers=headers).status_code == 200
