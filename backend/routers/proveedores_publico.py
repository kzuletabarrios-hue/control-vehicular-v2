# backend/routers/proveedores_publico.py
# Endpoints PUBLICOS (sin autenticacion) para que el conductor de un
# proveedor se autorregistre al llegar, escaneando el QR de la porteria.
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.proveedores import (
    CAMPOS_VEHICULO, CAMPOS_ORDEN, _clean, _insert_ordenes,
    validar_token_ingreso_qr, crear_token_sesion_registro, validar_token_sesion_registro,
    fecha_valida, _extraer_numero_orden, _raise_error_insercion,
    SESION_REGISTRO_TTL_SEG,
)
from sqlalchemy.exc import IntegrityError, DataError

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))

CAMPOS_VEHICULO_PUBLICOS = [
    "placa_vehiculo", "nombre_conductor", "tipo_documento", "cedula_conductor",
    "telefono_conductor", "tipo_vehiculo", "hora_cita",
    "fecha_pago_arl", "epp_cumple", "tipo_carga", "formato_carga",
    "cantidad_pallets", "manejo_carga",
]
# Nota: muelle_descargue NO lo llena el conductor — el guarda lo asigna al
# confirmar el ingreso (ver PUT /api/proveedores/{id}).

_PLACA_RE = re.compile(r"^[A-Z]+[0-9]+$")
_ORDEN_RE = re.compile(r"^4\d{9}$")

TIPOS_DOCUMENTO = ("CC", "NIT", "Otro")
TIPOS_CARGA     = ("Seca", "Refrigerada", "Mixta")
FORMATOS_CARGA  = ("Paletizada", "Granel", "Mixta")
MANEJOS_CARGA   = ("Conductor con certificado de montacargas", "Reciservicios", "Ercol", "Operador logístico externo")


@router.get("/token-info")
def token_info(token: str):
    validar_token_ingreso_qr(token)
    # El QR ya cumplió su propósito (probar que se escaneó a tiempo); a partir de
    # aquí se usa un token de sesión de más duración para no caducar mientras el
    # conductor llena el formulario.
    return {"valido": True, "token_sesion": crear_token_sesion_registro()}


@router.get("/conductor-frecuente")
def conductor_frecuente(
    cedula: str,
    token: str,
    db: Session = Depends(get_db),
):
    # Requiere el token de sesion (ya escaneo un QR real) para no dejar este
    # lookup completamente abierto a cualquiera -- solo devuelve datos si
    # coincide exactamente con una cedula ya registrada antes.
    validar_token_sesion_registro(token)
    cedula = (cedula or "").strip()
    if not cedula:
        return {"encontrado": False}
    row = db.execute(text("""
        SELECT nombre_conductor, telefono, tipo_vehiculo, empresa_principal
        FROM conductores_frecuentes WHERE cedula = :c AND activo = TRUE
    """), {"c": cedula}).fetchone()
    if not row:
        return {"encontrado": False}
    return {
        "encontrado": True,
        "nombre_conductor": row.nombre_conductor,
        "telefono": row.telefono,
        "tipo_vehiculo": row.tipo_vehiculo,
        "empresa_principal": row.empresa_principal,
    }


def _buscar_cita_hoy(db: Session, numero_orden_compra) -> dict | None:
    """Busca la cita programada de HOY o AYER (fechas calculadas en el
    SERVIDOR con _BOG -- nunca se confía en una fecha que mande el cliente)
    para un número de orden de compra. Es la fuente de verdad tanto del
    lookup público (GET /citas/buscar, usado para la UX del formulario) como
    de POST /autorregistro (que la vuelve a consultar como autoridad real de
    seguridad): este flujo es público y sin autenticación, así que un POST
    directo sin pasar por el formulario debe ser rechazado igual que si
    hubiera pasado por el lookup. Mismo criterio de normalización que usa
    el guarda en GET /proveedores/citas/buscar (routers/proveedores.py).

    Incluye también `fecha = ayer` -- mismo motivo que el filtro
    `fecha IN (:hoy, :ayer)` de GET /citas/alertas (routers/citas.py): una
    franja que termina tarde en la noche más la tolerancia puede seguir
    vigente después de medianoche, y el conductor puede llegar y escanear
    el QR ya del lado de "hoy" en el reloj. Si por algún motivo hubiera dos
    filas candidatas para el mismo número de orden (una de hoy y otra de
    ayer -- no debería pasar en operación normal, cada orden pertenece a un
    único archivo/fecha del WMS), se prioriza la más reciente
    (ORDER BY fecha DESC) por ser la recarga más nueva del archivo.

    NO validar proximidad horaria aquí -- decisión de negocio 2026-08-06: ni
    el conductor ni el guarda deben bloquearse por estar fuera del rango de
    hora_cita_inicio/fin. Solo se alerta (GET /proveedores/citas/alertas),
    nunca se bloquea. Tampoco se filtra por `estado` aquí (a diferencia del
    _validar_orden de citas-muelles-cedi-r10): si la cita ya quedó 'usada'
    igual se devuelve el match y es el INSERT de más abajo (UNIQUE parcial
    idx_proveedores_ordenes_cita_id_unico) el que la rechaza con un mensaje
    de negocio claro -- ver _raise_error_insercion.

    Incluye `id` (citas_programadas.id) en el resultado -- POST /autorregistro
    lo usa para setear proveedores_ordenes.cita_id y así marcar que esta cita
    ya tiene una llegada registrada. No se expone `id` en la respuesta
    pública de GET /citas/buscar (ver buscar_cita_publico), solo se usa
    internamente."""
    numero = _extraer_numero_orden(numero_orden_compra)
    if not numero:
        return None
    ahora_dt = datetime.now(_BOG).replace(tzinfo=None)
    hoy = ahora_dt.date()
    ayer = hoy - timedelta(days=1)
    row = db.execute(
        text("""
            SELECT id, proveedor_nombre, hora_cita_inicio
            FROM citas_programadas
            WHERE fecha IN (:hoy, :ayer) AND numero_orden_compra = :numero
            ORDER BY fecha DESC
            LIMIT 1
        """),
        {"hoy": hoy.isoformat(), "ayer": ayer.isoformat(), "numero": numero},
    ).fetchone()
    if not row:
        return None
    r = dict(row._mapping)
    return {
        "id": r["id"],
        "proveedor_nombre": r["proveedor_nombre"],
        "hora_cita_inicio": str(r["hora_cita_inicio"])[:5] if r["hora_cita_inicio"] else None,
    }


@router.get("/citas/buscar")
def buscar_cita_publico(
    numero_orden_compra: str,
    token: str,
    db: Session = Depends(get_db),
):
    """Lookup público para el autocompletado del formulario del conductor.
    Protegido con el token de sesión de registro (mismo mecanismo que
    /conductor-frecuente) para no dejarlo completamente abierto a cualquiera.
    A diferencia del lookup del guarda (GET /proveedores/citas/buscar), aquí
    NO hay fallback manual: si no hay match el conductor no puede agregar esa
    orden -- ver reglas más estrictas en POST /autorregistro, que es la
    autoridad real (este GET es solo UX)."""
    validar_token_sesion_registro(token)
    cita = _buscar_cita_hoy(db, numero_orden_compra)
    if not cita:
        return {"encontrado": False}
    # No se expone `id` (uso interno de POST /autorregistro para cita_id).
    return {
        "encontrado": True,
        "proveedor_nombre": cita["proveedor_nombre"],
        "hora_cita_inicio": cita["hora_cita_inicio"],
    }


@router.post("/autorregistro", status_code=201)
def autorregistro(
    body: dict,
    db: Session = Depends(get_db),
):
    token = body.get("token")
    payload_sesion = validar_token_sesion_registro(token)

    vehiculo = body.get("vehiculo") or {}
    ordenes  = body.get("ordenes") or []

    placa       = (vehiculo.get("placa_vehiculo") or "").strip().upper()
    conductor   = (vehiculo.get("nombre_conductor") or "").strip()
    tipo_doc    = (vehiculo.get("tipo_documento") or "").strip()
    cedula      = (vehiculo.get("cedula_conductor") or "").strip()
    telefono    = (vehiculo.get("telefono_conductor") or "").strip()
    tipo_veh    = (vehiculo.get("tipo_vehiculo") or "").strip()
    fecha_arl   = (vehiculo.get("fecha_pago_arl") or "").strip()
    epp         = vehiculo.get("epp_cumple")
    tipo_carga  = (vehiculo.get("tipo_carga") or "").strip()
    formato_c   = (vehiculo.get("formato_carga") or "").strip()
    pallets     = (vehiculo.get("cantidad_pallets") or "").strip()
    manejo      = (vehiculo.get("manejo_carga") or "").strip()

    if not placa:
        raise HTTPException(400, "La placa es obligatoria")
    if not _PLACA_RE.match(placa):
        raise HTTPException(400, "La placa debe escribirse solo con letras seguidas de números, sin espacios ni caracteres especiales (ejemplo: ABC123)")
    if not conductor:
        raise HTTPException(400, "El nombre del conductor es obligatorio")
    if tipo_doc not in TIPOS_DOCUMENTO:
        raise HTTPException(400, "Selecciona el tipo de documento")
    if not cedula:
        raise HTTPException(400, "El número de documento es obligatorio")
    if not telefono:
        raise HTTPException(400, "El teléfono del conductor es obligatorio")
    if not tipo_veh:
        raise HTTPException(400, "El tipo de vehículo es obligatorio")
    if not fecha_arl:
        raise HTTPException(400, "La fecha de ARL es obligatoria")
    if not fecha_valida(fecha_arl):
        raise HTTPException(400, "La fecha de ARL no es válida")
    if epp is None or epp == "":
        raise HTTPException(400, "Indica si cuentas con los elementos de protección personal")
    if tipo_carga not in TIPOS_CARGA:
        raise HTTPException(400, "Selecciona el tipo de carga")
    if formato_c not in FORMATOS_CARGA:
        raise HTTPException(400, "Selecciona el formato de carga")
    if not pallets:
        raise HTTPException(400, "La cantidad de pallets es obligatoria")
    if manejo not in MANEJOS_CARGA:
        raise HTTPException(400, "Selecciona quién maneja la carga")
    if not ordenes:
        raise HTTPException(400, "Agrega al menos un proveedor/orden a la que vienes a entregar")

    # El proveedor NUNCA lo escribe el conductor a mano: para cada orden se
    # vuelve a buscar la cita de HOY en el servidor (defensa en profundidad
    # -- este endpoint es público y sin autenticación, un POST directo puede
    # saltarse el formulario y el lookup GET /citas/buscar por completo) y se
    # pisa `empresa` con el valor autoritativo de la BD, sin importar lo que
    # venga en el body. Si una orden no tiene cita registrada hoy se rechaza
    # toda la petición: a diferencia del guarda, aquí no hay fallback manual.
    hora_cita_autoritativa = None
    for o in ordenes:
        numero_oc = (o.get("numero_orden_compra") or "").strip()
        if not numero_oc:
            raise HTTPException(400, "Cada proveedor/orden debe tener número de orden de compra")
        if not _ORDEN_RE.match(numero_oc):
            raise HTTPException(400, f"El número de orden \"{numero_oc}\" debe empezar en 4 y tener 10 dígitos (ej. 4001234567)")
        cita = _buscar_cita_hoy(db, numero_oc)
        if not cita or not (cita.get("proveedor_nombre") or "").strip():
            raise HTTPException(
                400,
                f"La orden \"{numero_oc}\" no aparece en las citas programadas de hoy. "
                "Acércate a la caseta para que el guarda registre tu ingreso.",
            )
        o["empresa"] = cita["proveedor_nombre"]
        # Marca esta orden como "llegada registrada" para esta cita (ver
        # migración 2026-08-06_indice_proveedores_ordenes_cita_id.sql). El
        # UNIQUE parcial sobre proveedores_ordenes.cita_id se captura más
        # abajo, al insertar, por si dos autorregistros para la misma cita
        # llegan en carrera.
        o["cita_id"] = cita["id"]
        # hora_cita es un campo único a nivel de vehículo (no por orden): la
        # PRIMERA orden con match de la lista fija la hora autoritativa; si
        # una orden posterior trae una hora de cita distinta no se pisa (el
        # frontend solo la muestra como aviso informativo junto a esa orden).
        if hora_cita_autoritativa is None and cita.get("hora_cita_inicio"):
            hora_cita_autoritativa = cita["hora_cita_inicio"]

    ahora = datetime.now(_BOG)
    rid = str(uuid.uuid4())
    vals = {c: _clean(vehiculo.get(c)) for c in CAMPOS_VEHICULO if c in CAMPOS_VEHICULO_PUBLICOS}
    vals["id"] = rid
    vals["placa_vehiculo"] = placa
    vals["nombre_conductor"] = conductor
    # Autoritativo desde citas_programadas (ver loop de ordenes arriba) --
    # sobreescribe lo que haya mandado el cliente en vehiculo.hora_cita,
    # mismo criterio que con `empresa` en cada orden.
    vals["hora_cita"] = hora_cita_autoritativa
    vals["epp_cumple"] = bool(epp)
    vals["fecha"] = ahora.date().isoformat()
    vals["hora_ingreso"] = ahora.strftime("%H:%M:%S")
    vals["estado_confirmacion"] = "pendiente"
    vals["origen"] = "autorregistro"
    vals["creado_por"] = None
    # Métrica de UX (Alejandro/Jorge, 2026-08-25): cuánto tardó el conductor
    # en llenar el formulario, desde que escaneó el QR hasta este envío.
    # Se deriva del propio JWT de sesión de registro: su claim "exp" (epoch
    # UTC, PyJWT lo decodifica como número, no datetime) menos el TTL fijo
    # de la sesión reconstruye la hora exacta de emisión (= hora de escaneo).
    # Nunca debe tumbar el autorregistro: si el cálculo falla o da un valor
    # absurdo, se guarda NULL en vez de reventar la función (indicador
    # secundario, no crítico para el flujo).
    try:
        hora_inicio_sesion_epoch = payload_sesion["exp"] - SESION_REGISTRO_TTL_SEG
        ahora_epoch = datetime.now(timezone.utc).timestamp()
        duracion_segundos = round(ahora_epoch - hora_inicio_sesion_epoch)
        if duracion_segundos < 0:
            duracion_segundos = None
    except Exception:
        duracion_segundos = None
    vals["tiempo_autorregistro_segundos"] = duracion_segundos

    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    try:
        db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
        _insert_ordenes(db, rid, ordenes)
        # Fase 5.4: marca de una vez la(s) cita(s) como 'usada' en el momento
        # del autorregistro (hasta ahora eso solo ocurría cuando el guarda
        # confirmaba el ingreso -- PUT /proveedores/{id}/confirmar, Fase 5.3
        # -- lo que generaba falsas alertas de "vencida"/"por vencer" en
        # GET /citas/alertas mientras el registro seguía 'pendiente' de
        # confirmar). Mismo patrón exacto (subquery contra
        # proveedores_ordenes.cita_id + WHERE estado != 'usada') que usa
        # confirmar_autorregistro en routers/proveedores.py (línea ~1085) --
        # se deja igual a propósito para que ambos escritores de citas_programadas.estado
        # sean idempotentes entre sí y no se pisen: si esta escritura ya la dejó
        # en 'usada', el UPDATE de la confirmación del guarda es un no-op (y
        # viceversa, aunque en la práctica esta siempre corre primero).
        #
        # No hace falta iterar `ordenes` para armar un WHERE id IN (...) con
        # los cita_id: proveedores_ordenes ya tiene las filas recién insertadas
        # por _insert_ordenes (misma transacción), así que el subquery las ve.
        #
        # La defensa real contra la carrera de dos conductores autorregistrando
        # la MISMA orden casi al mismo tiempo no es este WHERE estado != 'usada'
        # (que aquí solo evita un UPDATE innecesario) -- es el UNIQUE parcial
        # idx_proveedores_ordenes_cita_id_unico sobre proveedores_ordenes.cita_id
        # que ya viola el INSERT de _insert_ordenes de arriba: el segundo
        # request nunca llega a ejecutar este UPDATE, revienta antes con
        # IntegrityError y cae al `except IntegrityError` de abajo, que
        # responde 409 con mensaje de negocio claro (_raise_error_insercion),
        # no un 500 crudo. Ambas protecciones son complementarias, no se
        # contradicen: una (UNIQUE) resuelve la concurrencia real a nivel de
        # inserción; la otra (estado != 'usada') solo hace idempotente el
        # UPDATE en cascada frente al otro escritor (el guarda).
        db.execute(text("""
            UPDATE citas_programadas
            SET estado = 'usada', updated_at = NOW()
            WHERE id IN (
                SELECT cita_id FROM proveedores_ordenes
                WHERE proveedor_id = :id AND cita_id IS NOT NULL
            )
            AND estado != 'usada'
        """), {"id": rid})
        db.commit()
    except IntegrityError as e:
        _raise_error_insercion(db, e)
    except DataError:
        db.rollback()
        raise HTTPException(400, "Datos inválidos: revisa los campos e intenta de nuevo.")

    # Guarda/actualiza el catálogo de conductores frecuentes para que la próxima
    # vez que este conductor escanee el QR, el formulario se le autocomplete solo.
    try:
        db.execute(text("""
            INSERT INTO conductores_frecuentes
                (id, cedula, nombre_conductor, telefono, tipo_vehiculo, activo, ultima_visita)
            VALUES (:id, :cedula, :nombre, :telefono, :tipo, TRUE, :fecha)
            ON CONFLICT (cedula) DO UPDATE SET
                nombre_conductor = EXCLUDED.nombre_conductor,
                telefono         = COALESCE(EXCLUDED.telefono, conductores_frecuentes.telefono),
                tipo_vehiculo    = COALESCE(EXCLUDED.tipo_vehiculo, conductores_frecuentes.tipo_vehiculo),
                activo           = TRUE,
                ultima_visita    = EXCLUDED.ultima_visita,
                updated_at       = NOW()
        """), {
            "id": str(uuid.uuid4()), "cedula": cedula, "nombre": conductor,
            "telefono": telefono, "tipo": tipo_veh, "fecha": ahora.date().isoformat(),
        })
        db.commit()
    except Exception:
        db.rollback()  # no dejar que un problema aca invalide el registro ya guardado

    return {"id": rid, "message": "Registro enviado. El guarda confirmará tu ingreso en un momento."}
