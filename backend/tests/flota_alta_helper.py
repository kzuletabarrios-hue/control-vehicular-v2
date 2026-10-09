"""Payload mínimo VÁLIDO para el alta de flota (POST /api/flota) tras exigir
los campos obligatorios del registro inicial. Los tests que solo necesitan un
alta exitosa lo usan para no repetir los campos.

Desde la migración 2026-10-08 el alta exige `conductor_id` (conductor activo
del maestro); `conductor_qa_id()` crea (una vez) un conductor de prueba."""
from sqlalchemy import text

from database import SessionLocal

QA_CEDULA = "9999990001"
QA_NOMBRE = "QA CONDUCTOR MAESTRO"


def _tienda_id() -> str:
    db = SessionLocal()
    row = db.execute(text("SELECT id FROM distribucion LIMIT 1")).fetchone()
    db.close()
    if not row:
        raise RuntimeError("El seed no trae tiendas en 'distribucion'")
    return str(row.id)


def conductor_qa_id() -> str:
    """Id de un conductor ACTIVO de prueba en el maestro (lo crea si falta)."""
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT id FROM conductores WHERE n_cedula = :c"), {"c": QA_CEDULA}
        ).fetchone()
        if row:
            db.execute(text("UPDATE conductores SET activo = TRUE WHERE id = :i"), {"i": row.id})
            db.commit()
            return str(row.id)
        row = db.execute(text("""
            INSERT INTO conductores (id, conductor, n_cedula, activo)
            VALUES (gen_random_uuid(), :n, :c, TRUE) RETURNING id
        """), {"n": QA_NOMBRE, "c": QA_CEDULA}).fetchone()
        db.commit()
        return str(row.id)
    finally:
        db.close()


def alta_ok(**extra) -> dict:
    base = {
        "conductor_id": conductor_qa_id(),
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
