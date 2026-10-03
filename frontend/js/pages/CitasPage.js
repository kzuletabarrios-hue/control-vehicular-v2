// ── CITAS PAGE (Fase 3, solo lectura) ──
// Extraído de frontend/index.html (líneas 6292-6410, función CitasPage del
// <script> monolítico, marcada con el comentario "/* ── CITAS (Fase 3, solo
// lectura) ── */", justo antes de "/* ── APP ROOT ── */"). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado -- este módulo es una copia autocontenida, lista para que la
// Fase 6 lo importe cuando quede conectado vía <script type="module">.
//
// Hallazgo: esta página es standalone (módulo de solo consulta del estado
// de citas del día, con export a Excel de "proveedores que no llegaron"),
// DISTINTA de las citas que se gestionan dentro de ProveedoresPage (carga
// del archivo del WMS y configuración de tolerancia) -- se confirmó leyendo
// el código real: no vive dentro de la sección de proveedores, es su propia
// función top-level en el monolito, tal como anticipaba el encargo.
//
// Importa Ico (core/icons.js), api (core/api-client.js), today, fmtDateHora,
// puede y playAlertSound (core/utils.js), useVisibilityPolling
// (core/hooks.js) y los componentes compartidos Alert, LoadingDots
// (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { today, fmtDateHora, puede, playAlertSound } from '../core/utils.js';
import { useVisibilityPolling } from '../core/hooks.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';

const { useState, useEffect, useCallback, useRef } = React;
const h = React.createElement;

// Ajuste de la tolerancia (minutos después del fin de la franja antes de
// considerar tarde al proveedor). Solo para quien tiene citas:write (hoy,
// admin). El backend aplica el valor también a las citas ya cargadas de hoy
// en adelante.
function EditarTolerancia({actual,onGuardado}){
  const [valor,setValor] = useState(String(actual));
  const [estado,setEstado] = useState(null);
  const [guardando,setGuardando] = useState(false);
  useEffect(()=>setValor(String(actual)),[actual]);
  const guardar = async()=>{
    const n = Number(valor);
    if(!Number.isInteger(n)||n<0||n>240) return setEstado({type:'err',msg:'Escribe un número de minutos entre 0 y 240.'});
    setGuardando(true);
    try{
      const r = await api.put('/citas/config',{tolerancia_min_default:n});
      setEstado({type:'ok',msg:`Tolerancia guardada: ${n} min. Se aplicó a ${r.citas_actualizadas??0} cita(s) de hoy en adelante.`});
      onGuardado&&onGuardado();
    }catch(e){ setEstado({type:'err',msg:e.message||'No se pudo guardar'}); }
    finally{ setGuardando(false); }
  };
  return h('div',{style:{marginTop:10,display:'flex',flexDirection:'column',gap:6}},
    h('label',{htmlFor:'tolerancia-min',style:{fontSize:11,fontWeight:700,color:'var(--slate)'}},'Tolerancia después del fin de la franja (minutos)'),
    h('div',{style:{display:'flex',gap:8,alignItems:'center'}},
      h('input',{id:'tolerancia-min',type:'number',min:0,max:240,step:5,value:valor,onChange:e=>setValor(e.target.value),style:{width:90}}),
      h('button',{onClick:guardar,disabled:guardando||String(actual)===valor,style:{background:'var(--navy2)',color:'#fff',border:'none',borderRadius:8,padding:'8px 14px',cursor:'pointer',fontWeight:700,fontSize:12,fontFamily:'inherit',opacity:(guardando||String(actual)===valor)?.5:1}},guardando?'Guardando...':'Guardar')
    ),
    h('p',{style:{fontSize:11,color:'var(--slate)',margin:0}},`Ejemplo: cita de 7:00 a 8:00 con ${Number(valor)||0} min → tarde desde las ${(()=>{const t=8*60+(Number(valor)||0);return String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');})()}.`),
    estado&&h(Alert,{...estado,onClose:()=>setEstado(null)})
  );
}

export function CitasPage({user}){
  const [citas,setCitas]   = useState([]);
  const [config,setConfig] = useState(null);
  const [alertasCitas,setAlertasCitas] = useState(null);
  const [loading,setLoading] = useState(true);
  const [error,setError]     = useState(null);
  // Rango de fechas para el export (Sección "proveedores que no llegaron"),
  // independiente del tablero de hoy de abajo, que sigue fijo a today().
  const [fi,setFi] = useState(today());
  const [ff,setFf] = useState(today());

  const load = useCallback(()=>{
    Promise.all([
      api.get(`/citas?fecha=${today()}`),
      api.get('/citas/config'),
      api.get('/citas/alertas'),
    ]).then(([listado,cfg,al])=>{
      setCitas(Array.isArray(listado)?listado:(listado.items||[]));
      setConfig(cfg);
      setAlertasCitas(al);
      setError(null);
    }).catch(()=>setError('No se pudo cargar el estado de las citas'))
      .finally(()=>setLoading(false));
  },[]);
  // Igual que Muelles: tablero operativo que el coordinador consulta
  // seguido, así que se refresca cada minuto y se pausa en background.
  useVisibilityPolling(load, 60000, [load]);

  // Suena una alerta cuando a una cita programada le falten <=5 min para su
  // hora de inicio (alertasCitas.por_iniciar). Una sola vez por orden de
  // compra -- mismo patrón que MuellesPage en citas-muelles-cedi-r10.
  const avisadosInicio = useRef(new Set());
  useEffect(()=>{
    if(!alertasCitas) return;
    const vistosIds = new Set();
    (alertasCitas.por_iniciar||[]).forEach(c=>{
      vistosIds.add(c.numero_orden_compra);
      if(!avisadosInicio.current.has(c.numero_orden_compra)){
        avisadosInicio.current.add(c.numero_orden_compra);
        playAlertSound();
      }
    });
    avisadosInicio.current.forEach(id=>{ if(!vistosIds.has(id)) avisadosInicio.current.delete(id); });
  },[alertasCitas]);

  const hhmm = t => t ? String(t).slice(0,5) : '—';

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('div',{className:'header-brand'},h('h1',null,'Citas'),h('span',null,'Vista de consulta'))
      )
    ),
    h('div',{style:{padding:'10px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)'}},
      h('p',{style:{fontSize:11,color:'var(--slate)'}},
        'La carga del archivo del WMS se hace desde Proveedores → Citas del día. La tolerancia de citas se configura desde este módulo, solo para roles con permiso de escritura (hoy, administración) — aquí puedes consultar el estado del día.'
      ),
      !loading&&!error&&config&&h('span',{className:'pill pill-slate',style:{marginTop:6,display:'inline-block'}},
        `Tolerancia vigente: ${config.tolerancia_min_default} min`
      ),
      !loading&&!error&&config&&puede(user,'citas','write')&&h(EditarTolerancia,{actual:config.tolerancia_min_default,onGuardado:load})
    ),
    puede(user,'citas','export')&&h('div',{style:{display:'flex',gap:8,padding:'8px 14px',flexWrap:'wrap',alignItems:'flex-end',background:'var(--white)',borderBottom:'1px solid var(--border)'}},
      h('div',{style:{display:'flex',flexDirection:'column',gap:2}},h('label',{style:{fontSize:10,color:'var(--slate)',fontWeight:600}},'Desde'),h('input',{type:'date',value:fi,onChange:e=>setFi(e.target.value),style:{fontSize:12}})),
      h('div',{style:{display:'flex',flexDirection:'column',gap:2}},h('label',{style:{fontSize:10,color:'var(--slate)',fontWeight:600}},'Hasta'),h('input',{type:'date',value:ff,onChange:e=>setFf(e.target.value),style:{fontSize:12}})),
      h('button',{onClick:()=>api.exportar('citas',fi,ff),style:{background:'none',border:'1.5px solid var(--slate)',color:'var(--slate)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
        h(Ico,{n:'download',s:14}),' Excel · No llegaron'
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      error&&h(Alert,{type:'err',msg:error,onClose:()=>setError(null)}),
      loading?h(LoadingDots):h(React.Fragment,null,

        alertasCitas&&h('div',{style:{display:'flex',flexDirection:'column',gap:8,marginBottom:14}},
          h('div',{className:'alert alert-err',style:{marginBottom:0}},
            h(Ico,{n:'alert',s:14}),
            h('span',null,`${alertasCitas.vencidas.length} cita${alertasCitas.vencidas.length===1?'':'s'} vencida${alertasCitas.vencidas.length===1?'':'s'}`)
          ),
          h('div',{className:'alert alert-warn',style:{marginBottom:0}},
            h(Ico,{n:'alert',s:14}),
            h('span',null,`${alertasCitas.por_vencer.length} por vencer (≤10 min)`)
          ),
          h('div',{className:'alert',style:{marginBottom:0,background:'#dbeafe',color:'#1d4ed8',border:'1px solid #93c5fd'}},
            h(Ico,{n:'calendar',s:14}),
            h('span',null,`${alertasCitas.por_iniciar.length} por iniciar (≤5 min)`)
          ),
          h('p',{style:{fontSize:10,color:'var(--slate)'}},
            alertasCitas.archivo_hoy
              ? `Archivo del WMS cargado hoy${alertasCitas.hora_carga?` — ${fmtDateHora(alertasCitas.hora_carga)}`:''}.`
              : 'Todavía no se ha cargado el archivo del WMS para hoy.'
          )
        ),

        citas.length===0
          ? h('div',{className:'empty'},h(Ico,{n:'calendar',s:44}),h('p',null,'No hay citas cargadas para hoy'))
          : h('div',{style:{overflowX:'auto'}},
              h('table',{className:'preview-table'},
                h('thead',null,h('tr',null,
                  h('th',null,'Hora'),h('th',null,'O. Compra'),h('th',null,'Proveedor'),h('th',null,'Carga'),h('th',null,'Pallets')
                )),
                h('tbody',null,
                  citas.map(c=>h('tr',{key:c.id},
                    h('td',null,`${hhmm(c.hora_cita_inicio)} – ${hhmm(c.hora_cita_fin)}`),
                    h('td',null,c.numero_orden_compra||'—'),
                    h('td',null,c.proveedor_nombre||'—'),
                    h('td',null,c.descripcion_carga||'—'),
                    h('td',null,c.cantidad_pallets||'—')
                  ))
                )
              )
            )
      )
    )
  );
}
