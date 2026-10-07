"""Payload mínimo VÁLIDO para el alta de flota (POST /api/flota) tras exigir
los campos obligatorios del registro inicial. Los tests que solo necesitan un
alta exitosa lo usan para no repetir los campos."""
from sqlalchemy import text

from database import SessionLocal


def _tienda_id() -> str:
    db = SessionLocal()
    row = db.execute(text("SELECT id FROM distribucion LIMIT 1")).fetchone()
    db.close()
    if not row:
        raise RuntimeError("El seed no trae tiendas en 'distribucion'")
    return str(row.id)


def alta_ok(**extra) -> dict:
    base = {
        "muelle_cargue": "7",
        "n_pallets": 0,
        "n_contenedores": 0,
        "cant_volumen_externo": "N/A",
        "tienda_1": _tienda_id(),
        "protocolo": "N/A",
        "observacion": "N/A",
    }
    base.update(extra)
    return base
