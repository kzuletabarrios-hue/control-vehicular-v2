# backend/routers/citas.py
#
# Fase 3 (solo lectura) + Fase 5.2 (primera escritura autorizada) del plan
# de consolidación con citas-muelles-cedi-r10. control-vehicular-v2 YA tiene
# capacidad de carga del archivo del WMS (POST /proveedores/citas/importar,
# ver routers/proveedores.py) desde antes de este módulo, y desde Fase 5.2
# también expone aquí PUT /config para editar la tolerancia -- este router
# deja de ser exclusivamente de lectura. control-vehicular-v2 va camino a
# ser el ÚNICO escritor de citas_programadas/configuracion (auditoría de
# colisiones reales entre las dos apps, 2026-08-07); citas-muelles-cedi-r10
# sigue activa por ahora y conserva sus propios POST /citas/cargar y
# PUT /citas/config, que se desactivan en una fase posterior, después de
# validar que este importador y este endpoint funcionan igual en producción.
#
# Lógica de alertas() copiada literal de la de referencia en
# C:\citas-muelles-cedi-r10\backend\routers\citas.py -- incluyendo el
# cálculo con datetime.combine(fecha, hora) y el filtro fecha IN (hoy, ayer),
# que corrige un bug histórico con franjas que cruzan medianoche al sumar la
# tolerancia. No se cambia ni una línea de esa fórmula: ambas apps leen la
# misma tabla citas_programadas y deben mostrar los mismos conteos.
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))
ALERTA_VENCE_MIN  = 10  # aviso cuando falten <=10 min para el fin de la franja (+tolerancia)
ALERTA_INICIO_MIN = 5   # aviso cuando falten <=5 min para que empiece la hora de la cita


def _fin_con_tolerancia(fecha, hora_cita_fin, tolerancia_min):
    """Datetime completo (fecha+hora) del fin de la franja + tolerancia.
    datetime.combine (no .time() sueltas) para que la comparación no se
    rompa cuando franja+tolerancia cruza medianoche -- misma fórmula que
    usaba alertas() antes de extraerse aquí, no se cambia ni una línea."""
    return datetime.combine(fecha, hora_cita_fin) + timedelta(minutes=tolerancia_min or 0)


def cita_vencida(fecha, hora_cita_fin, tolerancia_min, ahora_dt) -> bool:
    """¿Ya pasó hora_cita_fin + tolerancia_min? Único punto donde vive
    este criterio -- lo usan alertas() (abajo) y GET /export/citas
    (routers/export.py, columna calculada 'Vencida'). `ahora_dt` se
    recibe como parámetro (no se calcula internamente) para que quien
    procese muchas filas en un loop lo calcule una sola vez."""
    return ahora_dt > _fin_con_tolerancia(fecha, hora_cita_fin, tolerancia_min)


def _tolerancia_default(db) -> int:
    row = db.execute(text("SELECT valor FROM configuracion WHERE clave = 'tolerancia_min_default'")).fetchone()
    try:
        return int(row.valor) if row else 30
    except (TypeError, ValueError):
        return 30


@router.get("/config")
def obtener_config(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    return {"tolerancia_min_default": _tolerancia_default(db)}


@router.put("/config")
def actualizar_config(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permiso("citas", "write")),
):
    """Mismo contrato que PUT /citas/config del sistema original
    (citas-muelles-cedi-r10/backend/routers/citas.py) -- primer endpoint de
    ESCRITURA de este router (autorizado explícitamente en Fase 5.2, ver
    comentario de cabecera del módulo).

    `configuracion` es una tabla clave-valor genérica sin trigger que
    refresque `updated_at` (confirmado por Jorge, 2026-08-07) y sin CHECK de
    formato sobre `valor` (TEXT libre) -- por eso updated_at/updated_por se
    setean a mano en la sentencia, y la validación de rango (0-240 minutos)
    es responsabilidad exclusiva de este endpoint, no del esquema.

    Sobre el permiso "citas":"write": verificado hoy contra la tabla
    `roles` real (SELECT nombre, permisos->'citas' FROM roles) -- SOLO
    `admin` y `coordinador` lo tienen hoy. `coordinador` está en
    ROLES_SOLO_LECTURA_EN_ESTA_APP (ver routers/auth.py): su token se
    'clampea' a solo ["read"] dentro de control-vehicular-v2 aunque la fila
    compartida de `roles` diga "write" (necesario para no quitarle
    escritura en la app hermana, donde sí opera con ese permiso). En la
    práctica, hoy en control-vehicular-v2 SOLO el rol `admin` puede llamar
    este endpoint con éxito -- el resto de roles recibe 403. No se asume
    resuelto ni se cambia `roles` aquí: si Karen quiere que otro rol
    (ej. guarda_bodega/supervisor) pueda ajustar la tolerancia, es una
    decisión de negocio pendiente, no una omisión de este código.
    """
    tolerancia = body.get("tolerancia_min_default")
    try:
        tolerancia = int(tolerancia)
    except (TypeError, ValueError):
        raise HTTPException(400, "La tolerancia debe ser un número de minutos")
    if tolerancia < 0 or tolerancia > 240:
        raise HTTPException(400, "La tolerancia debe estar entre 0 y 240 minutos")

    db.execute(text("""
        INSERT INTO configuracion (clave, valor, updated_at, updated_por)
        VALUES ('tolerancia_min_default', :v, NOW(), :uid)
        ON CONFLICT (clave) DO UPDATE SET valor = :v, updated_at = NOW(), updated_por = :uid
    """), {"v": str(tolerancia), "uid": current_user["id"]})
    db.commit()
    return {"tolerancia_min_default": tolerancia}


@router.get("")
def listar(
    fecha: str = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    where = "WHERE fecha = :fecha" if fecha else ""
    params = {"fecha": fecha} if fecha else {}
    rows = db.execute(
        text(f"SELECT * FROM citas_programadas {where} ORDER BY hora_cita_inicio ASC"), params
    ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/alertas")
def alertas(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("citas", "read")),
):
    """Calculado en vivo en cada consulta -- nunca se persiste 'vencida' en
    citas_programadas.estado, así que esto nunca queda desincronizado de la
    hora real (mismo criterio que "por vencer" en el tablero de muelles)."""
    ahora_dt = datetime.now(_BOG).replace(tzinfo=None)
    hoy = ahora_dt.date()
    ayer = hoy - timedelta(days=1)

    archivo = db.execute(text("""
        SELECT created_at FROM archivos_citas WHERE fecha = :hoy ORDER BY created_at DESC LIMIT 1
    """), {"hoy": hoy.isoformat()}).fetchone()

    # Incluye también las de ayer: una franja que terminaba tarde en la noche
    # más la tolerancia puede seguir vigente después de medianoche.
    rows = db.execute(text("""
        SELECT numero_orden_compra, proveedor_nombre, hora_cita_inicio, hora_cita_fin, tolerancia_min, fecha
        FROM citas_programadas WHERE fecha IN (:hoy, :ayer) AND estado = 'pendiente'
        ORDER BY hora_cita_fin ASC
    """), {"hoy": hoy.isoformat(), "ayer": ayer.isoformat()}).fetchall()

    por_vencer, vencidas, por_iniciar = [], [], []
    for r in rows:
        # datetime completo (fecha+hora), no solo .time(): comparar horas
        # sueltas rompe cuando la franja+tolerancia cruza la medianoche.
        inicio_dt = datetime.combine(r.fecha, r.hora_cita_inicio)
        fin_dt = _fin_con_tolerancia(r.fecha, r.hora_cita_fin, r.tolerancia_min)
        item = {
            "numero_orden_compra": r.numero_orden_compra,
            "proveedor_nombre": r.proveedor_nombre,
            "hora_cita_inicio": r.hora_cita_inicio.strftime("%H:%M"),
            "hora_cita_fin": r.hora_cita_fin.strftime("%H:%M"),
        }
        if ahora_dt > fin_dt:
            vencidas.append(item)
        elif (fin_dt - ahora_dt).total_seconds() <= ALERTA_VENCE_MIN * 60:
            por_vencer.append(item)
        if ahora_dt <= inicio_dt and (inicio_dt - ahora_dt).total_seconds() <= ALERTA_INICIO_MIN * 60:
            por_iniciar.append(item)

    return {
        "archivo_hoy": archivo is not None,
        "hora_carga": archivo.created_at.isoformat() if archivo else None,
        "por_vencer": por_vencer,
        "vencidas": vencidas,
        "por_iniciar": por_iniciar,
    }
