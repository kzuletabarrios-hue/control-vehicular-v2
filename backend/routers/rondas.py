# backend/routers/rondas.py
import uuid
import io
from datetime import date, datetime, time as dtime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from routers.auth import get_current_user

router = APIRouter()

ROLES_GESTION = ('admin', 'supervisor')
ROLES_RONDA   = ('admin', 'supervisor', 'recorredor_externo')

RONDAS_POR_TURNO   = 8
RONDA_CAMINATA_MIN = 20   # min. estimados para recorrer los puntos de una ronda
PERMANENCIA_MIN_MIN = 15  # min. mínimos de permanencia en Tanques entre rondas
ALERTA_ATRASO_MIN  = 35   # min. sin movimiento para marcar alerta en el panel

TURNOS = {'dia': dtime(6, 0), 'noche': dtime(18, 0)}
TURNO_DURACION_MIN = 720  # 12h

# Bloques de apoyo fijo en Control de Acceso (hora absoluta del día)
APOYOS_FIJOS = [
    (dtime(6, 0),  dtime(8, 0),  'Apoyo en Control de Acceso'),
    (dtime(11, 0), dtime(13, 0), 'Cubrimiento de almuerzos'),
    (dtime(13, 30), dtime(14, 30), 'Apoyo por cambio de turno en Control de Acceso'),
    (dtime(20, 0), dtime(22, 0), 'Apoyo nocturno en Control de Acceso'),
]


def _require_roles(*roles):
    def dep(user: dict = Depends(get_current_user)):
        if user['rol'] not in roles:
            raise HTTPException(403, "Sin permiso para esta acción")
        return user
    return dep


def _to_min(t: dtime) -> int:
    return t.hour * 60 + t.minute


def _fmt(min_abs: int) -> str:
    min_abs = min_abs % 1440
    return f"{min_abs // 60:02d}:{min_abs % 60:02d}"


def turno_actual(ahora: dtime = None) -> str:
    ahora = ahora or datetime.now().time()
    inicio_dia = _to_min(TURNOS['dia'])
    rel = (_to_min(ahora) - inicio_dia) % 1440
    return 'dia' if rel < TURNO_DURACION_MIN else 'noche'


def _apoyos_relativos(turno: str):
    """Bloques de apoyo fijo, en minutos relativos al inicio del turno."""
    inicio_turno = _to_min(TURNOS[turno])
    out = []
    for ini, fin, motivo in APOYOS_FIJOS:
        rel_ini = (_to_min(ini) - inicio_turno) % 1440
        rel_fin = (_to_min(fin) - inicio_turno) % 1440
        if rel_fin <= rel_ini:
            continue
        if 0 <= rel_ini and rel_fin <= TURNO_DURACION_MIN:
            out.append((rel_ini, rel_fin, motivo))
    return sorted(out)


def _ventanas_libres(apoyos):
    ventanas = []
    cursor = 0
    for ini, fin, _ in apoyos:
        if ini > cursor:
            ventanas.append((cursor, ini))
        cursor = max(cursor, fin)
    if cursor < TURNO_DURACION_MIN:
        ventanas.append((cursor, TURNO_DURACION_MIN))
    return [v for v in ventanas if v[1] > v[0]]


def calcular_cronograma(turno: str):
    """Genera la programación estimada de 8 rondas + apoyos fijos del turno,
    en minutos relativos al inicio del turno. No escribe en BD."""
    apoyos = _apoyos_relativos(turno)
    ventanas = _ventanas_libres(apoyos)

    # cuántas rondas caben (caminata) en cada ventana, proporcional a su duración
    capacidades = [max(0, (fin - ini) // RONDA_CAMINATA_MIN) for ini, fin in ventanas]
    cap_total = sum(capacidades)
    if cap_total == 0:
        asignadas = [0] * len(ventanas)
    else:
        duraciones = [fin - ini for ini, fin in ventanas]
        total_dur = sum(duraciones)
        crudo = [min(cap, round(RONDAS_POR_TURNO * dur / total_dur)) for cap, dur in zip(capacidades, duraciones)]
        # ajustar para que la suma sea exactamente RONDAS_POR_TURNO
        while sum(crudo) < RONDAS_POR_TURNO:
            for i in range(len(crudo)):
                if crudo[i] < capacidades[i]:
                    crudo[i] += 1
                    break
            else:
                break
        while sum(crudo) > RONDAS_POR_TURNO:
            for i in reversed(range(len(crudo))):
                if crudo[i] > 0:
                    crudo[i] -= 1
                    break
        asignadas = crudo

    items = []
    for ini, fin, motivo in apoyos:
        items.append({"tipo": "apoyo", "motivo": motivo, "inicio_min": ini, "fin_min": fin})

    numero = 1
    for (ini, fin), n in zip(ventanas, asignadas):
        if n == 0:
            items.append({"tipo": "permanencia", "inicio_min": ini, "fin_min": fin})
            continue
        duracion = fin - ini
        resto = duracion - n * RONDA_CAMINATA_MIN
        descanso = max(0, resto // n)
        cursor = ini
        for i in range(n):
            extra = (resto - descanso * n) if i == n - 1 else 0
            bloque_descanso = descanso + extra
            if bloque_descanso > 0:
                items.append({"tipo": "permanencia", "inicio_min": cursor, "fin_min": cursor + bloque_descanso})
                cursor += bloque_descanso
            items.append({"tipo": "ronda", "numero": numero, "inicio_min": cursor, "fin_min": cursor + RONDA_CAMINATA_MIN})
            cursor += RONDA_CAMINATA_MIN
            numero += 1

    items.sort(key=lambda x: x["inicio_min"])
    inicio_turno_abs = _to_min(TURNOS[turno])
    for it in items:
        it["hora_inicio"] = _fmt(inicio_turno_abs + it["inicio_min"])
        it["hora_fin"]    = _fmt(inicio_turno_abs + it["fin_min"])
    return items


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
    es_base  = bool(body.get("es_base", False))
    existe_qr = db.execute(
        text("SELECT 1 FROM puntos_ronda WHERE codigo_qr = :qr"), {"qr": codigo_qr}
    ).fetchone()
    if existe_qr:
        raise HTTPException(409, "El código QR ya está en uso")
    db.execute(text("""
        INSERT INTO puntos_ronda (id, nombre, codigo_qr, orden, es_base)
        VALUES (:id, :nombre, :codigo_qr, :orden, :es_base)
    """), {"id": rid, "nombre": nombre, "codigo_qr": codigo_qr, "orden": orden, "es_base": es_base})
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
    campos = {c: body[c] for c in ("nombre", "orden", "activo", "es_base") if c in body}
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


def _qr_cards_html(filas):
    cards = []
    import qrcode
    from qrcode.image.svg import SvgPathImage
    for nombre, codigo_qr, etiqueta in filas:
        img = qrcode.make(codigo_qr, image_factory=SvgPathImage)
        buf = io.BytesIO()
        img.save(buf)
        svg = buf.getvalue().decode("utf-8")
        svg = svg[svg.find("<svg"):]
        cards.append(f"""
        <div class="card">
          <div class="qr">{svg}</div>
          <div class="name">{nombre}</div>
          <div class="code">{codigo_qr}</div>
          <div class="order">{etiqueta}</div>
        </div>""")
    return "".join(cards)


_QR_PAGE_STYLE = """
  body{font-family:'DM Sans',sans-serif;margin:0;padding:20px;background:#fff;color:#0f172a}
  h1{text-align:center;font-size:20px;margin-bottom:4px;color:#0f2440}
  .sub{text-align:center;color:#64748b;font-size:12px;margin-bottom:20px}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
  .card{border:1.5px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;page-break-inside:avoid}
  .qr svg{width:160px;height:160px;display:block;margin:0 auto}
  .name{font-weight:700;font-size:14px;margin-top:10px;color:#0f2440}
  .code{font-size:9px;color:#64748b;margin-top:4px;word-break:break-all;font-family:monospace}
  .order{font-size:10px;color:#94a3b8;margin-top:3px;font-weight:600}
  @media print{ body{padding:0} .grid{gap:12px} h1,.sub{margin-bottom:8px} }
"""


# ── QR PARA IMPRIMIR ─────────────────────────────────────────────

@router.get("/puntos/qr-print", response_class=HTMLResponse)
def qr_print(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    try:
        import qrcode  # noqa: F401
    except ImportError:
        raise HTTPException(500, "Librería qrcode no instalada en el servidor")

    puntos = db.execute(text(
        "SELECT * FROM puntos_ronda WHERE activo=TRUE ORDER BY orden ASC, nombre ASC"
    )).fetchall()
    apoyo = db.execute(text(
        "SELECT * FROM puntos_apoyo WHERE activo=TRUE LIMIT 1"
    )).fetchone()

    if not puntos and not apoyo:
        return HTMLResponse("<html><body><p>No hay puntos activos.</p></body></html>")

    filas = [(p.nombre, p.codigo_qr, f"Punto #{p.orden}" + (" · BASE" if p.es_base else "")) for p in puntos]
    if apoyo:
        filas.append((apoyo.nombre, apoyo.codigo_qr, "QR exclusivo · No cuenta como ronda"))

    html = f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"/>
<title>QR Puntos de Ronda — CEDI R10</title>
<style>{_QR_PAGE_STYLE}</style></head><body>
<h1>Puntos de Ronda y Apoyo Operativo — CEDI R10</h1>
<p class="sub">Imprimir y pegar físicamente en cada punto. Escaneados con la app para marcar la ronda o el apoyo.</p>
<div class="grid">{_qr_cards_html(filas)}</div>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""
    return HTMLResponse(html)


@router.get("/apoyo/qr-print", response_class=HTMLResponse)
def apoyo_qr_print(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    apoyo = db.execute(text("SELECT * FROM puntos_apoyo WHERE activo=TRUE LIMIT 1")).fetchone()
    if not apoyo:
        return HTMLResponse("<html><body><p>No hay QR de apoyo configurado.</p></body></html>")
    filas = [(apoyo.nombre, apoyo.codigo_qr, "QR exclusivo · No cuenta como ronda")]
    html = f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"/>
<title>QR Apoyo Operativo — CEDI R10</title>
<style>{_QR_PAGE_STYLE}</style></head><body>
<h1>QR Apoyo Operativo — CEDI R10</h1>
<p class="sub">Usar únicamente al llegar o salir de un apoyo en Control de Acceso.</p>
<div class="grid">{_qr_cards_html(filas)}</div>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""
    return HTMLResponse(html)


# ── CRONOGRAMA DEL TURNO ─────────────────────────────────────────

@router.get("/turno/cronograma")
def turno_cronograma(
    turno: str = None,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    turno = turno if turno in ("dia", "noche") else turno_actual()
    items = calcular_cronograma(turno)

    hoy = str(date.today())
    ciclos = db.execute(text("""
        SELECT * FROM rondas_ciclos
        WHERE recorredor_id = :uid AND fecha = :hoy AND turno = :turno
        ORDER BY numero_ronda ASC
    """), {"uid": user["id"], "hoy": hoy, "turno": turno}).fetchall()
    ciclos_por_numero = {c.numero_ronda: c for c in ciclos}

    apoyos = db.execute(text("""
        SELECT * FROM apoyos_operativos
        WHERE recorredor_id = :uid AND fecha = :hoy
        ORDER BY hora_llegada ASC
    """), {"uid": user["id"], "hoy": hoy}).fetchall()

    inicio_turno_abs = _to_min(TURNOS[turno])

    def _apoyo_en_bloque(ini_min, fin_min):
        for a in apoyos:
            llegada_min = a.hora_llegada.hour * 60 + a.hora_llegada.minute
            rel = (llegada_min - inicio_turno_abs) % 1440
            if ini_min <= rel <= fin_min:
                return a
        return None

    for it in items:
        if it["tipo"] == "ronda":
            ciclo = ciclos_por_numero.get(it["numero"])
            it["estado"] = ciclo.estado if ciclo else "pendiente"
            it["ciclo_id"] = str(ciclo.id) if ciclo else None
        elif it["tipo"] == "apoyo":
            a = _apoyo_en_bloque(it["inicio_min"], it["fin_min"])
            if a:
                it["estado"] = "completo" if a.hora_salida else "en_curso"
            else:
                it["estado"] = "pendiente"

    completadas = sum(1 for c in ciclos if c.estado == "completa")
    return {
        "turno": turno,
        "items": items,
        "rondas_completadas": completadas,
        "rondas_pendientes": max(0, RONDAS_POR_TURNO - completadas),
        "rondas_objetivo": RONDAS_POR_TURNO,
    }


# ── CICLO ACTIVO ──────────────────────────────────────────────────

def _puntos_obligatorios(db):
    return db.execute(text(
        "SELECT * FROM puntos_ronda WHERE activo=TRUE AND es_base=FALSE ORDER BY orden ASC"
    )).fetchall()


@router.get("/ciclo/activo")
def ciclo_activo(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    ciclo = db.execute(text("""
        SELECT * FROM rondas_ciclos
        WHERE recorredor_id = :uid AND estado = 'en_curso'
        ORDER BY hora_inicio DESC LIMIT 1
    """), {"uid": user["id"]}).fetchone()
    if not ciclo:
        return {"activo": False}

    marcados = db.execute(text("""
        SELECT r.*, p.nombre AS punto_nombre, p.orden, p.es_base
        FROM rondas r JOIN puntos_ronda p ON p.id = r.punto_id
        WHERE r.ciclo_id = :cid ORDER BY r.created_at ASC
    """), {"cid": ciclo.id}).fetchall()
    marcados_ids = {m.punto_id for m in marcados}

    obligatorios = _puntos_obligatorios(db)
    pendientes = [dict(p._mapping) for p in obligatorios if str(p.id) not in {str(x) for x in marcados_ids}]

    return {
        "activo": True,
        "ciclo": dict(ciclo._mapping),
        "marcados": [dict(m._mapping) for m in marcados],
        "pendientes": pendientes,
        "todos_marcados": len(pendientes) == 0,
    }


@router.post("/ciclo/iniciar", status_code=201)
def ciclo_iniciar(
    body: dict = None,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    body = body or {}
    turno = body.get("turno") if body.get("turno") in ("dia", "noche") else turno_actual()
    hoy = str(date.today())

    activo = db.execute(text("""
        SELECT 1 FROM rondas_ciclos WHERE recorredor_id = :uid AND estado = 'en_curso'
    """), {"uid": user["id"]}).fetchone()
    if activo:
        raise HTTPException(409, "Ya tienes una ronda en curso. Complétala antes de iniciar otra.")

    apoyo_abierto = db.execute(text("""
        SELECT 1 FROM apoyos_operativos
        WHERE recorredor_id = :uid AND fecha = :hoy AND hora_salida IS NULL
    """), {"uid": user["id"], "hoy": hoy}).fetchone()
    if apoyo_abierto:
        raise HTTPException(409, "Tienes un apoyo operativo en curso. Finalízalo antes de iniciar una ronda.")

    ahora = datetime.now().time()
    for ini, fin, motivo in APOYOS_FIJOS:
        if ini <= ahora < fin:
            raise HTTPException(409, f"Horario de apoyo obligatorio ({motivo}). No se puede iniciar ronda ahora.")

    completadas = db.execute(text("""
        SELECT COUNT(*) AS n FROM rondas_ciclos
        WHERE recorredor_id = :uid AND fecha = :hoy AND turno = :turno AND estado = 'completa'
    """), {"uid": user["id"], "hoy": hoy, "turno": turno}).fetchone().n
    if completadas >= RONDAS_POR_TURNO:
        raise HTTPException(409, f"Ya completaste las {RONDAS_POR_TURNO} rondas obligatorias del turno.")

    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO rondas_ciclos (id, recorredor_id, fecha, turno, numero_ronda, estado)
        VALUES (:id, :uid, :hoy, :turno, :num, 'en_curso')
    """), {"id": rid, "uid": user["id"], "hoy": hoy, "turno": turno, "num": completadas + 1})
    db.commit()
    return {"id": rid, "numero_ronda": completadas + 1, "message": "Ronda iniciada desde Tanques"}


# ── MARCAR PUNTO DENTRO DE UN CICLO ──────────────────────────────

@router.put("/marcar", status_code=201)
def marcar_punto(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    ciclo_id         = body.get("ciclo_id")
    punto_id         = body.get("punto_id")
    codigo_escaneado = (body.get("codigo_escaneado") or "").strip()
    estado           = body.get("estado", "ok")
    observacion      = body.get("observacion") or None
    fotografia       = body.get("fotografia") or None

    if not ciclo_id:
        raise HTTPException(400, "ciclo_id es requerido")
    if not punto_id:
        raise HTTPException(400, "punto_id es requerido")
    if not codigo_escaneado:
        raise HTTPException(400, "Debes escanear el código QR del punto")
    if estado not in ("ok", "novedad", "omitido"):
        raise HTTPException(400, "estado inválido: debe ser ok, novedad u omitido")
    if estado == "omitido" and not observacion:
        raise HTTPException(400, "La observación es obligatoria al omitir un punto")

    ciclo = db.execute(text("""
        SELECT * FROM rondas_ciclos WHERE id = :cid AND recorredor_id = :uid
    """), {"cid": ciclo_id, "uid": user["id"]}).fetchone()
    if not ciclo:
        raise HTTPException(404, "Ronda no encontrada")
    if ciclo.estado != "en_curso":
        raise HTTPException(409, "Esta ronda ya fue cerrada")

    punto = db.execute(
        text("SELECT * FROM puntos_ronda WHERE id = :id AND activo=TRUE"), {"id": punto_id}
    ).fetchone()
    if not punto:
        raise HTTPException(404, "Punto no encontrado o inactivo")
    if punto.codigo_qr != codigo_escaneado:
        raise HTTPException(400, "Código QR no corresponde a este punto")

    ya_marcado = db.execute(text("""
        SELECT 1 FROM rondas WHERE punto_id = :pid AND ciclo_id = :cid
    """), {"pid": punto_id, "cid": ciclo_id}).fetchone()
    if ya_marcado:
        raise HTTPException(409, "Este punto ya fue marcado en esta ronda")

    obligatorios = _puntos_obligatorios(db)
    if punto.es_base:
        marcados = db.execute(text("""
            SELECT punto_id FROM rondas WHERE ciclo_id = :cid
        """), {"cid": ciclo_id}).fetchall()
        marcados_ids = {str(m.punto_id) for m in marcados}
        faltan = [p for p in obligatorios if str(p.id) not in marcados_ids]
        if faltan:
            raise HTTPException(400, f"Aún faltan {len(faltan)} puntos por recorrer antes de regresar a Tanques")

    rid  = str(uuid.uuid4())
    hora = datetime.now().strftime("%H:%M:%S")
    db.execute(text("""
        INSERT INTO rondas
            (id, recorredor_id, punto_id, ciclo_id, fecha, hora_marcacion,
             codigo_escaneado, estado, observacion, fotografia)
        VALUES
            (:id, :recorredor_id, :punto_id, :ciclo_id, CURRENT_DATE, :hora,
             :codigo_escaneado, :estado, :observacion, :fotografia)
    """), {
        "id": rid, "recorredor_id": user["id"], "punto_id": punto_id, "ciclo_id": ciclo_id,
        "hora": hora, "codigo_escaneado": codigo_escaneado,
        "estado": estado, "observacion": observacion, "fotografia": fotografia,
    })

    cerrada = False
    if punto.es_base:
        db.execute(text("""
            UPDATE rondas_ciclos SET hora_fin = NOW(), estado = 'completa' WHERE id = :cid
        """), {"cid": ciclo_id})
        cerrada = True

    db.commit()
    return {
        "id": rid,
        "message": "Ronda completada — regresaste a Tanques" if cerrada else "Punto marcado correctamente",
        "ciclo_cerrado": cerrada,
    }


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
            ORDER BY r.created_at DESC
        """), {"hoy": hoy}).fetchall()
    else:
        rows = db.execute(text("""
            SELECT r.*, p.nombre AS punto_nombre, p.orden
            FROM rondas r
            JOIN puntos_ronda p ON p.id = r.punto_id
            WHERE r.recorredor_id = :uid AND r.fecha = :hoy
            ORDER BY r.created_at DESC
        """), {"uid": user["id"], "hoy": hoy}).fetchall()
    return [dict(r._mapping) for r in rows]


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
        ORDER BY r.fecha DESC, r.created_at DESC
        LIMIT 500
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


# ── APOYO OPERATIVO ───────────────────────────────────────────────

@router.post("/apoyo/marcar", status_code=201)
def apoyo_marcar(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    codigo_escaneado = (body.get("codigo_escaneado") or "").strip()
    motivo_manual    = body.get("motivo") or None

    if not codigo_escaneado:
        raise HTTPException(400, "Debes escanear el QR de Apoyo Operativo")

    qr = db.execute(text(
        "SELECT * FROM puntos_apoyo WHERE activo=TRUE AND codigo_qr = :qr"
    ), {"qr": codigo_escaneado}).fetchone()
    if not qr:
        raise HTTPException(400, "Código QR no corresponde al QR de Apoyo Operativo")

    hoy = str(date.today())
    abierto = db.execute(text("""
        SELECT * FROM apoyos_operativos
        WHERE recorredor_id = :uid AND fecha = :hoy AND hora_salida IS NULL
        ORDER BY hora_llegada DESC LIMIT 1
    """), {"uid": user["id"], "hoy": hoy}).fetchone()

    if abierto:
        db.execute(text("""
            UPDATE apoyos_operativos SET hora_salida = NOW() WHERE id = :id
        """), {"id": abierto.id})
        db.commit()
        return {"id": str(abierto.id), "accion": "salida", "message": "Salida de apoyo operativo registrada"}

    ciclo_activo_row = db.execute(text("""
        SELECT 1 FROM rondas_ciclos WHERE recorredor_id = :uid AND estado = 'en_curso'
    """), {"uid": user["id"]}).fetchone()
    if ciclo_activo_row:
        raise HTTPException(409, "Tienes una ronda en curso. Termínala o márcala con novedad antes de iniciar un apoyo.")

    ahora = datetime.now().time()
    motivo_auto = None
    for ini, fin, motivo in APOYOS_FIJOS:
        if ini <= ahora < fin:
            motivo_auto = motivo
            break
    motivo  = motivo_auto or motivo_manual or "Apoyo operativo (manual)"
    tipo    = "automatico" if motivo_auto else "manual"

    rid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO apoyos_operativos (id, recorredor_id, fecha, motivo, tipo, codigo_escaneado)
        VALUES (:id, :uid, :hoy, :motivo, :tipo, :codigo)
    """), {"id": rid, "uid": user["id"], "hoy": hoy, "motivo": motivo, "tipo": tipo, "codigo": codigo_escaneado})
    db.commit()
    return {"id": rid, "accion": "llegada", "motivo": motivo, "message": "Llegada a apoyo operativo registrada"}


@router.get("/apoyo/hoy")
def apoyo_hoy(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_RONDA)),
):
    hoy = str(date.today())
    rows = db.execute(text("""
        SELECT * FROM apoyos_operativos
        WHERE recorredor_id = :uid AND fecha = :hoy
        ORDER BY hora_llegada DESC
    """), {"uid": user["id"], "hoy": hoy}).fetchall()
    return [dict(r._mapping) for r in rows]


# ── PANEL DE SEGUIMIENTO (supervisión) ───────────────────────────

@router.get("/panel")
def panel(
    db: Session = Depends(get_db),
    user: dict = Depends(_require_roles(*ROLES_GESTION)),
):
    hoy = str(date.today())
    recorredores = db.execute(text("""
        SELECT u.id, u.nombre FROM usuarios u
        JOIN roles r ON r.id = u.rol_id
        WHERE r.nombre = 'recorredor_externo' AND u.activo = TRUE
        ORDER BY u.nombre ASC
    """)).fetchall()

    resultado = []
    for u in recorredores:
        ciclos = db.execute(text("""
            SELECT * FROM rondas_ciclos WHERE recorredor_id = :uid AND fecha = :hoy
        """), {"uid": u.id, "hoy": hoy}).fetchall()
        completadas = sum(1 for c in ciclos if c.estado == 'completa')
        en_curso    = next((c for c in ciclos if c.estado == 'en_curso'), None)

        apoyos = db.execute(text("""
            SELECT * FROM apoyos_operativos WHERE recorredor_id = :uid AND fecha = :hoy
            ORDER BY hora_llegada DESC
        """), {"uid": u.id, "hoy": hoy}).fetchall()
        apoyo_en_curso = next((a for a in apoyos if a.hora_salida is None), None)

        ultima_marcacion = db.execute(text("""
            SELECT r.hora_marcacion, r.created_at, p.nombre AS punto_nombre
            FROM rondas r JOIN puntos_ronda p ON p.id = r.punto_id
            WHERE r.recorredor_id = :uid AND r.fecha = :hoy
            ORDER BY r.created_at DESC LIMIT 1
        """), {"uid": u.id, "hoy": hoy}).fetchone()

        eventos = []
        if ultima_marcacion:
            eventos.append(("ronda", ultima_marcacion.created_at, ultima_marcacion.punto_nombre))
        for a in apoyos:
            eventos.append(("apoyo", a.hora_salida or a.hora_llegada, "Apoyo Operativo"))
        eventos.sort(key=lambda e: e[1], reverse=True)
        ultimo = eventos[0] if eventos else None

        minutos_sin_movimiento = None
        if ultimo:
            delta = datetime.now(ultimo[1].tzinfo) - ultimo[1] if ultimo[1].tzinfo else datetime.now() - ultimo[1]
            minutos_sin_movimiento = round(delta.total_seconds() / 60)

        alerta = (
            minutos_sin_movimiento is not None
            and minutos_sin_movimiento > ALERTA_ATRASO_MIN
            and not apoyo_en_curso
        )

        resultado.append({
            "recorredor_id": str(u.id),
            "recorredor_nombre": u.nombre,
            "rondas_completadas": completadas,
            "rondas_pendientes": max(0, RONDAS_POR_TURNO - completadas),
            "ronda_en_curso": dict(en_curso._mapping) if en_curso else None,
            "ultimo_evento": {"tipo": ultimo[0], "detalle": ultimo[2]} if ultimo else None,
            "minutos_sin_movimiento": minutos_sin_movimiento,
            "alerta_atraso": alerta,
            "apoyo_en_curso": dict(apoyo_en_curso._mapping) if apoyo_en_curso else None,
            "historial_apoyos": [dict(a._mapping) for a in apoyos],
        })

    return resultado
