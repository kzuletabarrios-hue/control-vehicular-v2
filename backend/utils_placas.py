# backend/utils_placas.py
"""Normalización de placas, compartida por backend/routers/flota.py
(flota propia, texto libre históricamente mal digitado) y
backend/routers/bd_maestros.py (alta/edición del maestro `vehiculos`).

Regla única (decisión de la usuaria 2026-10-02, tras la limpieza de
placas mal digitadas en producción): mayúsculas, sin espacios ni
guiones. Se usa ANTES de guardar (INSERT/UPDATE) y antes de comparar
contra el maestro, para que 'abc-123', ' ABC 123 ' y 'ABC123' sean
siempre la misma placa.
"""
import re

_RE_ESPACIOS_GUIONES = re.compile(r"[\s\-]+")


def normalizar_placa(raw) -> str | None:
    """Normaliza una placa a mayúsculas, sin espacios ni guiones.

    None/''/solo-espacios -> None (no se inventa una placa vacía).
    No valida formato (largo, letras/números): la decisión de la
    usuaria es NUNCA bloquear el guardado por una placa fuera de
    formato o fuera del maestro, solo marcarla para revisión
    (ver placa_no_verificada en flota.py)."""
    if raw is None:
        return None
    texto = str(raw).strip()
    if not texto:
        return None
    return _RE_ESPACIOS_GUIONES.sub("", texto).upper()
