"""
Guardrail de seguridad para toda la suite de tests de backend.

Objetivo único de este archivo: hacer IMPOSIBLE que `pytest` corra
contra la base de datos real de producción (Supabase del CEDI), sea
por accidente, por un .env mal configurado o porque alguien copió
backend/.env.test y le pegó encima el DATABASE_URL de producción.

Cómo funciona:
1. Al recolectar tests, se carga backend/.env.test (si existe) con
   override=True -- esto gana sobre cualquier DATABASE_URL que ya
   esté en el entorno del shell, y gana sobre backend/.env porque
   database.py llama a load_dotenv() SIN override (por eso el orden
   de carga importa: este archivo se importa antes que cualquier
   módulo de la app).
2. Se valida el DATABASE_URL resultante contra un listado de
   "huellas" inequívocas de producción (host del pooler de Supabase y
   el project ref real). Si coincide con cualquiera, se aborta TODA
   la sesión de pytest con pytest.exit() -- no se marca un test como
   failed, se detiene la recolección completa, código de salida != 0.
3. Un fixture autouse de sesión repite la misma validación al inicio
   de la sesión de tests, como defensa en profundidad por si algo
   reconfigura el entorno entre la carga de conftest.py y la
   ejecución de los tests.

Si hoy no hay tests todavía, este archivo queda como base lista para
cuando se escriban -- no depende de que exista ningún test real.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv
except ImportError as exc:  # pragma: no cover - dependencia esperada
    raise RuntimeError(
        "python-dotenv no está instalado. Instala las dependencias de "
        "desarrollo con: pip install -r backend/requirements-dev.txt"
    ) from exc

BACKEND_DIR = Path(__file__).resolve().parent
ENV_TEST_PATH = BACKEND_DIR / ".env.test"

# Huellas inequívocas de la base de datos de PRODUCCIÓN real (CEDI).
# Cualquiera de las dos, encontrada en DATABASE_URL (case-insensitive,
# substring), bloquea la sesión completa de tests.
_PRODUCTION_MARKERS = (
    "aws-1-sa-east-1.pooler.supabase.com",  # host del connection pooler
    "vhzxtgrpnztwntoqhfaf",                  # project ref de Supabase
)


def _load_test_env() -> None:
    """Carga backend/.env.test ANTES que nada más pueda fijar
    DATABASE_URL a producción -- así, cuando database.py haga su propio
    load_dotenv() (sin override) para leer backend/.env de producción,
    ya no pisa nada porque DATABASE_URL ya está seteada.

    override=False a propósito: si quien corre pytest ya trae
    DATABASE_URL explícita en el entorno/shell/CI (por ejemplo, para
    verificar este mismo guardrail, o por una variable de CI mal
    configurada), esa variable manda y ES la que se valida más abajo.
    .env.test solo actúa como default seguro cuando no hay nada más
    seteado -- nunca oculta un DATABASE_URL explícito, ni bueno ni
    malo."""
    if ENV_TEST_PATH.exists():
        load_dotenv(ENV_TEST_PATH, override=False)


def assert_not_production_database(database_url: str | None) -> None:
    """Lanza un error duro (no un simple assert) si `database_url`
    resuelve a producción, o si no está definida en absoluto. Se deja
    como función reutilizable (no solo uso interno de este archivo)
    para que fixtures futuras de conexión a BD puedan llamarla también
    justo antes de abrir cualquier conexión real."""
    if not database_url:
        pytest.exit(
            "DATABASE_URL no está definida. No se puede correr la suite de "
            "tests sin apuntar explícitamente a una base de datos LOCAL de "
            "pruebas. Copia/revisa backend/.env.test y volvé a intentar. "
            "Abortando por seguridad -- NUNCA se debe asumir un default.",
            returncode=1,
        )
        return  # pragma: no cover - pytest.exit no retorna, esto es defensivo

    lowered = database_url.lower()
    for marker in _PRODUCTION_MARKERS:
        if marker.lower() in lowered:
            pytest.exit(
                "BLOQUEADO POR SEGURIDAD: DATABASE_URL apunta a un host o "
                f"proyecto de PRODUCCIÓN real (coincide con «{marker}»). "
                "Los tests NUNCA deben correr contra los datos reales del "
                "CEDI. Revisa backend/.env.test (debe apuntar a "
                "127.0.0.1, puerto del Postgres local de pruebas) y la "
                "variable DATABASE_URL de tu entorno/shell -- alguna de las "
                "dos está mal configurada.",
                returncode=1,
            )


# Se ejecuta al importar este conftest.py, es decir, ANTES de que pytest
# recolecte o importe cualquier módulo de test (y antes de que cualquier
# módulo de test pueda importar backend/database.py).
_load_test_env()
assert_not_production_database(os.getenv("DATABASE_URL"))


@pytest.fixture(scope="session", autouse=True)
def _guardrail_no_produccion() -> None:
    """Defensa en profundidad: repite la validación al arrancar la
    sesión de tests, en caso de que algo (otro plugin, un fixture con
    autouse de mayor prioridad, una variable de entorno seteada tarde)
    haya alterado DATABASE_URL entre la carga de este archivo y el
    arranque real de la sesión."""
    assert_not_production_database(os.getenv("DATABASE_URL"))
