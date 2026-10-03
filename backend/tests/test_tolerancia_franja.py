"""Tolerancia de citas y límite de "tarde" para proveedores (2026-10-03).

Regla de la usuaria: una cita de 7:00 a 8:00 con 15 min de tolerancia es
tarde solo desde las 8:15 (fin de franja + tolerancia).
  - PUT /api/citas/config cambia la tolerancia y la aplica también a las
    citas ya cargadas de hoy en adelante (no a las de días anteriores).
  - _attach_limite_cita entrega a cada proveedor cita_hora_fin y
    cita_tolerancia_min para que el frontend calcule el límite.
"""
import json
import uuid
from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal
from main import app
from routers.proveedores import _attach_limite_cita

client = TestClient(app)


@pytest.fixture(autouse=True)
def admin_con_citas_write():
    """En producción admin tiene citas: ["export","read","write"]; las
    migraciones locales no lo dan (drift). Se otorga solo en la BD local
    mientras corre cada test y se restaura al terminar."""
    db = SessionLocal()
    antes = db.execute(text("SELECT permisos->'citas' FROM roles WHERE nombre='admin'")).scalar()
    db.execute(text("""UPDATE roles SET permisos = jsonb_set(permisos, '{citas}', '["export","read","write"]'::jsonb)
                       WHERE nombre='admin'"""))
    db.commit()
    try:
        yield
    finally:
        if antes is None:
            db.execute(text("UPDATE roles SET permisos = permisos - 'citas' WHERE nombre='admin'"))
        else:
            db.execute(text("UPDATE roles SET permisos = jsonb_set(permisos, '{citas}', CAST(:v AS jsonb)) WHERE nombre='admin'"),
                       {"v": json.dumps(antes)})
        db.commit()
        db.close()


def _admin():
    r = client.post("/api/auth/login", json={"email": "admin@ejemplo.test", "password": "Test1234!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _oc():
    return "4" + str(uuid.uuid4().int)[:9]


@pytest.fixture()
def citas_temp():
    """Una cita de hoy y una de hace 10 días, ambas con tolerancia 60."""
    db = SessionLocal()
    hoy = db.execute(text("SELECT (NOW() AT TIME ZONE 'America/Bogota')::date")).scalar()
    ids = []
    orig = db.execute(text("SELECT valor FROM configuracion WHERE clave='tolerancia_min_default'")).scalar()
    try:
        for f in (hoy, hoy - timedelta(days=10)):
            cid = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO citas_programadas (id, fecha, numero_orden_compra, proveedor_nombre,
                                               hora_cita_inicio, hora_cita_fin, tolerancia_min)
                VALUES (:id, :f, :oc, 'QA TOLERANCIA', '07:00', '08:00', 60)
            """), {"id": cid, "f": f, "oc": _oc()})
            ids.append(cid)
        db.commit()
        yield ids
    finally:
        db.execute(text("DELETE FROM citas_programadas WHERE id::text = ANY(:ids) OR proveedor_nombre = 'QA TOLERANCIA'"), {"ids": ids})
        if orig is not None:
            db.execute(text("UPDATE configuracion SET valor=:v WHERE clave='tolerancia_min_default'"), {"v": orig})
        db.commit()
        db.close()


def test_put_config_aplica_a_citas_de_hoy_en_adelante(citas_temp):
    hoy_id, pasada_id = citas_temp
    r = client.put("/api/citas/config", headers=_admin(), json={"tolerancia_min_default": 15})
    assert r.status_code == 200, r.text
    assert r.json()["tolerancia_min_default"] == 15
    assert r.json()["citas_actualizadas"] >= 1
    db = SessionLocal()
    try:
        tol = dict(db.execute(text("SELECT id::text, tolerancia_min FROM citas_programadas WHERE id::text = ANY(:i)"),
                              {"i": citas_temp}).fetchall())
    finally:
        db.close()
    assert tol[hoy_id] == 15      # la de hoy toma el nuevo valor
    assert tol[pasada_id] == 60   # la histórica no se toca


def test_put_config_rechaza_valores_fuera_de_rango():
    r = client.put("/api/citas/config", headers=_admin(), json={"tolerancia_min_default": 500})
    assert r.status_code == 400


def test_attach_limite_cita_con_y_sin_cita_enlazada(citas_temp):
    hoy_id, _ = citas_temp
    items = [
        {"id": "con-cita", "ordenes": [{"cita_id": hoy_id}]},
        {"id": "sin-cita", "ordenes": [{"cita_id": None}]},
    ]
    db = SessionLocal()
    try:
        _attach_limite_cita(db, items)
        default = int(db.execute(text("SELECT valor FROM configuracion WHERE clave='tolerancia_min_default'")).scalar())
    finally:
        db.close()
    assert items[0]["cita_hora_fin"] == "08:00"
    assert items[0]["cita_tolerancia_min"] == 60
    assert items[1]["cita_hora_fin"] is None
    assert items[1]["cita_tolerancia_min"] == default
