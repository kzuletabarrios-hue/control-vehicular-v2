// ── ESTADÍSTICAS PANEL (pestaña "Estadísticas", estilo Power BI) ──
// Archivo nuevo (rama dashboard-estadisticas). Consume
// GET /dashboard/estadisticas?fecha_desde&fecha_hasta según el contrato
// exacto de Jorge (docs/estadisticas_contrato.md) vía el cliente `api`
// existente -- no se toca backend/ en absoluto.
//
// Se monta bajo demanda: HomePage.js solo lo renderiza cuando
// tab==='estadisticas', así que su primer fetch ocurre "al abrir la
// pestaña" (no hay polling de fondo -- a diferencia del resumen de Home,
// que sí usa useVisibilityPolling cada 120s). El refresco posterior es
// manual vía el botón "Actualizar" o al cambiar de rango rápido.
//
// Chart.js 4 se carga bajo demanda (inyección dinámica de <script>, no en
// el <head> de index.html) para no pesarle a los roles que nunca abren
// esta pestaña (guardas de puesto, recorredor externo) -- ver loadChartJs()
// más abajo. Cada gráfica destruye su instancia anterior de Chart antes de
// crear una nueva y al desmontar (ver ChartCanvas), para no acumular fugas
// de memoria al cambiar de rango o de pestaña repetidamente.
//
// Depende de React como global UMD, igual que el resto de la app -- no se
// importa como módulo ES.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { fmtDate, fechaValida, today, ahoraHora } from '../core/utils.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { Alert } from '../shared/Alert.js';

const { useState, useEffect, useRef } = React;
const h = React.createElement;

// ── Paleta sobria y consistente (Power BI look), definida una sola vez ──
// Reutiliza el espíritu de los colores ya usados en StatCard/HomePage
// (navy, amber, purple, green, cyan) para no introducir una paleta ajena
// al resto de la app.
const COLORS = {
  flota:          '#1e4570', // navy3, mismo tono que StatCard "Flota hoy"
  proveedores:    '#d97706', // mismo tono que StatCard "Proveedores hoy"
  acceso:         '#7c3aed', // mismo tono que StatCard "Acceso hoy"
  visitantes:     '#059669', // mismo tono que StatCard "Visitantes hoy"
  muelleProm:     '#0891b2', // mismo tono que StatCard "En muelle"
  muelleMed:      '#64748b',
  ruta:           '#1e4570',
  pallets:        '#1e4570',
  contenedores:   '#d97706',
  selloSalida:    '#059669',
  selloEntrada:   '#0891b2',
};

// ── Carga bajo demanda de Chart.js (UMD, auto-registra todos los
// controladores/escalas). Se guarda la promesa a nivel de módulo para que
// una segunda visita a la pestaña dentro de la misma sesión no vuelva a
// descargar el script. ──
const CHART_JS_URL = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js';
let _chartJsPromise = null;
function loadChartJs(){
  if(window.Chart) return Promise.resolve();
  if(_chartJsPromise) return _chartJsPromise;
  _chartJsPromise = new Promise((resolve,reject)=>{
    const s = document.createElement('script');
    s.src = CHART_JS_URL;
    s.async = true;
    s.onload = ()=>resolve();
    s.onerror = ()=>{ _chartJsPromise = null; reject(new Error('No se pudo cargar el módulo de gráficas. Verifica tu conexión e intenta de nuevo.')); };
    document.head.appendChild(s);
  });
  return _chartJsPromise;
}

// Suma días fuera de la zona horaria del navegador de forma segura: parte
// de mediodía local (mismo truco que fmtDate en core/utils.js) para que
// sumar/restar días con setDate() nunca "brinque" de fecha por un desfase
// de horas -- Colombia no tiene horario de verano, pero el navegador del
// usuario podría estar en cualquier zona horaria.
const _addDays = (isoDate, delta) => {
  const d = new Date(isoDate+'T12:00:00');
  d.setDate(d.getDate()+delta);
  const p = n=>String(n).padStart(2,'0');
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
};
const _diffDias = (a,b) => Math.round((new Date(b+'T12:00:00') - new Date(a+'T12:00:00'))/86400000);

// Traduce el detail crudo del 400 del endpoint (fecha_desde>fecha_hasta,
// rango>366 días, formato inválido) a texto legible. Mismo patrón que
// textoErrorAnulacion en core/utils.js: api._fetch descarta el status code,
// así que solo tenemos el texto del body.
function textoErrorEstadisticas(e){
  try{
    const parsed = JSON.parse(e.message);
    if(typeof parsed.detail === 'string') return parsed.detail;
  }catch(_){ /* body no era JSON, se usa el mensaje crudo abajo */ }
  return e.message || 'No se pudieron cargar las estadísticas. Intenta de nuevo.';
}

const fmtMin = v => v==null ? '—' : `${v} min`;
const fmtPct = v => v==null ? '—' : `${v}%`;
// n_validos/n_viajes siempre viaja junto al promedio/mediana (contrato,
// sección 3, nota para Laura): se usa para decidir el subtítulo de
// confianza de la cifra en vez de mostrar un promedio "pelado" calculado
// sobre 1-2 muestras sin contexto.
const confMuestras = n => {
  if(!n) return 'Sin datos válidos en el rango';
  if(n<5) return `${n} muestra${n===1?'':'s'} · dato poco representativo`;
  return `${n} muestras`;
};

// ── KPI card: número grande + label corta, estilo Power BI ──
function Kpi({label, icon, color, value, sub}){
  return h('div',{className:'kpi-card'},
    h('div',{style:{display:'flex',alignItems:'center',gap:6}},
      h('span',{style:{color, display:'flex'}}, h(Ico,{n:icon,s:13})),
      h('span',{className:'kpi-lbl'},label)
    ),
    h('div',{className:'kpi-val',style:{color}}, value),
    sub&&h('div',{className:'kpi-sub'},sub)
  );
}

// ── Tarjeta contenedora de cada gráfica: título pequeño en mayúsculas +
// estado vacío explícito ("Sin datos en el rango", nunca un gráfico plano
// en 0 que confunda "no hubo actividad" con "no hay dato"). ──
function ChartCard({title, empty, full, children}){
  return h('div',{className:'chart-card'+(full?' chart-card-full':'')},
    h('p',{className:'chart-card-ttl'},title),
    empty ? h('div',{className:'chart-empty'},'Sin datos en el rango') : children
  );
}

// ── Canvas + ciclo de vida de una instancia de Chart.js. Destruye la
// instancia anterior antes de crear una nueva y al desmontar (cambio de
// rango, cambio de pestaña) para no acumular fugas de memoria. Solo se
// reconstruye cuando cambia `stats` (nueva respuesta del endpoint) o
// `ready` (Chart.js recién terminó de cargar) -- no en cada render. ──
function ChartCanvas({buildConfig, stats, ready, height=220}){
  const canvasRef = useRef(null);
  const chartRef  = useRef(null);
  useEffect(()=>{
    if(!ready || !stats || !canvasRef.current || !window.Chart) return;
    const cfg = buildConfig(stats);
    chartRef.current = new window.Chart(canvasRef.current, cfg);
    return ()=>{
      if(chartRef.current){ chartRef.current.destroy(); chartRef.current = null; }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[stats, ready]);
  return h('div',{style:{position:'relative',height}}, h('canvas',{ref:canvasRef}));
}

// ── Configs de Chart.js (funciones puras data → config), una por gráfica ──
function buildTendenciaConfig(stats){
  const rows = stats.tendencia_diaria||[];
  return {
    type:'line',
    data:{
      labels:rows.map(r=>fmtDate(r.fecha)),
      datasets:[
        {label:'Flota propia',      data:rows.map(r=>r.flota),          borderColor:COLORS.flota,       backgroundColor:COLORS.flota,       tension:.25, pointRadius:2},
        {label:'Proveedores',       data:rows.map(r=>r.proveedores),    borderColor:COLORS.proveedores, backgroundColor:COLORS.proveedores, tension:.25, pointRadius:2},
        {label:'Control de acceso', data:rows.map(r=>r.control_acceso), borderColor:COLORS.acceso,      backgroundColor:COLORS.acceso,      tension:.25, pointRadius:2},
        {label:'Visitantes',        data:rows.map(r=>r.visitantes),     borderColor:COLORS.visitantes,  backgroundColor:COLORS.visitantes,  tension:.25, pointRadius:2},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index', intersect:false},
      plugins:{legend:{position:'bottom'}},
      scales:{ y:{beginAtZero:true, ticks:{precision:0}}, x:{grid:{display:false}} }
    }
  };
}

function buildHorasConfig(stats){
  const rows = stats.ingresos_por_hora||[];
  return {
    type:'bar',
    data:{
      labels:rows.map(r=>String(r.hora).padStart(2,'0')+'h'),
      datasets:[
        {label:'Control de acceso',     data:rows.map(r=>r.control_acceso),     backgroundColor:COLORS.acceso},
        {label:'Proveedores',           data:rows.map(r=>r.proveedores),        backgroundColor:COLORS.proveedores},
        {label:'Flota (salidas CEDI)',  data:rows.map(r=>r.flota_salidas_cedi), backgroundColor:COLORS.flota},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'bottom'}},
      scales:{ y:{beginAtZero:true, ticks:{precision:0}}, x:{grid:{display:false}} }
    }
  };
}

function buildMuelleConfig(stats){
  const rows = stats.tiempo_muelle_proveedores?.por_dia||[];
  return {
    type:'line',
    data:{
      labels:rows.map(r=>fmtDate(r.fecha)),
      datasets:[
        // spanGaps:false a propósito: un día con n_validos=0 viene en null
        // (contrato, sección 3) y debe verse como un hueco en la línea, no
        // como "0 minutos" (dato falso) ni interpolado silenciosamente.
        {label:'Promedio (min)', data:rows.map(r=>r.promedio_minutos), borderColor:COLORS.muelleProm, backgroundColor:COLORS.muelleProm, spanGaps:false, tension:.25, pointRadius:2},
        {label:'Mediana (min)',  data:rows.map(r=>r.mediana_minutos),  borderColor:COLORS.muelleMed,  backgroundColor:COLORS.muelleMed,  spanGaps:false, tension:.25, pointRadius:2, borderDash:[4,3]},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index', intersect:false},
      plugins:{
        legend:{position:'bottom'},
        tooltip:{callbacks:{label:ctx=>`${ctx.dataset.label}: ${ctx.parsed.y==null?'sin datos':ctx.parsed.y+' min'}`}}
      },
      scales:{ y:{beginAtZero:true}, x:{grid:{display:false}} }
    }
  };
}

function buildTopPlacasConfig(stats){
  const rows = stats.tiempo_ruta_flota?.top_placas||[];
  return {
    type:'bar',
    data:{
      labels:rows.map(r=>r.placa),
      datasets:[{label:'Tiempo promedio de ruta (min)', data:rows.map(r=>r.promedio_minutos), backgroundColor:COLORS.ruta}]
    },
    options:{
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{display:false},
        tooltip:{callbacks:{afterLabel:ctx=>{
          const r = rows[ctx.dataIndex];
          return `Mediana: ${r.mediana_minutos} min · ${r.n_viajes} viaje${r.n_viajes===1?'':'s'}`;
        }}}
      },
      scales:{ x:{beginAtZero:true} }
    }
  };
}

function buildCargaConfig(stats){
  const rows = stats.carga_despachada_por_dia||[];
  return {
    type:'bar',
    data:{
      labels:rows.map(r=>fmtDate(r.fecha)),
      datasets:[
        {label:'Pallets',      data:rows.map(r=>r.pallets),      backgroundColor:COLORS.pallets},
        {label:'Contenedores', data:rows.map(r=>r.contenedores), backgroundColor:COLORS.contenedores},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'bottom'}},
      scales:{ y:{beginAtZero:true, ticks:{precision:0}}, x:{grid:{display:false}} }
    }
  };
}

function buildSellosConfig(stats){
  const rows = stats.cumplimiento_sellos?.por_dia||[];
  return {
    type:'line',
    data:{
      labels:rows.map(r=>fmtDate(r.fecha)),
      datasets:[
        {label:'% sello salida',  data:rows.map(r=>r.pct_sello_salida),  borderColor:COLORS.selloSalida,  backgroundColor:COLORS.selloSalida,  spanGaps:false, tension:.25, pointRadius:2},
        {label:'% sello entrada', data:rows.map(r=>r.pct_sello_entrada), borderColor:COLORS.selloEntrada, backgroundColor:COLORS.selloEntrada, spanGaps:false, tension:.25, pointRadius:2, borderDash:[4,3]},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index', intersect:false},
      plugins:{
        legend:{position:'bottom'},
        tooltip:{callbacks:{label:ctx=>`${ctx.dataset.label}: ${ctx.parsed.y==null?'sin viajes':ctx.parsed.y+'%'}`}}
      },
      scales:{ y:{beginAtZero:true, max:100}, x:{grid:{display:false}} }
    }
  };
}

export function EstadisticasPanel(){
  const [chartReady,setChartReady] = useState(!!window.Chart);
  const [chartError,setChartError] = useState('');
  useEffect(()=>{
    if(chartReady) return;
    loadChartJs().then(()=>setChartReady(true)).catch(e=>setChartError(e.message));
  },[]); // eslint-disable-line react-hooks/exhaustive-deps

  const [rango,setRango]   = useState('30d'); // 'hoy' | '7d' | '30d' | 'custom'
  const [desde,setDesde]   = useState(()=>_addDays(today(),-29));
  const [hasta,setHasta]   = useState(()=>today());
  const [customDesde,setCustomDesde] = useState('');
  const [customHasta,setCustomHasta] = useState('');
  const [rangoError,setRangoError]   = useState('');

  const [stats,setStats]       = useState(null);
  const [loading,setLoading]   = useState(false);
  const [error,setError]       = useState('');
  const [lastUpdated,setLastUpdated] = useState('');

  const cargar = (d,h)=>{
    setError('');
    setLoading(true);
    api.get(`/dashboard/estadisticas?fecha_desde=${d}&fecha_hasta=${h}`)
      .then(res=>{ setStats(res); setLastUpdated(ahoraHora()); })
      .catch(e=>setError(textoErrorEstadisticas(e)))
      .finally(()=>setLoading(false));
  };

  // Carga inicial al abrir la pestaña (se monta una sola vez, HomePage
  // desmonta este componente al salir de tab==='estadisticas'). No hay
  // polling: los refrescos posteriores son manuales (chip de rango rápido
  // o botón "Actualizar").
  useEffect(()=>{ cargar(desde,hasta); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const aplicarRangoRapido = id=>{
    setRango(id);
    setRangoError('');
    const h = today();
    const d = id==='hoy' ? h : id==='7d' ? _addDays(h,-6) : _addDays(h,-29);
    setDesde(d); setHasta(h);
    cargar(d,h);
  };

  const aplicarPersonalizado = ()=>{
    if(!customDesde||!customHasta||!fechaValida(customDesde)||!fechaValida(customHasta)){
      setRangoError('Selecciona ambas fechas.'); return;
    }
    if(customDesde>customHasta){
      setRangoError("La fecha 'desde' no puede ser mayor a 'hasta'."); return;
    }
    if(_diffDias(customDesde,customHasta)>366){
      setRangoError('El rango máximo permitido es de 366 días.'); return;
    }
    setRangoError('');
    setDesde(customDesde); setHasta(customHasta);
    cargar(customDesde,customHasta);
  };

  const actualizar = ()=> rango==='custom' ? aplicarPersonalizado() : cargar(desde,hasta);

  const chips = [
    {id:'hoy',    label:'Hoy'},
    {id:'7d',     label:'7 días'},
    {id:'30d',    label:'30 días'},
    {id:'custom', label:'Personalizado'},
  ];

  // Estados vacíos por sección (contrato: relleno con 0 en A/C/E/F, así que
  // "todo en 0" sí significa "sin actividad" -- distinto de B/D, donde el
  // criterio es n_validos/top_placas.length, nunca el valor en sí).
  const tendenciaVacia  = !stats || (stats.tendencia_diaria||[]).every(r=>!r.flota&&!r.proveedores&&!r.control_acceso&&!r.visitantes);
  const horasVacio      = !stats || (stats.ingresos_por_hora||[]).every(r=>!r.control_acceso&&!r.proveedores&&!r.flota_salidas_cedi);
  const muelleVacio     = !stats || (stats.tiempo_muelle_proveedores?.global?.n_validos||0)===0;
  const topPlacasVacio  = !stats || (stats.tiempo_ruta_flota?.top_placas||[]).length===0;
  const cargaVacia      = !stats || (stats.carga_despachada_por_dia||[]).every(r=>!r.pallets&&!r.contenedores);
  const sellosVacio     = !stats || (stats.cumplimiento_sellos?.global?.total_viajes||0)===0;

  return h('div',{className:'pad'},
    h('p',{className:'sec-ttl'},h(Ico,{n:'barChart',s:12}),' Estadísticas'),

    // ── Filtros ──
    h('div',{className:'fcard'},
      h('div',{style:{display:'flex',flexWrap:'wrap',gap:7,alignItems:'center'}},
        chips.map(c=>h('button',{
          key:c.id,
          className:'range-chip',
          style:{
            background:rango===c.id?'var(--navy2)':'none',
            color:rango===c.id?'#fff':'var(--slate)',
            borderColor:rango===c.id?'var(--navy2)':'var(--border)'
          },
          onClick:()=> c.id==='custom' ? (setRango('custom'), setRangoError('')) : aplicarRangoRapido(c.id)
        }, c.label)),
        h('button',{
          className:'btn-outline',
          style:{marginLeft:'auto'},
          onClick:actualizar,
          disabled:loading
        }, h(Ico,{n:'refresh',s:14}), loading?'Actualizando…':'Actualizar')
      ),
      rango==='custom'&&h('div',{className:'fgrid2',style:{marginTop:10}},
        h('div',{className:'fg'},
          h('label',null,'Desde'),
          h('input',{type:'date',value:customDesde,max:customHasta||undefined,onChange:e=>setCustomDesde(e.target.value)})
        ),
        h('div',{className:'fg'},
          h('label',null,'Hasta'),
          h('input',{type:'date',value:customHasta,min:customDesde||undefined,onChange:e=>setCustomHasta(e.target.value)})
        )
      ),
      rango==='custom'&&h('button',{className:'btn-primary',style:{marginTop:10},onClick:aplicarPersonalizado},'Aplicar rango'),
      rangoError&&h('p',{style:{color:'var(--red)',fontSize:11,marginTop:6,fontWeight:600}},rangoError),
      stats&&h('p',{style:{fontSize:10,color:'var(--slate)',marginTop:8}},
        `Mostrando ${fmtDate(stats.fecha_desde)} — ${fmtDate(stats.fecha_hasta)}`,
        lastUpdated?` · Actualizado a las ${lastUpdated}`:''
      )
    ),

    chartError&&h(Alert,{type:'warn',msg:chartError}),
    error&&h(Alert,{type:'err',msg:error}),

    !stats&&loading&&h('div',{style:{padding:'40px 14px',textAlign:'center'}}, h(LoadingDots)),

    stats&&h('div',null,
      // ── KPIs ──
      h('div',{className:'kpi-grid',style:{marginBottom:14}},
        h(Kpi,{label:'Flota propia',      icon:'truck',     color:COLORS.flota,       value:(stats.tendencia_diaria||[]).reduce((a,r)=>a+r.flota,0)}),
        h(Kpi,{label:'Proveedores',       icon:'package',   color:COLORS.proveedores, value:(stats.tendencia_diaria||[]).reduce((a,r)=>a+r.proveedores,0)}),
        h(Kpi,{label:'Control de acceso', icon:'userCheck', color:COLORS.acceso,      value:(stats.tendencia_diaria||[]).reduce((a,r)=>a+r.control_acceso,0)}),
        h(Kpi,{label:'Visitantes',        icon:'users',     color:COLORS.visitantes,  value:(stats.tendencia_diaria||[]).reduce((a,r)=>a+r.visitantes,0)}),
        h(Kpi,{label:'Tiempo prom. en muelle', icon:'clock', color:COLORS.muelleProm,
          value:fmtMin(stats.tiempo_muelle_proveedores?.global?.promedio_minutos),
          sub:confMuestras(stats.tiempo_muelle_proveedores?.global?.n_validos||0)}),
        h(Kpi,{label:'Tiempo prom. ruta flota', icon:'truck', color:COLORS.ruta,
          value:fmtMin(stats.tiempo_ruta_flota?.global?.promedio_minutos),
          sub:confMuestras(stats.tiempo_ruta_flota?.global?.n_validos||0)}),
        h(Kpi,{label:'% sello salida', icon:'checkCircle', color:COLORS.selloSalida,
          value:fmtPct(stats.cumplimiento_sellos?.global?.pct_sello_salida),
          sub:stats.cumplimiento_sellos?.global?.total_viajes ? `${stats.cumplimiento_sellos.global.con_sello_salida}/${stats.cumplimiento_sellos.global.total_viajes} viajes` : 'Sin viajes en el rango'}),
        h(Kpi,{label:'% sello entrada', icon:'checkCircle', color:COLORS.selloEntrada,
          value:fmtPct(stats.cumplimiento_sellos?.global?.pct_sello_entrada),
          sub:stats.cumplimiento_sellos?.global?.viajes_con_llegada ? `${stats.cumplimiento_sellos.global.con_sello_entrada}/${stats.cumplimiento_sellos.global.viajes_con_llegada} viajes con llegada` : 'Sin viajes con llegada en el rango'})
      ),

      chartError&&!chartReady&&h('div',{style:{padding:'20px 0',textAlign:'center',color:'var(--slate)',fontSize:12}},
        'Las gráficas no están disponibles ahora mismo, pero los KPI de arriba siguen siendo correctos.'
      ),
      !chartReady&&!chartError&&h('div',{style:{padding:'20px 0',textAlign:'center'}}, h(LoadingDots)),

      chartReady&&h('div',{className:'chart-grid'},
        h(ChartCard,{title:'Tendencia diaria por módulo', full:true, empty:tendenciaVacia},
          h(ChartCanvas,{buildConfig:buildTendenciaConfig, stats, ready:chartReady})
        ),
        h(ChartCard,{title:'Ingresos por hora del día', full:true, empty:horasVacio},
          h(ChartCanvas,{buildConfig:buildHorasConfig, stats, ready:chartReady})
        ),
        h(ChartCard,{title:'Tiempo en muelle (promedio y mediana por día)', empty:muelleVacio},
          h(ChartCanvas,{buildConfig:buildMuelleConfig, stats, ready:chartReady})
        ),
        h(ChartCard,{title:'Flota · tiempo de ruta por placa (top 10)', empty:topPlacasVacio},
          h(ChartCanvas,{buildConfig:buildTopPlacasConfig, stats, ready:chartReady, height:260})
        ),
        h(ChartCard,{title:'Flota · pallets y contenedores por día', empty:cargaVacia},
          h(ChartCanvas,{buildConfig:buildCargaConfig, stats, ready:chartReady})
        ),
        h(ChartCard,{title:'Flota · cumplimiento de sellos por día', empty:sellosVacio},
          h(ChartCanvas,{buildConfig:buildSellosConfig, stats, ready:chartReady})
        )
      )
    )
  );
}
