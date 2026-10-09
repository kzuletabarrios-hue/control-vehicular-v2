# backend/utils_nombres.py
"""Normalización de nombres de personas para que el mismo conductor no quede
escrito de varias formas (mayúsculas/minúsculas, espacios dobles)."""
import re

_RE_ESPACIOS = re.compile(r"\s+")


def normalizar_nombre(raw):
    """'  juan   Pérez - cc 123 ' -> 'JUAN PÉREZ - CC 123'. None/vacío -> None."""
    if raw is None:
        return None
    texto = _RE_ESPACIOS.sub(" ", str(raw)).strip()
    return texto.upper() if texto else None
