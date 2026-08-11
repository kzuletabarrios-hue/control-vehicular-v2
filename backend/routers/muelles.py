# backend/routers/muelles.py
#
# Fase 2 (solo lectura) del plan de consolidación con citas-muelles-cedi-r10.
# Decisión del arquitecto: este router expone ÚNICAMENTE el tablero de
# muelles en modo lectura. NO se agrega crear/asignar/liberar aquí -- los
# roles que hoy hacen esas operaciones (guarda_bodega, guarda_peatonal,
# guarda_vehicular) no existen todavía en este backend, y escribir sobre
# muelles/muelle_eventos desde dos apps distintas abriría una segunda vía
# de modificar el mismo estado operativo que ya gestiona citas-muelles-
# cedi-r10 en producción. Esa fase queda pendiente y explícita a futuro.
#
# ── CAMBIO TEMPORAL DE FUENTE DE DATOS (2026-08-07, decisión de Alejandro) ──
# muelles/muelle_eventos están vacías en producción -- nadie las usa
# operativamente todavía. proveedores.muelle_descargue (texto libre,
# diligenciado hoy por los guardas) SÍ tiene datos reales, y es la misma
# fuente que ya usa dashboard.py para derivar "en_muelle" con éxito.
# Mientras muelles/muelle_eventos no tengan uso operativo real, este
# endpoint deriva el tablero de proveedores.muelle_descargue en su lugar.
#
# TODO: revertir a esto cuando esas tablas tengan uso operativo real:
#
# from datetime import datetime, timedelta, timezone
# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from sqlalchemy import text
# from database import get_db
# from routers.auth import require_permiso
#
# router = APIRouter()
# _BOG = timezone(timedelta(hours=-5))
# ALERTA_MUELLE_MIN = 120  # ajustado por Karen (2026-08-07): 2h, antes 90 min
#
# @router.get("")
# def tablero(
#     db: Session = Depends(get_db),
#     _: dict = Depends(require_permiso("muelles", "read")),
# ):
#     rows = db.execute(text("""
#         SELECT
#             m.id, m.numero, m.zona, m.tipo_carga_habitual,
#             e.id AS evento_id, e.hora_asignado,
#             p.id AS proveedor_id, p.placa_vehiculo, p.nombre_conductor, p.tipo_carga,
#             (SELECT string_agg(
#                 po.empresa || CASE WHEN po.numero_orden_compra IS NOT NULL THEN ' (OC ' || po.numero_orden_compra || ')' ELSE '' END,
#                 ' · '
#             ) FROM proveedores_ordenes po WHERE po.proveedor_id = p.id) AS empresas
#         FROM muelles m
#         LEFT JOIN muelle_eventos e ON e.muelle_id = m.id AND e.hora_liberado IS NULL
#         LEFT JOIN proveedores p ON p.id = e.proveedor_id
#         WHERE m.activo = TRUE
#         ORDER BY m.numero
#     """)).fetchall()
#
#     ahora = datetime.now(_BOG)
#     items = []
#     for r in rows:
#         d = dict(r._mapping)
#         d["estado"] = "ocupado" if d["evento_id"] else "libre"
#         if d["evento_id"]:
#             minutos = int((ahora - d["hora_asignado"]).total_seconds() // 60)
#             d["minutos_ocupado"] = minutos
#             d["alerta_tiempo"] = minutos >= ALERTA_MUELLE_MIN
#         items.append(d)
#     return items

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))
ALERTA_MUELLE_MIN = 120  # ajustado por Karen: 2 horas (antes 90 min / citas-muelles-cedi-r10 sigue en 90)

# Universo fijo de muelles 1-18. De muelle_descargue (texto libre) solo se
# puede derivar quién está ocupando un muelle, nunca quién está libre --
# sin esta lista fija no habría forma de mostrar "libre" en el tablero.
MUELLES_NUMEROS = list(range(1, 19))

# TODO: retirar este mapeo y volver al JOIN contra
# muelles.tipo_carga_habitual en cuanto esa tabla tenga datos operativos
# reales (hoy está vacía, el JOIN devolvería NULL siempre). Rango exacto
# portado de MUELLES_HABITUALES en frontend/index.html (~línea 2934).
MUELLES_HABITUALES = {"Refrigerada": (1, 6), "Seca": (13, 18)}


def _tipo_carga_habitual(numero: int):
    for tipo, (desde, hasta) in MUELLES_HABITUALES.items():
        if desde <= numero <= hasta:
            return tipo
    return None


# Mismo criterio que normalizarMuelle en frontend/index.html (~línea 615):
# extrae el primer número de un texto libre ("Muelle 7", "7", " 07 "),
# descarta si no hay ninguno.
def _normalizar_muelle(valor):
    if valor is None or valor == "":
        return None
    m = re.search(r"\d+", str(valor))
    if not m:
        return None
    return int(m.group(0))


@router.get("")
def tablero(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("muelles", "read")),
):
    # Mismo criterio exacto que backend/routers/dashboard.py (~líneas 85-93)
    # para "en_muelle" -- Muelles e Inicio nunca deben contradecirse sobre
    # si un vehículo está o no en muelle.
    #
    # Columnas adicionales (hora_cita, hora_wps, hora_ingreso_confirmado,
    # hora_muelle_liberado, muelle_numero): línea de tiempo completa que
    # consume el frontend (mismo patrón que DetalleTiempos en Proveedores,
    # frontend ~línea 784-793). Se leen con nombres explícitos (no SELECT
    # p.*) para no arrastrar columnas que el panel no necesita.
    # "empresas" se arma en dos niveles (pedido de Karen: mostrar la OC junto
    # a la empresa, solo en este tablero -- Proveedores y Dashboard no se
    # tocan). numero_orden_compra es texto libre digitado por el guarda sin
    # CHECK ni UNIQUE: un mismo proveedor puede tener varias filas de la
    # misma empresa, unas con OC y otras sin ella (olvido de digitación). Si
    # se concatenara "empresa (OC ...)" fila por fila y se aplicara DISTINCT
    # sobre ese string ya armado, una fila sin OC generaría una entrada
    # fantasma duplicada para una empresa que ya tiene OC en otra fila
    # ("ACME (OC 123), ACME"). Por eso se agrupa primero por empresa (sub-
    # consulta correlacionada a p.id) armando ahí las OCs distintas y no
    # nulas/vacías de esa empresa, y solo en el nivel externo se unen las
    # empresas entre sí. Empresa sin ninguna OC capturada -> se muestra solo
    # el nombre, sin paréntesis (igual que antes). Reemplaza el LEFT JOIN
    # proveedores_ordenes anterior (solo se usaba para esta columna), lo que
    # también simplifica el GROUP BY de p.* a nada.
    rows = db.execute(text("""
        SELECT p.id, p.placa_vehiculo, p.nombre_conductor, p.muelle_descargue,
               p.hora_ingreso, p.tipo_carga,
               p.hora_cita, p.hora_wps, p.hora_ingreso_confirmado,
               p.hora_muelle_liberado, p.muelle_numero,
               (
                   SELECT string_agg(
                       CASE WHEN emp.ocs IS NULL THEN emp.empresa
                            ELSE emp.empresa || ' (' || emp.ocs || ')'
                       END,
                       ', ' ORDER BY emp.empresa
                   )
                   FROM (
                       SELECT po.empresa,
                              string_agg(
                                  DISTINCT 'OC ' || NULLIF(po.numero_orden_compra, ''),
                                  ', ' ORDER BY 'OC ' || NULLIF(po.numero_orden_compra, '')
                              ) AS ocs
                       FROM proveedores_ordenes po
                       WHERE po.proveedor_id = p.id
                       GROUP BY po.empresa
                   ) emp
               ) AS empresas
        FROM proveedores p
        WHERE p.estado_confirmacion = 'confirmado' AND p.hora_salida IS NULL
        ORDER BY p.hora_ingreso ASC
    """)).fetchall()

    # Un solo ocupante por número de muelle. Si dos registros distintos
    # normalizan al mismo número (colisión/typo del guarda), se queda con
    # el de hora_ingreso más antiguo (ya viene ordenado ASC) y se descarta
    # el resto en silencio -- no bloquea nada.
    ocupantes = {}
    for r in rows:
        numero = _normalizar_muelle(r.muelle_descargue)
        if numero is None or numero in ocupantes:
            continue
        ocupantes[numero] = r

    ahora = datetime.now(_BOG)
    hoy = ahora.date()

    items = []
    for numero in MUELLES_NUMEROS:
        r = ocupantes.get(numero)
        item = {
            "id": str(numero),
            "numero": numero,
            "zona": None,
            "tipo_carga_habitual": _tipo_carga_habitual(numero),
            "estado": "ocupado" if r is not None else "libre",
            "placa_vehiculo": None,
            "nombre_conductor": None,
            "empresas": None,
            "tipo_carga": None,
            # Línea de tiempo completa (mismo orden que DetalleTiempos en
            # Proveedores, frontend ~línea 784-793): cita, WPS, ingreso
            # confirmado, salida de muelle. hora_ingreso ya viaja arriba
            # (placa_vehiculo, etc. van sueltos por compat). No se incluye
            # "Llegada al muelle" como paso propio: en la operación real no
            # se captura como evento distinto de "ingreso confirmado".
            "hora_cita": None,
            # hora_ingreso: ya se leía en el SELECT de arriba pero no viajaba
            # en el payload -- lo necesita la línea de tiempo del panel de
            # detalle en frontend (MuelleDetallePanel, paso "Llegada/portería",
            # mismo campo que ya consume DetalleTiempos en Proveedores).
            "hora_ingreso": None,
            "hora_wps": None,
            "hora_ingreso_confirmado": None,
            "hora_muelle_liberado": None,
            "muelle_numero": None,
            "minutos_ocupado": None,
            "alerta_tiempo": False,
        }
        if r is not None:
            item["placa_vehiculo"] = r.placa_vehiculo
            item["nombre_conductor"] = r.nombre_conductor
            item["empresas"] = r.empresas
            item["tipo_carga"] = r.tipo_carga
            item["hora_cita"] = r.hora_cita
            item["hora_ingreso"] = r.hora_ingreso
            item["hora_wps"] = r.hora_wps
            item["hora_ingreso_confirmado"] = r.hora_ingreso_confirmado
            item["hora_muelle_liberado"] = r.hora_muelle_liberado
            item["muelle_numero"] = r.muelle_numero
            # Base del cálculo de "tiempo excedido": el momento en que el
            # guarda vehicular confirma el ingreso (hora_ingreso_confirmado),
            # no la llegada a portería (hora_ingreso) ni una asignación de
            # muelle -- en la operación real no hay un evento distinto que
            # marque "llegada al muelle". Fallback a hora_ingreso como red de
            # seguridad para filas legacy; en la práctica todo registro con
            # estado_confirmacion = 'confirmado' (único filtro del SELECT de
            # arriba) debería traer hora_ingreso_confirmado poblada. Resuelto
            # en Python (no COALESCE en SQL) porque el ajuste de "cruce de
            # medianoche" de abajo ya vive aquí y aplica igual a cualquiera
            # de las dos columnas (ambas son TIME sin fecha).
            base_hora = r.hora_ingreso_confirmado or r.hora_ingreso
            if base_hora is not None:
                # TIME sin fecha -- se combina con la fecha de hoy en zona
                # Bogotá para calcular el tiempo transcurrido.
                base_dt = datetime.combine(hoy, base_hora, tzinfo=_BOG)
                minutos = int((ahora - base_dt).total_seconds() // 60)
                if minutos < 0:
                    # Cruce de medianoche (hora registrada el día anterior
                    # con el mismo campo TIME) -- no se puede saber cuántos
                    # días exactos pasaron, se evita mostrar un negativo.
                    minutos = 0
                item["minutos_ocupado"] = minutos
                item["alerta_tiempo"] = minutos >= ALERTA_MUELLE_MIN
        items.append(item)

    return items
