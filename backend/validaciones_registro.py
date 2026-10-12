# backend/validaciones_registro.py
"""Helpers compartidos para validar altas/ediciones de registros operativos
(control_acceso, visitantes). Extraídos de routers/control_acceso.py sin
cambiar su comportamiento."""
import re
from datetime import date, timedelta, timezone

from fastapi import HTTPException

# Misma zona horaria fija que usan dashboard.py, export.py y /api/tiempo
# (Bogotá = UTC-5, sin DST).
BOG = timezone(timedelta(hours=-5))
_RE_HORA = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?")


def validar_texto_obligatorio(valor, mensaje: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise HTTPException(400, mensaje)
    return valor.strip()


def validar_fecha(valor, campo: str):
    """None/'' -> None. Formato YYYY-MM-DD o 400."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str) and len(valor) == 10:
        try:
            date.fromisoformat(valor)
            return valor
        except ValueError:
            pass
    raise HTTPException(400, f"{campo}: fecha inválida, use el formato AAAA-MM-DD")


def validar_hora(valor, campo: str):
    """None/'' -> None. Formato HH:MM o HH:MM:SS o 400."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str) and _RE_HORA.fullmatch(valor):
        return valor
    raise HTTPException(400, f"{campo}: hora inválida, use el formato HH:MM")
