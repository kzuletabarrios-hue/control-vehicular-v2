# backend/routers/proveedores_publico.py
# Endpoints PUBLICOS (sin autenticacion) para que el conductor de un
# proveedor se autorregistre al llegar, escaneando el QR de la porteria.
import json
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
    fecha_valida,
)
from routers.citas import _ORDEN_RE
from sqlalchemy.exc import IntegrityError, DataError

router = APIRouter()

_BOG = timezone(timedelta(hours=-5))


def _validar_orden(db: Session, numero: str) -> dict:
    """Valida un número de orden contra el archivo de citas cargado por el
    coordinador. Devuelve {"valido": True, ...datos de la cita} o
    {"valido": False, "motivo": "..."}.
    """
    numero = (numero or "").strip()
    if not _ORDEN_RE.match(numero):
        return {"valido": False, "motivo": "El número de orden debe empezar en 4 y tener 10 dígitos"}

    row = db.execute(text("""
        SELECT id, fecha, proveedor_nombre, hora_cita_inicio, hora_cita_fin, tolerancia_min, estado
        FROM citas_programadas WHERE numero_orden_compra = :n
    """), {"n": numero}).fetchone()

    if not row:
        return {"valido": False, "motivo": "Orden no encontrada. Verifica que logística haya cargado el archivo de hoy."}

    hoy = datetime.now(_BOG).date()
    if row.fecha != hoy:
        return {"valido": False, "motivo": f"Esta orden no es de hoy (es del {row.fecha.strftime('%d/%m/%Y')})"}

    if row.estado == "usada":
        return {"valido": False, "motivo": "Esta orden ya fue utilizada para un ingreso"}
    if row.estado == "cancelada":
        return {"valido": False, "motivo": "Esta orden fue cancelada"}

    ahora = datetime.now(_BOG).time()
    tol = timedelta(minutes=row.tolerancia_min or 0)
    ini = (datetime.combine(hoy, row.hora_cita_inicio) - tol).time()
    fin = (datetime.combine(hoy, row.hora_cita_fin) + tol).time()
    if not (ini <= ahora <= fin):
        return {
            "valido": False,
            "motivo": f"Fuera del horario permitido — tu cita era {row.hora_cita_inicio.strftime('%H:%M')}–{row.hora_cita_fin.strftime('%H:%M')}",
        }

    return {
        "valido": True,
        "cita_id": str(row.id),
        "proveedor_nombre": row.proveedor_nombre or "",
        "hora_cita_inicio": row.hora_cita_inicio.strftime("%H:%M"),
        "hora_cita_fin": row.hora_cita_fin.strftime("%H:%M"),
    }


def _audit_publico(db, accion, rid, datos_despues):
    # Sin usuario autenticado (endpoint público) -- usuario_id/email quedan
    # NULL, pero igual queda registrado quién intentó qué orden y cuándo.
    db.execute(text("""
        INSERT INTO audit_log (accion, tabla, registro_id, datos_despues)
        VALUES (:accion, 'citas_programadas', :rid, CAST(:despues AS jsonb))
    """), {"accion": accion, "rid": rid, "despues": json.dumps(datos_despues, default=str)})


@router.get("/validar-orden")
def validar_orden_endpoint(numero: str, token: str, db: Session = Depends(get_db)):
    # Requiere el token de sesión (ya escaneó un QR real), mismo patrón que
    # /conductor-frecuente, para no dejar la consulta abierta a cualquiera.
    validar_token_sesion_registro(token)
    resultado = _validar_orden(db, numero)
    try:
        accion = "VALIDACION_ACEPTADA" if resultado["valido"] else "VALIDACION_RECHAZADA"
        _audit_publico(db, accion, numero, resultado)
        db.commit()
    except Exception:
        db.rollback()
    return resultado

CAMPOS_VEHICULO_PUBLICOS = [
    "placa_vehiculo", "nombre_conductor", "tipo_documento", "cedula_conductor",
    "telefono_conductor", "tipo_vehiculo",
    "fecha_pago_arl", "epp_cumple", "tipo_carga", "formato_carga",
    "cantidad_pallets", "manejo_carga",
]
# Nota: muelle_descargue NO lo llena el conductor — el guarda lo asigna al
# confirmar el ingreso (ver PUT /api/proveedores/{id}).

_PLACA_RE = re.compile(r"^[A-Z]+[0-9]+$")

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


@router.post("/autorregistro", status_code=201)
def autorregistro(
    body: dict,
    db: Session = Depends(get_db),
):
    token = body.get("token")
    validar_token_sesion_registro(token)

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

    # Revalidar cada orden server-side, sin confiar en lo que ya se validó en
    # el navegador (el token de sesión no ata la orden a una sesión específica,
    # y la franja horaria pudo vencer mientras el conductor llenaba el resto
    # del formulario). La empresa siempre sale de la cita, nunca de lo que
    # escribió el conductor.
    ordenes_validadas = []
    for o in ordenes:
        numero = (o.get("numero_orden_compra") or "").strip()
        if not numero:
            raise HTTPException(400, "Cada proveedor/orden debe tener número de orden de compra")
        chk = _validar_orden(db, numero)
        if not chk["valido"]:
            raise HTTPException(400, f"Orden {numero}: {chk['motivo']}")
        ordenes_validadas.append({
            **o,
            "numero_orden_compra": numero,
            "empresa": chk["proveedor_nombre"],
            "cita_id": chk["cita_id"],
        })

    ahora = datetime.now(_BOG)
    rid = str(uuid.uuid4())
    vals = {c: _clean(vehiculo.get(c)) for c in CAMPOS_VEHICULO if c in CAMPOS_VEHICULO_PUBLICOS}
    vals["id"] = rid
    vals["placa_vehiculo"] = placa
    vals["nombre_conductor"] = conductor
    vals["epp_cumple"] = bool(epp)
    vals["fecha"] = ahora.date().isoformat()
    vals["hora_ingreso"] = ahora.strftime("%H:%M:%S")
    vals["estado_confirmacion"] = "pendiente"
    vals["origen"] = "autorregistro"
    vals["creado_por"] = None

    cols = ", ".join(vals.keys())
    placeholders = ", ".join(f":{k}" for k in vals.keys())
    try:
        db.execute(text(f"INSERT INTO proveedores ({cols}) VALUES ({placeholders})"), vals)
        _insert_ordenes(db, rid, ordenes_validadas)
        for ov in ordenes_validadas:
            # WHERE estado != 'usada' cierra la carrera de dos conductores
            # validando la misma orden casi al mismo tiempo: solo uno gana.
            marcada = db.execute(text("""
                UPDATE citas_programadas SET estado = 'usada', proveedor_id = :pid, updated_at = NOW()
                WHERE id = :cid AND estado != 'usada'
            """), {"pid": rid, "cid": ov["cita_id"]})
            if marcada.rowcount == 0:
                raise HTTPException(409, f"La orden {ov['numero_orden_compra']} ya fue registrada por otro conductor justo ahora.")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except (IntegrityError, DataError):
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
