"""Tests de GET /api/dashboard/estadisticas (tarea 2026-09-26, rama
dashboard-estadisticas).

Corren contra el Postgres LOCAL de pruebas levantado con
`bash scripts/dev_test_db.sh reset` (backend/.env.test) -- el guardrail de
backend/conftest.py aborta toda la sesión de pytest si DATABASE_URL
apuntara a producción.

Cubre el contrato de docs/estadisticas_contrato.md: forma exacta del
JSON de respuesta, validaciones de fechas (formato, desde > hasta,
rango máximo de 366 días), y permisos (dashboard:read, igual que
/resumen y /tiempo-autorregistro).
"""
import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from sqlalchemy import text

client = TestClient(app)

SEED_PASSWORD = "Test1234!"
ADMIN_EMAIL = "admin@ejemplo.test"
COORDINADOR_EMAIL = "coordinador@ejemplo.test"
GUARDA_BODEGA_EMAIL = "guarda.bodega@ejemplo.test"


def _login(email: str, password: str = SEED_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _requiere_usuario_seed(email: str):
    db = SessionLocal()
    row = db.execute(text("SELECT 1 FROM usuarios WHERE email = :e"), {"e": email}).fetchone()
    db.close()
    if not row:
        pytest.skip(
            f"El usuario de seed '{email}' no existe en la BD de pruebas -- "
            "corre `bash scripts/dev_test_db.sh reset`."
        )


@pytest.fixture()
def token_admin():
    _requiere_usuario_seed(ADMIN_EMAIL)
    resp = _login(ADMIN_EMAIL)
    assert resp.status_code == 200, f"login de admin falló: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture()
def token_coordinador():
    _requiere_usuario_seed(COORDINADOR_EMAIL)
    resp = _login(COORDINADOR_EMAIL)
    assert resp.status_code == 200, f"login de coordinador falló: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture()
def token_guarda_bodega():
    _requiere_usuario_seed(GUARDA_BODEGA_EMAIL)
    resp = _login(GUARDA_BODEGA_EMAIL)
    assert resp.status_code == 200, f"login de guarda_bodega falló: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


# ── Fixtures de datos aislados para casos límite (secciones B y D) ────
# Inserción directa por SQL (sin pasar por ningún endpoint de escritura,
# que no es lo que se prueba aquí) y limpieza explícita en `finally` --
# mismo patrón que test_flota_permisos_coordinador.py::registro_flota.
# Se usan fechas de 2029 (fuera de cualquier fecha ya usada por otros
# tests de este archivo o por supabase/seed.sql) para que cada caso sea
# reproducible sin depender del orden de ejecución ni de qué día es
# "hoy" cuando corre la suite.


def _insert_proveedor_edge(fecha, estado_confirmacion="confirmado", hora_ingreso=None,
                            hora_ingreso_confirmado=None, hora_salida=None, fecha_salida=None,
                            placa_vehiculo="QA-EDGE-B"):
    db = SessionLocal()
    pid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO proveedores (id, fecha, placa_vehiculo, estado_confirmacion,
                                  hora_ingreso, hora_ingreso_confirmado, hora_salida, fecha_salida)
        VALUES (:id, :fecha, :placa, :estado, :hi, :hic, :hs, :fs)
    """), {
        "id": pid, "fecha": fecha, "placa": placa_vehiculo, "estado": estado_confirmacion,
        "hi": hora_ingreso, "hic": hora_ingreso_confirmado, "hs": hora_salida, "fs": fecha_salida,
    })
    db.commit()
    db.close()
    return pid


def _delete_proveedor(pid):
    db = SessionLocal()
    db.execute(text("DELETE FROM proveedores_ordenes WHERE proveedor_id = :id"), {"id": pid})
    db.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": pid})
    db.commit()
    db.close()


def _insert_flota_edge(fecha, placa="QA-EDGE-D", fecha_salida=None, hora_salida_cedi=None,
                        fecha_llegada=None, hora_llegada=None):
    db = SessionLocal()
    fid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO flota_propia (id, fecha, placa, fecha_salida, hora_salida_cedi, fecha_llegada, hora_llegada)
        VALUES (:id, :fecha, :placa, :fs, :hsc, :fl, :hl)
    """), {
        "id": fid, "fecha": fecha, "placa": placa,
        "fs": fecha_salida, "hsc": hora_salida_cedi, "fl": fecha_llegada, "hl": hora_llegada,
    })
    db.commit()
    db.close()
    return fid


def _delete_flota(fid):
    db = SessionLocal()
    db.execute(text("DELETE FROM flota_propia WHERE id = :id"), {"id": fid})
    db.commit()
    db.close()


# ── Forma de la respuesta ─────────────────────────────────────────────


def test_estadisticas_sin_parametros_200_forma_correcta(token_admin):
    resp = client.get("/api/dashboard/estadisticas", headers=_bearer(token_admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == {
        "fecha_desde", "fecha_hasta", "tendencia_diaria",
        "tiempo_muelle_proveedores", "ingresos_por_hora",
        "tiempo_ruta_flota", "carga_despachada_por_dia",
        "cumplimiento_sellos",
    }
    assert isinstance(body["fecha_desde"], str)
    assert isinstance(body["fecha_hasta"], str)

    # Default de 30 días: fecha_hasta - fecha_desde == 30
    from datetime import date
    desde = date.fromisoformat(body["fecha_desde"])
    hasta = date.fromisoformat(body["fecha_hasta"])
    assert (hasta - desde).days == 30

    # A: una fila por día, sin huecos.
    assert len(body["tendencia_diaria"]) == 31
    fila = body["tendencia_diaria"][0]
    assert set(fila.keys()) == {"fecha", "flota", "proveedores", "control_acceso", "visitantes"}
    for campo in ("flota", "proveedores", "control_acceso", "visitantes"):
        assert isinstance(fila[campo], int)

    # B: global + por_dia con longitud = rango completo.
    b = body["tiempo_muelle_proveedores"]
    assert set(b.keys()) == {"global", "por_dia"}
    assert set(b["global"].keys()) == {"promedio_minutos", "mediana_minutos", "n_validos"}
    assert len(b["por_dia"]) == 31
    for fila_b in b["por_dia"]:
        assert set(fila_b.keys()) == {"fecha", "promedio_minutos", "mediana_minutos", "n_validos"}
        assert isinstance(fila_b["n_validos"], int)
        if fila_b["n_validos"] == 0:
            assert fila_b["promedio_minutos"] is None
            assert fila_b["mediana_minutos"] is None

    # C: 24 horas exactas, 0-23.
    c = body["ingresos_por_hora"]
    assert len(c) == 24
    assert [f["hora"] for f in c] == list(range(24))
    for fila_c in c:
        assert set(fila_c.keys()) == {"hora", "control_acceso", "proveedores", "flota_salidas_cedi"}

    # D: global + top_placas (máx 10, puede ser menor).
    d = body["tiempo_ruta_flota"]
    assert set(d.keys()) == {"global", "top_placas"}
    assert set(d["global"].keys()) == {"promedio_minutos", "mediana_minutos", "n_validos"}
    assert len(d["top_placas"]) <= 10
    for fila_d in d["top_placas"]:
        assert set(fila_d.keys()) == {"placa", "promedio_minutos", "mediana_minutos", "n_viajes"}

    # E: una fila por día.
    e = body["carga_despachada_por_dia"]
    assert len(e) == 31
    for fila_e in e:
        assert set(fila_e.keys()) == {"fecha", "pallets", "contenedores"}
        assert isinstance(fila_e["pallets"], int)
        assert isinstance(fila_e["contenedores"], int)

    # F: global + por_dia con 0/null coherente.
    f = body["cumplimiento_sellos"]
    assert set(f.keys()) == {"global", "por_dia"}
    assert set(f["global"].keys()) == {
        "total_viajes", "con_sello_salida", "pct_sello_salida",
        "viajes_con_llegada", "con_sello_entrada", "pct_sello_entrada",
    }
    assert len(f["por_dia"]) == 31
    for fila_f in f["por_dia"]:
        if fila_f["total_viajes"] == 0:
            assert fila_f["con_sello_salida"] == 0
            assert fila_f["pct_sello_salida"] is None
        if fila_f["viajes_con_llegada"] == 0:
            assert fila_f["con_sello_entrada"] == 0
            assert fila_f["pct_sello_entrada"] is None


def test_estadisticas_con_rango_explicito_devuelve_ese_rango(token_admin):
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-05"},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fecha_desde"] == "2026-01-01"
    assert body["fecha_hasta"] == "2026-01-05"
    assert len(body["tendencia_diaria"]) == 5
    assert [f["fecha"] for f in body["tendencia_diaria"]] == [
        "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
    ]


# ── Validaciones de fechas ──────────────────────────────────────────


def test_estadisticas_fecha_desde_mayor_a_hasta_400(token_admin):
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_desde": "2026-02-01", "fecha_hasta": "2026-01-01"},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 400
    assert "fecha_desde no puede ser mayor a fecha_hasta" in resp.json()["detail"]


def test_estadisticas_rango_mayor_a_366_dias_400(token_admin):
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_desde": "2025-01-01", "fecha_hasta": "2026-06-01"},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 400
    assert "366" in resp.json()["detail"]


def test_estadisticas_rango_exactamente_366_dias_200(token_admin):
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_desde": "2025-01-01", "fecha_hasta": "2026-01-01"},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 200, resp.text


def test_estadisticas_formato_invalido_400(token_admin):
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_desde": "no-es-una-fecha", "fecha_hasta": "2026-01-01"},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 400
    assert "inválido" in resp.json()["detail"]


def test_estadisticas_solo_fecha_hasta_completa_desde_con_30_dias(token_admin):
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_hasta": "2026-03-31"},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fecha_hasta"] == "2026-03-31"
    assert body["fecha_desde"] == "2026-03-01"


# ── Permisos ─────────────────────────────────────────────────────────


def test_estadisticas_sin_token_401():
    resp = client.get("/api/dashboard/estadisticas")
    assert resp.status_code == 401


def test_estadisticas_admin_200(token_admin):
    resp = client.get("/api/dashboard/estadisticas", headers=_bearer(token_admin))
    assert resp.status_code == 200, resp.text


def test_estadisticas_coordinador_200(token_coordinador):
    """coordinador tiene "dashboard":["read"] (migración
    20260804110000_alta_formal_coordinador_retroactivo.sql) y es uno de
    los 4 roles que ve la pestaña Estadísticas en HomePage.js
    (showEstadisticas = isAdmin||isCoordinador)."""
    resp = client.get("/api/dashboard/estadisticas", headers=_bearer(token_coordinador))
    assert resp.status_code == 200, resp.text


def test_estadisticas_guarda_bodega_200_pese_a_no_ver_la_pestana(token_guarda_bodega):
    """HALLAZGO DE PERMISOS (no es un bug de este endpoint -- es una
    decisión de diseño heredada de /resumen y /tiempo-autorregistro,
    documentada en el contrato sección 0): require_permiso("dashboard",
    "read") es un permiso de MÓDULO, no de endpoint. Verificado contra
    la BD local de pruebas (roles.permisos->'dashboard'): admin,
    supervisor, operador, consulta, coordinador, guarda_bodega,
    guarda_peatonal y guarda_vehicular TODOS tienen "dashboard":["read"]
    -- solo recorredor_externo no lo tiene.

    HomePage.js oculta la pestaña "Estadísticas" únicamente para
    guardas/recorredor vía `showEstadisticas = isAdmin||isCoordinador`
    (control de UI, no de autorización). Cualquier guarda de puesto con
    su token real (o alguien con Postman/curl) puede invocar
    GET /dashboard/estadisticas directamente y obtener 200 con el JSON
    completo, pese a nunca ver el botón en la interfaz.

    Este test documenta el comportamiento actual (no lo corrige: no es
    responsabilidad de QA decidir permisos). Recomendación de Diego para
    Jorge/Alejandro si se quiere negar el acceso a nivel de API real
    (no solo ocultarlo en UI): dar de alta un permiso propio y más
    granular, ej. "estadisticas":["read"], en vez de reusar "dashboard"
    -- cambio de permisos fuera del alcance de esta tarea."""
    resp = client.get("/api/dashboard/estadisticas", headers=_bearer(token_guarda_bodega))
    assert resp.status_code == 200, resp.text


# ── Casos límite: rango de 1 día (Hoy) sin ningún dato ────────────────


def test_estadisticas_un_dia_sin_datos_null_y_longitudes_correctas(token_admin):
    """Rango de 1 solo día (equivalente al chip 'Hoy' del frontend)
    sobre una fecha aislada sin ningún registro en ninguna tabla: A/C/E/F
    se rellenan con 0 (nunca ausencia de fila), B/D van en null/[] en vez
    de 0 falso -- exactamente el criterio del contrato, sección 3."""
    dia = "2029-01-15"
    resp = client.get(
        "/api/dashboard/estadisticas",
        params={"fecha_desde": dia, "fecha_hasta": dia},
        headers=_bearer(token_admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fecha_desde"] == dia
    assert body["fecha_hasta"] == dia

    # A: 1 fila, todo en 0 (relleno explícito, no ausencia de fila).
    assert body["tendencia_diaria"] == [
        {"fecha": dia, "flota": 0, "proveedores": 0, "control_acceso": 0, "visitantes": 0}
    ]

    # B: por_dia 1 fila, n_validos=0 -> promedio/mediana null (nunca 0).
    b = body["tiempo_muelle_proveedores"]
    assert b["global"] == {"promedio_minutos": None, "mediana_minutos": None, "n_validos": 0}
    assert b["por_dia"] == [{"fecha": dia, "promedio_minutos": None, "mediana_minutos": None, "n_validos": 0}]

    # C: 24 horas exactas, todas en 0.
    c = body["ingresos_por_hora"]
    assert len(c) == 24
    assert [f["hora"] for f in c] == list(range(24))
    assert all(f["control_acceso"] == 0 and f["proveedores"] == 0 and f["flota_salidas_cedi"] == 0 for f in c)

    # D: global en null, top_placas vacío (sin relleno, contrato sección 3).
    d = body["tiempo_ruta_flota"]
    assert d["global"] == {"promedio_minutos": None, "mediana_minutos": None, "n_validos": 0}
    assert d["top_placas"] == []

    # E: 1 fila, pallets/contenedores en 0.
    assert body["carga_despachada_por_dia"] == [{"fecha": dia, "pallets": 0, "contenedores": 0}]

    # F: 1 fila, conteos en 0 y porcentajes en null (denominador 0, nunca 0 falso).
    f = body["cumplimiento_sellos"]
    assert f["global"] == {
        "total_viajes": 0, "con_sello_salida": 0, "pct_sello_salida": None,
        "viajes_con_llegada": 0, "con_sello_entrada": 0, "pct_sello_entrada": None,
    }
    assert f["por_dia"] == [{
        "fecha": dia, "total_viajes": 0, "con_sello_salida": 0, "pct_sello_salida": None,
        "viajes_con_llegada": 0, "con_sello_entrada": 0, "pct_sello_entrada": None,
    }]


# ── Casos límite: cruce de medianoche ─────────────────────────────────


def test_estadisticas_muelle_cruce_medianoche_se_contabiliza_correctamente(token_admin):
    """Proveedor que ingresa a las 23:00 y sale (fecha_salida NULL,
    hueco de dato real) con hora_salida 01:00: el contrato infiere +1
    día porque 01:00 < 23:00 (sección B, `CASE WHEN salida_ts_base <
    ingreso_ts THEN salida_ts_base + interval '1 day'`). Duración
    esperada: 2 horas = 120 minutos, contabilizada en el día de
    ingreso (p.fecha), no en el de salida."""
    dia = "2029-02-10"
    pid = _insert_proveedor_edge(
        fecha=date.fromisoformat(dia),
        estado_confirmacion="confirmado",
        hora_ingreso=time(23, 0),
        hora_salida=time(1, 0),
        fecha_salida=None,
        placa_vehiculo="QA-MEDIANOCHE-B",
    )
    try:
        resp = client.get(
            "/api/dashboard/estadisticas",
            params={"fecha_desde": dia, "fecha_hasta": dia},
            headers=_bearer(token_admin),
        )
        assert resp.status_code == 200, resp.text
        b = resp.json()["tiempo_muelle_proveedores"]
        assert b["global"] == {"promedio_minutos": 120.0, "mediana_minutos": 120.0, "n_validos": 1}
        assert b["por_dia"] == [{"fecha": dia, "promedio_minutos": 120.0, "mediana_minutos": 120.0, "n_validos": 1}]
    finally:
        _delete_proveedor(pid)


def test_estadisticas_ruta_flota_cruce_medianoche_se_contabiliza_correctamente(token_admin):
    """Flota: fecha_salida y fecha_llegada son columnas explícitas
    (sección D no necesita inferir cruce de medianoche, a diferencia de
    B). Salida 23:30 del día D, llegada 00:30 del día D+1: duración real
    60 minutos, contabilizada en el día de salida (f.fecha_salida)."""
    d = date.fromisoformat("2029-02-20")
    d1 = date.fromisoformat("2029-02-21")
    fid = _insert_flota_edge(
        fecha=d, placa="QA-MEDIANOCHE-D",
        fecha_salida=d, hora_salida_cedi=time(23, 30),
        fecha_llegada=d1, hora_llegada=time(0, 30),
    )
    try:
        resp = client.get(
            "/api/dashboard/estadisticas",
            params={"fecha_desde": d.isoformat(), "fecha_hasta": d.isoformat()},
            headers=_bearer(token_admin),
        )
        assert resp.status_code == 200, resp.text
        dd = resp.json()["tiempo_ruta_flota"]
        assert dd["global"] == {"promedio_minutos": 60.0, "mediana_minutos": 60.0, "n_validos": 1}
        assert dd["top_placas"] == [
            {"placa": "QA-MEDIANOCHE-D", "promedio_minutos": 60.0, "mediana_minutos": 60.0, "n_viajes": 1}
        ]
    finally:
        _delete_flota(fid)


# ── Casos límite: exclusión por umbral (no cuentan en n_validos) ─────


def test_estadisticas_muelle_mas_de_24h_excluido_de_n_validos(token_admin):
    """min > 1440 (24h): ningún proveedor 'confirmado' debería tardar
    más de un día completo -- se excluye como olvido de registrar
    salida, no como medición real (contrato, sección 5)."""
    dia = "2029-03-01"
    pid = _insert_proveedor_edge(
        fecha=date.fromisoformat(dia),
        estado_confirmacion="confirmado",
        hora_ingreso=time(0, 0),
        hora_salida=time(0, 0),
        fecha_salida=date.fromisoformat("2029-03-03"),  # 48h exactas
        placa_vehiculo="QA-UMBRAL-B-48H",
    )
    try:
        resp = client.get(
            "/api/dashboard/estadisticas",
            params={"fecha_desde": dia, "fecha_hasta": dia},
            headers=_bearer(token_admin),
        )
        assert resp.status_code == 200, resp.text
        b = resp.json()["tiempo_muelle_proveedores"]
        assert b["global"] == {"promedio_minutos": None, "mediana_minutos": None, "n_validos": 0}
    finally:
        _delete_proveedor(pid)


def test_estadisticas_muelle_negativo_o_cero_excluido_de_n_validos(token_admin):
    """min <= 0 (aquí exactamente 0, ingreso y salida a la misma hora):
    dato corrupto/orden invertido, se excluye (contrato, sección 5)."""
    dia = "2029-03-05"
    pid = _insert_proveedor_edge(
        fecha=date.fromisoformat(dia),
        estado_confirmacion="confirmado",
        hora_ingreso=time(10, 0),
        hora_salida=time(10, 0),
        fecha_salida=None,
        placa_vehiculo="QA-UMBRAL-B-CERO",
    )
    try:
        resp = client.get(
            "/api/dashboard/estadisticas",
            params={"fecha_desde": dia, "fecha_hasta": dia},
            headers=_bearer(token_admin),
        )
        assert resp.status_code == 200, resp.text
        b = resp.json()["tiempo_muelle_proveedores"]
        assert b["global"]["n_validos"] == 0
    finally:
        _delete_proveedor(pid)


def test_estadisticas_ruta_mas_de_48h_excluido_de_n_validos(token_admin):
    """min > 2880 (48h): ningún viaje de flota propia entre CEDI y
    tiendas debería tomar más de 2 días -- se excluye (contrato,
    sección 5)."""
    d = date.fromisoformat("2029-03-10")
    fid = _insert_flota_edge(
        fecha=d, placa="QA-UMBRAL-D-72H",
        fecha_salida=d, hora_salida_cedi=time(0, 0),
        fecha_llegada=date.fromisoformat("2029-03-13"), hora_llegada=time(0, 0),  # 72h
    )
    try:
        resp = client.get(
            "/api/dashboard/estadisticas",
            params={"fecha_desde": d.isoformat(), "fecha_hasta": d.isoformat()},
            headers=_bearer(token_admin),
        )
        assert resp.status_code == 200, resp.text
        dd = resp.json()["tiempo_ruta_flota"]
        assert dd["global"] == {"promedio_minutos": None, "mediana_minutos": None, "n_validos": 0}
        assert dd["top_placas"] == []
    finally:
        _delete_flota(fid)


def test_estadisticas_ruta_negativa_excluida_de_n_validos(token_admin):
    """Llegada registrada antes que la salida (error de captura):
    min < 0 -> excluido (contrato, sección 5)."""
    d = date.fromisoformat("2029-03-15")
    fid = _insert_flota_edge(
        fecha=d, placa="QA-UMBRAL-D-NEG",
        fecha_salida=d, hora_salida_cedi=time(10, 0),
        fecha_llegada=d, hora_llegada=time(9, 0),
    )
    try:
        resp = client.get(
            "/api/dashboard/estadisticas",
            params={"fecha_desde": d.isoformat(), "fecha_hasta": d.isoformat()},
            headers=_bearer(token_admin),
        )
        assert resp.status_code == 200, resp.text
        dd = resp.json()["tiempo_ruta_flota"]
        assert dd["global"] == {"promedio_minutos": None, "mediana_minutos": None, "n_validos": 0}
        assert dd["top_placas"] == []
    finally:
        _delete_flota(fid)
