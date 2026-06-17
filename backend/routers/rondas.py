# backend/routers/rondas.py
import uuid
import io
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import get_current_user

router = APIRouter()

ROLES_GESTION = ('admin', 'supervisor')
ROLES_RONDA   = ('admin', 'supervisor', 'recorredor_externo')


def _require_roles(*roles):
    def dep(user: dict = Depends(get_current_user)):
        if user['rol'] not in roles:
            raise HTTPException(403, "Sin permiso para esta acción")
        return user
    return dep


# ── PUNTOS DE RONDA ──────────────────────────────────────────────

@router.get("/puntos")
def listar_puntos(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    rows = db.execute(text(
        "SELECT * FROM puntos_ronda WHERE activo=TRUE ORDER BY orden ASC, nombre ASC"
    )).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/puntos", status_code=201)
def crear_punto(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre es requerido")
    rid      = str(uuid.uuid4())
    codigo_qr = body.get("codigo_qr") or f"CEDI-R10-{rid[:8].upper()}"
    orden    = body.get("orden", 1)
    existe_qr = db.execute(
        text("SELECT 1 FROM puntos_ronda WHERE codigo_qr = :qr"), {"qr": codigo_qr}
    ).fetchone()
    if existe_qr:
        raise HTTPException(409, "El código QR ya está en uso")
    db.execute(text("""
        INSERT INTO puntos_ronda (id, nombre, codigo_qr, orden)
        VALUES (:id, :nombre, :codigo_qr, :orden)
    """), {"id": rid, "nombre": nombre, "codigo_qr": codigo_qr, "orden": orden})
    db.commit()
    return {"id": rid, "codigo_qr": codigo_qr, "message": "Punto creado"}


@router.put("/puntos/{id}")
def actualizar_punto(
    id: str,
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    existe = db.execute(text("SELECT 1 FROM puntos_ronda WHERE id = :id"), {"id": id}).fetchone()
    if not existe:
        raise HTTPException(404, "Punto no encontrado")
    campos = {c: body[c] for c in ("nombre", "orden", "activo") if c in body}
    if not campos:
        raise HTTPException(400, "Sin campos para actualizar")
    campos["id"] = id
    sets = ", ".join(f"{c} = :{c}" for c in campos if c != "id")
    db.execute(text(f"UPDATE puntos_ronda SET {sets} WHERE id = :id"), campos)
    db.commit()
    return {"message": "Punto actualizado"}


@router.delete("/puntos/{id}")
def eliminar_punto(
    id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    db.execute(text("UPDATE puntos_ronda SET activo=FALSE WHERE id = :id"), {"id": id})
    db.commit()
    return {"message": "Punto desactivado"}


# ── QR PARA IMPRIMIR ─────────────────────────────────────────────

@router.get("/puntos/qr-print", response_class=HTMLResponse)
def qr_print(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        raise HTTPException(500, "Librería qrcode no instalada en el servidor")

    puntos = db.execute(text(
        "SELECT * FROM puntos_ronda WHERE activo=TRUE ORDER BY orden ASC, nombre ASC"
    )).fetchall()

    if not puntos:
        return HTMLResponse("<html><body><p>No hay puntos activos.</p></body></html>")

    cards = []
    for p in puntos:
        img = qrcode.make(p.codigo_qr, image_factory=SvgPathImage)
        buf = io.BytesIO()
        img.save(buf)
        svg = buf.getvalue().decode("utf-8")
        svg = svg[svg.find("<svg"):]   # strip XML declaration
        cards.append(f"""
        <div class="card">
          <div class="qr">{svg}</div>
          <div class="name">{p.nombre}</div>
          <div class="code">{p.codigo_qr}</div>
          <div class="order">Punto #{p.orden}</div>
        </div>""")

    html = f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"/>
<title>QR Puntos de Ronda — CEDI R10</title>
<style>
  body{{font-family:'DM Sans',sans-serif;margin:0;padding:20px;background:#fff;color:#0f172a}}
  h1{{text-align:center;font-size:20px;margin-bottom:4px;color:#0f2440}}
  .sub{{text-align:center;color:#64748b;font-size:12px;margin-bottom:20px}}
  .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
  .card{{border:1.5px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;page-break-inside:avoid}}
  .qr svg{{width:160px;height:160px;display:block;margin:0 auto}}
  .name{{font-weight:700;font-size:14px;margin-top:10px;color:#0f2440}}
  .code{{font-size:9px;color:#64748b;margin-top:4px;word-break:break-all;font-family:monospace}}
  .order{{font-size:10px;color:#94a3b8;margin-top:3px;font-weight:600}}
  @media print{{
    body{{padding:0}}
    .grid{{gap:12px}}
    h1,.sub{{margin-bottom:8px}}
  }}
</style></head><body>
<h1>Puntos de Ronda — CEDI R10</h1>
<p class="sub">Imprimir y pegar físicamente en cada punto. Escaneados con la app para marcar la ronda.</p>
<div class="grid">{"".join(cards)}</div>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""
    return HTMLResponse(html)


# ── RONDAS (MARCACIONES DEL DÍA) ─────────────────────────────────

@router.get("/hoy")
def ronda_hoy(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    hoy = str(date.today())
    if user['rol'] in ROLES_GESTION:
        rows = db.execute(text("""
            SELECT r.*, p.nombre AS punto_nombre, p.orden,
                   u.nombre AS recorredor_nombre
            FROM rondas r
            JOIN puntos_ronda p ON p.id = r.punto_id
            JOIN usuarios u     ON u.id = r.recorredor_id
            WHERE r.fecha = :hoy
            ORDER BY p.orden ASC, r.created_at ASC
        """), {"hoy": hoy}).fetchall()
    else:
        rows = db.execute(text("""
            SELECT r.*, p.nombre AS punto_nombre, p.orden
            FROM rondas r
            JOIN puntos_ronda p ON p.id = r.punto_id
            WHERE r.recorredor_id = :uid AND r.fecha = :hoy
            ORDER BY p.orden ASC
        """), {"uid": user["id"], "hoy": hoy}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/marcar", status_code=201)
def marcar_punto(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    punto_id         = body.get("punto_id")
    codigo_escaneado = (body.get("codigo_escaneado") or "").strip()
    estado           = body.get("estado", "ok")
    observacion      = body.get("observacion") or None
    fotografia       = body.get("fotografia") or None

    if not punto_id:
        raise HTTPException(400, "punto_id es requerido")
    if not codigo_escaneado:
        raise HTTPException(400, "Debes escanear el código QR del punto")
    if estado not in ("ok", "novedad", "omitido"):
        raise HTTPException(400, "estado inválido: debe ser ok, novedad u omitido")
    if estado == "omitido" and not observacion:
        raise HTTPException(400, "La observación es obligatoria al omitir un punto")

    punto = db.execute(
        text("SELECT * FROM puntos_ronda WHERE id = :id AND activo=TRUE"), {"id": punto_id}
    ).fetchone()
    if not punto:
        raise HTTPException(404, "Punto no encontrado o inactivo")

    if punto.codigo_qr != codigo_escaneado:
        raise HTTPException(400, "Código QR no corresponde a este punto")

    ya_marcado = db.execute(text("""
        SELECT 1 FROM rondas
        WHERE punto_id = :pid AND recorredor_id = :uid AND fecha = CURRENT_DATE
    """), {"pid": punto_id, "uid": user["id"]}).fetchone()
    if ya_marcado:
        raise HTTPException(409, "Este punto ya fue marcado hoy")

    rid  = str(uuid.uuid4())
    hora = datetime.now().strftime("%H:%M:%S")
    db.execute(text("""
        INSERT INTO rondas
            (id, recorredor_id, punto_id, fecha, hora_marcacion,
             codigo_escaneado, estado, observacion, fotografia)
        VALUES
            (:id, :recorredor_id, :punto_id, CURRENT_DATE, :hora,
             :codigo_escaneado, :estado, :observacion, :fotografia)
    """), {
        "id": rid, "recorredor_id": user["id"], "punto_id": punto_id,
        "hora": hora, "codigo_escaneado": codigo_escaneado,
        "estado": estado, "observacion": observacion, "fotografia": fotografia,
    })
    db.commit()
    return {"id": rid, "message": "Punto marcado correctamente"}


@router.get("/historial")
def historial(
    fecha: str = None,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    where  = ["1=1"]
    params = {}
    if fecha:
        where.append("r.fecha = :fecha")
        params["fecha"] = fecha
    rows = db.execute(text(f"""
        SELECT r.*, p.nombre AS punto_nombre, p.orden,
               u.nombre AS recorredor_nombre
        FROM rondas r
        JOIN puntos_ronda p ON p.id = r.punto_id
        JOIN usuarios u     ON u.id = r.recorredor_id
        WHERE {' AND '.join(where)}
        ORDER BY r.fecha DESC, p.orden ASC
        LIMIT 500
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]
