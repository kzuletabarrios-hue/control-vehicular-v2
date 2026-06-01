# backend/routers/export.py
import io
from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from database import get_db
from routers.auth import require_permiso

router = APIRouter()

NAVY = "0F2440"
AMBER = "F59E0B"


def _header_style(ws, headers: list[str]):
    fill = PatternFill("solid", fgColor=NAVY)
    font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"


def _autowidth(ws):
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)


def _stream(wb: Workbook, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/flota")
def export_flota(
    fecha_desde: str = Query(default=None),
    fecha_hasta: str = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("flota", "export")),
):
    where = ["1=1"]
    params = {}
    if fecha_desde:
        where.append("fecha >= :desde")
        params["desde"] = fecha_desde
    if fecha_hasta:
        where.append("fecha <= :hasta")
        params["hasta"] = fecha_hasta

    rows = db.execute(text(f"""
        SELECT fecha, placa, conductor, n_pallets, n_contenedores,
               cant_volumen_externo, muelle_cargue,
               ultima_tienda_visitada, protocolo, sello, sello_entrada,
               hora_salida_muelle, temperatura, hora_salida_cedi, hora_llegada,
               observacion
        FROM flota_propia
        WHERE {' AND '.join(where)}
        ORDER BY fecha DESC, created_at DESC
    """), params).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Flota Propia"

    headers = [
        "Fecha", "Placa", "Conductor", "Pallets", "Contenedores",
        "Vol. Externo", "Muelle", "Última Tienda", "Protocolo",
        "Sello", "Sello Entrada", "H. Salida Muelle", "Temperatura",
        "H. Salida CEDI", "H. Llegada", "Observación",
    ]
    _header_style(ws, headers)

    for row in rows:
        ws.append(list(row))

    _autowidth(ws)
    fname = f"flota_propia_{date.today()}.xlsx"
    return _stream(wb, fname)


@router.get("/proveedores")
def export_proveedores(
    fecha_desde: str = Query(default=None),
    fecha_hasta: str = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("proveedores", "export")),
):
    where = ["1=1"]
    params = {}
    if fecha_desde:
        where.append("fecha >= :desde")
        params["desde"] = fecha_desde
    if fecha_hasta:
        where.append("fecha <= :hasta")
        params["hasta"] = fecha_hasta

    rows = db.execute(text(f"""
        SELECT fecha, placa_vehiculo, nombre_conductor, tipo_vehiculo, empresa,
               muelle_descargue, carga_compartida, hora_ingreso, hora_salida,
               actividad_a_desarrollar, dependencia_autoriza, fecha_pago_arl, observaciones
        FROM proveedores
        WHERE {' AND '.join(where)}
        ORDER BY fecha DESC
    """), params).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Proveedores TGN"

    headers = [
        "Fecha", "Placa", "Conductor", "Tipo Vehículo", "Empresa",
        "Muelle Descargue", "Carga Compartida", "H. Ingreso", "H. Salida",
        "Actividad", "Dependencia Autoriza", "Pago ARL", "Observaciones",
    ]
    _header_style(ws, headers)
    for row in rows:
        ws.append(list(row))
    _autowidth(ws)
    return _stream(wb, f"proveedores_{date.today()}.xlsx")


@router.get("/control-acceso")
def export_control_acceso(
    fecha_desde: str = Query(default=None),
    fecha_hasta: str = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("control_acceso", "export")),
):
    where = ["1=1"]
    params = {}
    if fecha_desde:
        where.append("ca.fecha >= :desde")
        params["desde"] = fecha_desde
    if fecha_hasta:
        where.append("ca.fecha <= :hasta")
        params["hasta"] = fecha_hasta

    rows = db.execute(text(f"""
        SELECT ca.fecha, ca.cedula, ca.nombre, ca.contratista,
               ca.hora_ingreso, ca.hora_salida, ca.observaciones,
               b.estado AS estado_bd
        FROM control_acceso ca
        LEFT JOIN bd_control_acceso b ON ca.cedula = b.cedula
        WHERE {' AND '.join(where)}
        ORDER BY ca.fecha DESC
    """), params).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Control Acceso"

    headers = ["Fecha", "Cédula", "Nombre", "Contratista", "H. Ingreso", "H. Salida", "Observaciones", "Estado BD"]
    _header_style(ws, headers)
    for row in rows:
        ws.append(list(row))
    _autowidth(ws)
    return _stream(wb, f"control_acceso_{date.today()}.xlsx")


@router.get("/visitantes")
def export_visitantes(
    fecha_desde: str = Query(default=None),
    fecha_hasta: str = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permiso("visitantes", "export")),
):
    where = ["1=1"]
    params = {}
    if fecha_desde:
        where.append("fecha >= :desde")
        params["desde"] = fecha_desde
    if fecha_hasta:
        where.append("fecha <= :hasta")
        params["hasta"] = fecha_hasta

    rows = db.execute(text(f"""
        SELECT fecha, nombre, cedula, empresa, hora_ingreso, hora_salida, observaciones
        FROM visitantes
        WHERE {' AND '.join(where)}
        ORDER BY fecha DESC
    """), params).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Visitantes"

    headers = ["Fecha", "Nombre", "Cédula", "Empresa", "H. Ingreso", "H. Salida", "Observaciones"]
    _header_style(ws, headers)
    for row in rows:
        ws.append(list(row))
    _autowidth(ws)
    return _stream(wb, f"visitantes_{date.today()}.xlsx")
