// ── UTILS (fecha, geo, permisos, formatters) ──
// Extraído de frontend/index.html (líneas ~615-717, secciones
// "/* ── UTILS ── */" y "/* ── ANULACIÓN CONTROL ACCESO: permiso (UX) +
// traducción de errores ── */" del <script> monolítico). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado (ver notas de la Fase 2 del plan de migración) -- este módulo es
// una copia autocontenida, lista para que las fases 3-6 lo importen cuando
// quede conectado vía <script type="module">.

import { api } from './api-client.js';
import { Ico } from './icons.js';

const h = React.createElement;

const _bogSnap  = () => {const b=new Date(Date.now()-18000000);const p=n=>String(n).padStart(2,'0');return {fecha:`${b.getUTCFullYear()}-${p(b.getUTCMonth()+1)}-${p(b.getUTCDate())}`,hora:`${p(b.getUTCHours())}:${p(b.getUTCMinutes())}`};};
export const _tsBog    = async () => { try{return await api.get('/tiempo');}catch(_){return _bogSnap();} };

// Lectura puntual de GPS (una sola posición, no rastreo continuo). Nunca
// rechaza la promesa: si el navegador no da permiso, falla o se demora más
// de 6s, resuelve null y quien la use sigue adelante sin bloquear la acción.
export const obtenerUbicacion = () => new Promise(resolve=>{
  if(!navigator.geolocation){ resolve(null); return; }
  const listo = setTimeout(()=>resolve(null), 6000);
  navigator.geolocation.getCurrentPosition(
    pos=>{ clearTimeout(listo); resolve({lat:pos.coords.latitude, lng:pos.coords.longitude}); },
    ()=>{ clearTimeout(listo); resolve(null); },
    {enableHighAccuracy:true, timeout:5500, maximumAge:0}
  );
});
export const today     = () => _bogSnap().fecha;
export const ahoraHora = () => _bogSnap().hora;

// Beep de alerta (Web Audio API, sin archivos externos) para avisar cuando
// falten pocos minutos para una hora de cita. 3 tonos cortos ascendentes.
export const playAlertSound = () => {
  try{
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    [660,880,1046].forEach((freq,i)=>{
      const t0 = ctx.currentTime + i*0.22;
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'sine'; o.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.35, t0+0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0+0.18);
      o.start(t0); o.stop(t0+0.2);
    });
  }catch(e){ /* audio no soportado/bloqueado por el navegador */ }
};
export const fmtDate   = d  => d?new Date(d+'T12:00:00').toLocaleDateString('es-CO',{day:'2-digit',month:'short'}):'—';
// Timestamp completo (usado para anulado_at, created_at, etc. — vienen como TIMESTAMPTZ ISO)
export const fmtDateHora = iso => { if(!iso) return '—'; const d=new Date(iso); return isNaN(d) ? '—' : d.toLocaleString('es-CO',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}); };

/* ── ANULACIÓN CONTROL ACCESO: permiso (UX) + traducción de errores ──
   /auth/me NO expone el objeto `permisos` real de la BD (el backend lo
   descarta a propósito en /auth/me, ver auth.py). Esta lista es un
   espejo manual de qué roles quedaron con "anular" tras
   migration_anulacion_control_acceso.sql (todo rol que ya tuviera
   "write" en control_acceso). NO es la fuente de verdad: solo controla
   mostrar/ocultar el botón. El backend re-valida siempre con 403, así
   que un desajuste aquí es un problema de UX (botón visible que falla,
   o botón oculto que sí funcionaría), nunca un hueco de seguridad.
   Si el equipo agrega permisos granulares a /auth/me, reemplazar esto. */
export const ROLES_ANULAR_CONTROL_ACCESO = ['admin','supervisor','operador','guarda_peatonal'];
export const puedeAnularAcceso = user => !!user?.rol && ROLES_ANULAR_CONTROL_ACCESO.includes(user.rol);

// Helper de permisos granulares (UX): usa `permisos` tal como llega de /auth/login
// o /auth/me. El backend re-valida siempre con 403, así que esto solo decide
// mostrar/ocultar UI. Aún sin consumidores — se usará al construir las vistas
// de Muelles/Citas para el coordinador (solo-lectura).
export const puede = (user, modulo, accion) => !!user?.permisos?.[modulo]?.includes(accion);

// Traduce el detail crudo de PUT /control-acceso/{id}/anular (400/403/404)
// a un mensaje accionable. api._fetch descarta el status code y hace
// throw new Error(await r.text()), así que acá solo tenemos el texto del
// body — se intenta parsear como JSON de FastAPI ({"detail":...}) y si
// falla se usa el texto crudo tal cual.
export function textoErrorAnulacion(e){
  let detail = '';
  try{
    const parsed = JSON.parse(e.message);
    if(typeof parsed.detail === 'string') detail = parsed.detail;
    else if(Array.isArray(parsed.detail) && parsed.detail[0]) detail = String(parsed.detail[0].msg||'').replace(/^Value error,\s*/i,'');
  }catch(_){ detail = e.message || ''; }
  const d = detail.toLowerCase();
  if(d.includes('no encontrado')) return 'Este registro ya no existe (puede que ya lo hayan eliminado). Actualiza la lista.';
  if(d.includes('sin permiso') || d.includes('no tiene el permiso')) return 'No tienes permiso para anular registros. Pide a un supervisor o administrador que lo haga.';
  if(d.includes('ya está anulado')) return 'Este registro ya había sido anulado antes. Actualiza la lista para verlo en "Anulados".';
  if(d.includes('fuera de la ventana')) return 'Ya pasaron más de 24 horas desde que se creó este registro. Pide a un supervisor o administrador que lo anule.';
  if(d.includes('motivo')) return 'Escribe el motivo de la anulación.';
  return detail || 'No se pudo anular el registro. Intenta de nuevo.';
}
export const initials  = n  => (n||'U').split(' ').slice(0,2).map(w=>w[0]).join('').toUpperCase();
// Normaliza nombres propios a "Primera Letra Mayúscula" (evita que queden en
// MAYÚSCULA SOSTENIDA o en minúscula por como los digite quien los registra).
export const capitalizarNombre = s => (s||'').replace(/\s+/g,' ').trim()
  .split(' ').map(w=>w?w.charAt(0).toLocaleUpperCase('es')+w.slice(1).toLocaleLowerCase('es'):w).join(' ');
// Valida que un valor de <input type="date"> sea una fecha real con año de 4 dígitos
// razonable. Los navegadores no siempre lo garantizan (ver bug de "20226-06-11").
export const fechaValida = v => {
  if(!v) return true;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
  if(!m) return false;
  const anio = +m[1];
  return anio>=2000 && anio<=2100;
};
// Extrae el número de muelle de lo que el guarda haya digitado (ej. "Muelle 7",
// "7", " 07 ") -- el campo es texto libre, así que se tolera cualquier prefijo.
// Devuelve null si no hay un número reconocible.
export const normalizarMuelle = v => {
  if(v===null || v===undefined || v==='') return null;
  const m = /\d+/.exec(String(v));
  if(!m) return null;
  const n = parseInt(m[0],10);
  return Number.isFinite(n) ? n : null;
};

// Traduce el `rol` crudo del usuario (BD/JWT) a una etiqueta legible.
// Extraído de frontend/index.html línea ~4603 (sección "/* ── BASE DATOS
// PAGE ── */", usado ahí por BdUsuariosTab). Se adelanta a core/utils.js en
// la Fase 4 porque shell/PerfilSheet.js (línea ~671 del monolito) también lo
// necesita para mostrar el pill de rol del usuario en el sheet de perfil, y
// las fases previas no lo habían extraído todavía. Cuando la fase que
// module-ice la página de Base de Datos llegue, debe importar este mismo
// export en vez de redeclarar el objeto.
export const ROL_LABELS = {
  admin:'Administrador', supervisor:'Supervisor', operador:'Operador', consulta:'Consulta',
  guarda_bodega:'Guarda - Bodega', guarda_peatonal:'Guarda - Peatonal', guarda_vehicular:'Guarda - Vehicular',
  recorredor_externo:'Recorredor Externo', coordinador:'Coordinador',
};

// Promovidas aquí en la Fase 5 (lote 7, paso 0) desde
// pages/muelles/MuelleDetallePanel.js, donde habían quedado duplicadas
// temporalmente como desviación documentada (ver historial de ese archivo)
// porque tanto Muelles como Proveedores (DetalleTiempos) las necesitan.
// Ahora que Proveedores también se está modularizando, este es su lugar
// definitivo como fuente única -- MuelleDetallePanel.js,
// LogisticaInversaSection.js y los componentes de pages/proveedores/ las
// importan desde acá.

// Formatea un campo TIME ("HH:MM:SS" o "HH:MM") a "HH:MM" para mostrar en
// cualquier línea de tiempo de la app.
export const hhmmT = t => t ? String(t).slice(0,5) : null;

// Render de los "pasos" de una línea de tiempo (círculo+icono, conector
// vertical, título/hora/desc). `pasos`: [{icon,titulo,hora,desc}].
export function LineaTiempoPasos({pasos}){
  return h('div',{style:{display:'flex',flexDirection:'column'}},
    pasos.map((p,i)=>{
      const hecho = !!p.hora;
      const esUltimo = i===pasos.length-1;
      return h('div',{key:p.titulo,style:{display:'flex',gap:10}},
        h('div',{style:{display:'flex',flexDirection:'column',alignItems:'center',flexShrink:0}},
          h('div',{style:{
            width:26,height:26,borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,
            background:hecho?'#d1fae5':'#f1f5f9',
            border:'1.5px solid '+(hecho?'var(--green)':'var(--border)'),
            color:hecho?'var(--green)':'var(--slate)'
          }},h(Ico,{n:p.icon,s:13})),
          !esUltimo&&h('div',{style:{width:2,flex:1,minHeight:18,background:hecho?'var(--green)':'var(--border)',margin:'2px 0'}})
        ),
        h('div',{style:{flex:1,paddingBottom:esUltimo?0:14,minWidth:0}},
          h('div',{style:{display:'flex',alignItems:'baseline',justifyContent:'space-between',gap:8,flexWrap:'wrap'}},
            h('span',{style:{fontWeight:700,fontSize:12.5,color:hecho?'var(--text)':'var(--slate)'}},p.titulo),
            h('span',{className:'pill '+(hecho?'pill-green':'pill-slate'),style:{fontWeight:700}},p.hora||'—')
          ),
          h('p',{style:{fontSize:11,color:'var(--slate)',marginTop:2}},p.desc)
        )
      );
    })
  );
}
