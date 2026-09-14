"""Smoke test de entorno: confirma que la suite quedó conectada a la
base de datos LOCAL de pruebas (nunca producción) y que el guardrail
de conftest.py realmente actuó antes de llegar hasta acá."""
import os

from conftest import _PRODUCTION_MARKERS


def test_database_url_no_apunta_a_produccion():
    database_url = os.getenv("DATABASE_URL", "")
    assert database_url, "DATABASE_URL debería venir seteada por backend/.env.test"
    lowered = database_url.lower()
    for marker in _PRODUCTION_MARKERS:
        assert marker.lower() not in lowered, (
            f"DATABASE_URL contiene una huella de producción ({marker}); "
            "el guardrail de conftest.py debió haber abortado la sesión "
            "antes de llegar a este test."
        )


def test_database_url_apunta_al_postgres_local_de_pruebas():
    database_url = os.getenv("DATABASE_URL", "")
    assert "127.0.0.1" in database_url or "localhost" in database_url, (
        "Se esperaba un host local (127.0.0.1/localhost) para la BD de "
        "pruebas. Revisa backend/.env.test."
    )
