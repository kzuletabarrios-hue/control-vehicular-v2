// ── HOME PAGE ──
// Extraído de frontend/index.html (líneas 825-1010, función HomePage del
// <script> monolítico, justo antes de StatCard/DetalleLista). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado (ver notas de la Fase 2 del plan de migración) -- este módulo es
// una copia autocontenida, lista para que la Fase 6 lo importe cuando quede
// conectado vía <script type="module">.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// useVisibilityPolling (core/hooks.js), puede (core/utils.js) y los
// componentes compartidos StatCard, DetalleLista, LoadingDots (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { useVisibilityPolling } from '../core/hooks.js';
import { puede, fmtDate } from '../core/utils.js';
import { StatCard } from '../shared/StatCard.js';
import { DetalleLista } from '../shared/DetalleLista.js';
import { LoadingDots } from '../shared/LoadingDots.js';

const { useState, useEffect } = React;
const h = React.createElement;

export function HomePage({setPage,user}){
  const [resumen,setResumen] = useState(null);
  const [tab,setTab]         = useState('dashboard');
  const [showMuelle,setShowMuelle] = useState(false);
  const [showFlotaHoy,setShowFlotaHoy] = useState(false);
  const [showEnRuta,setShowEnRuta] = useState(false);
  const [showAccesoHoy,setShowAccesoHoy] = useState(false);
  const [showSinSalida,setShowSinSalida] = useState(false);
  const [showProvHoy,setShowProvHoy] = useState(false);
  const [showVisitantesHoy,setShowVisitantesHoy] = useState(false);
  const [showAccesoDiasAnt,setShowAccesoDiasAnt] = useState(false);
  const fechaHoy = new Intl.DateTimeFormat('es-CO',{timeZone:'America/Bogota',weekday:'long',day:'numeric',month:'long'}).format(new Date());
  const rol = user?.rol||'';
  const isAdmin = ['admin','supervisor','operador'].includes(rol);
  const isGuardaBodega    = rol==='guarda_bodega';
  const isGuardaPeatonal  = rol==='guarda_peatonal';
  const isGuardaVehicular = rol==='guarda_vehicular';
  const isRecorredor      = rol==='recorredor_externo';
  const isCoordinador     = rol==='coordinador';

  const cargar = ()=>api.get('/dashboard/resumen').then(setResumen).catch(()=>{});
  // Home es la pantalla menos operativa de las 4 con polling: 2 min y se
  // pausa en background (pestaña oculta / pantalla bloqueada).
  useVisibilityPolling(cargar, 120000, []);

  const allMods = [
    {id:'flota', label:'Flota Propia',     desc:'Salidas de vehículos',   cls:'m-flota',icon:'truck',    roles:['admin','supervisor','operador','guarda_bodega','guarda_vehicular','coordinador'],cnt:resumen?.flota?.hoy},
    {id:'prov',  label:'Proveedores',desc:'Vehículos terceros',     cls:'m-prov', icon:'package',  roles:['admin','supervisor','operador','guarda_vehicular','guarda_bodega','coordinador'],cnt:resumen?.proveedores?.hoy},
    {id:'visitavh',label:'Visita Vehicular',desc:'Visitas puntuales en vehículo', cls:'m-visitavh', icon:'truck', roles:['admin','supervisor','operador','guarda_bodega','guarda_vehicular'],cnt:resumen?.visita_vehicular?.hoy},
    {id:'acceso',label:'Control Acceso',   desc:'Entrada/salida personal',cls:'m-acc',  icon:'userCheck',roles:['admin','supervisor','operador','guarda_peatonal','coordinador'],  cnt:resumen?.control_acceso?.hoy},
    {id:'visit', label:'Visitantes',       desc:'Registro de visitas',    cls:'m-vis',  icon:'users',    roles:['admin','supervisor','operador','guarda_peatonal','guarda_vehicular','coordinador'],  cnt:resumen?.visitantes?.hoy},
    {id:'sust',  label:'Sustancias',        desc:'Control de sustancias',  cls:'m-sust', icon:'alert',    roles:['admin','supervisor','operador','guarda_peatonal'],cnt:null},
    {id:'herr',  label:'Herramientas',     desc:'Control de herramientas',cls:'m-herr', icon:'key',      roles:['admin','supervisor','operador','guarda_peatonal'],cnt:null},
    {id:'bd',    label:'Base de Datos',    desc:'Catálogos maestros',     cls:'m-bd',   icon:'database', roles:['admin','supervisor'],cnt:null},
    {id:'carga', label:'Carga Masiva',     desc:'Importar desde Excel',   cls:'m-carga',icon:'upload',   roles:['admin'],cnt:null},
    {id:'reg',       label:'Reportes',    desc:'Historial y Excel',      cls:'m-reg',  icon:'fileText', roles:['admin','supervisor','consulta','operador'],cnt:null},
    {id:'ronda',     label:'Ronda',       desc:'Marcación de puntos',    cls:'m-ronda',icon:'mapPin',   roles:['admin','supervisor','recorredor_externo'],cnt:null},
    {id:'novedades', label:'Novedades',   desc:'Registro de incidencias',cls:'m-nov',  icon:'bell',     roles:['admin','supervisor','recorredor_externo','operador'],cnt:null},
    {id:'rondapanel',label:'Panel Rondero',desc:'Seguimiento de rondas y apoyos', cls:'m-rondapanel',icon:'clock', roles:['admin','supervisor'],cnt:null},
    // Primer tile que gatea por permiso (puede(user,'muelles','read')) en vez de
    // un array `roles` estático -- los demás tiles arriba NO se tocan, siguen
    // gateando por rol. Fase 2 (solo lectura) del tablero real de muelles.
    {id:'muelles',label:'Muelles',desc:'Tablero de ocupación',cls:'m-muelles',icon:'mapPin',permiso:['muelles','read'],cnt:null},
  ];
  const mods = allMods.filter(m=>m.permiso ? puede(user,m.permiso[0],m.permiso[1]) : m.roles.includes(rol));

  const flotaPend  = resumen?.flota?.en_ruta||0;
  const accesoPend = resumen?.control_acceso?.activos_sin_salida||0;
  const pendFlota  = resumen?.pendientes?.flota_sin_llegada||[];
  const pendAcceso = resumen?.pendientes?.acceso_sin_salida||[];

  const showFlotaStats   = isAdmin||isGuardaBodega||isGuardaVehicular||isCoordinador;
  const showAccesoStats  = isAdmin||isGuardaPeatonal||isCoordinador;
  const showProvStats    = isAdmin||isGuardaVehicular||isGuardaBodega||isCoordinador;
  const showDashboard    = !isRecorredor;
  // Indicador gerencial (tiempo de autorregistro por QR): no es una cola
  // operativa del turno, es un dato de consulta ocasional -- solo perfiles
  // con visión gerencial/administrativa (los guardas de puesto no lo necesitan).
  const showTiempoAutoregistro = isAdmin||isCoordinador;

  const [tiempoAutoregistro,setTiempoAutoregistro] = useState(null);
  useEffect(()=>{
    if(!showTiempoAutoregistro) return;
    api.get('/dashboard/tiempo-autorregistro').then(setTiempoAutoregistro).catch(()=>{});
    // Dato lento (cambia con cada autorregistro por QR, no en tiempo real):
    // se carga una sola vez al montar, sin polling.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[showTiempoAutoregistro]);

  const tabBtn = (id,label,icon)=>h('button',{
    onClick:()=>setTab(id),
    style:{flex:1,display:'flex',alignItems:'center',justifyContent:'center',gap:5,padding:'7px 0',borderRadius:20,fontSize:12,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',transition:'all .15s',
      background:tab===id?'var(--navy)':'transparent',
      color:tab===id?'#fff':'var(--slate)',
      borderColor:tab===id?'var(--navy)':'var(--border)'}
  },h(Ico,{n:icon,s:12}),label);

  return h('div',{className:'scroll-body'},
    h('div',{style:{padding:'12px 14px 4px'}},
      h('p',{style:{fontSize:11,color:'var(--slate)',textTransform:'capitalize',fontWeight:500}},fechaHoy)
    ),
    showDashboard&&h('div',{className:'dash-section',style:{display:'flex',gap:6,paddingTop:6,paddingBottom:10}},
      tabBtn('dashboard','Dashboard','clipboard'),
      tabBtn('modulos','Módulos','home')
    ),
    tab==='dashboard'&&showDashboard&&h('div',null,
      resumen&&(showFlotaStats||showAccesoStats||showProvStats)&&h('div',{className:'dash-section'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'clipboard',s:12}),' Resumen de hoy'),
        h('div',{className:'sgrid',style:{marginBottom:4}},
          showFlotaStats&&h(StatCard,{label:'Flota hoy',       value:resumen.flota.hoy,          color:'#1e4570',icon:'truck',active:showFlotaHoy,onClick:()=>setShowFlotaHoy(v=>!v)}),
          showFlotaStats&&h(StatCard,{label:'En ruta',          value:resumen.flota.en_ruta,      color:'#f59e0b',icon:'truck',active:showEnRuta,onClick:()=>setShowEnRuta(v=>!v)}),
          showAccesoStats&&h(StatCard,{label:'Acceso hoy',     value:resumen.control_acceso.hoy, color:'#7c3aed',icon:'userCheck',active:showAccesoHoy,onClick:()=>setShowAccesoHoy(v=>!v)}),
          showAccesoStats&&h(StatCard,{label:'Sin salida',     value:accesoPend,                  color:'#e11d48',icon:'userCheck',active:showSinSalida,onClick:()=>setShowSinSalida(v=>!v)}),
          showAccesoStats&&h(StatCard,{label:'Pend. días anteriores', value:resumen.control_acceso.dias_anteriores_pendientes, color:'#b91c1c',icon:'alert',active:showAccesoDiasAnt,onClick:()=>setShowAccesoDiasAnt(v=>!v)}),
          showProvStats&&h(StatCard,{label:'Proveedores hoy',          value:resumen.proveedores.hoy,    color:'#d97706',icon:'package',active:showProvHoy,onClick:()=>setShowProvHoy(v=>!v)}),
          showProvStats&&h(StatCard,{label:'En muelle',        value:resumen.proveedores.en_muelle, color:'#0891b2',icon:'package',active:showMuelle,onClick:()=>setShowMuelle(v=>!v)}),
          showProvStats&&h(StatCard,{label:'Visitantes hoy',   value:resumen.visitantes.hoy,     color:'#059669',icon:'users',active:showVisitantesHoy,onClick:()=>setShowVisitantesHoy(v=>!v)})
        ),
        showFlotaHoy&&h(DetalleLista,{items:resumen.flota.hoy_detalle||[],emptyMsg:'Sin registros de flota hoy',render:v=>[
          h('strong',{key:'p'},v.placa),' · ',v.conductor||'—',v.muelle&&(' · Muelle '+v.muelle),' · ',v.estado
        ]}),
        showEnRuta&&h(DetalleLista,{items:pendFlota,emptyMsg:'Ningún vehículo en ruta ahora',render:v=>[
          h('strong',{key:'p'},v.placa),' · ',v.conductor||'—',' · Salió: ',v.hora_salida||'—',' (',v.fecha,')'
        ]}),
        showAccesoHoy&&h(DetalleLista,{items:resumen.control_acceso.hoy_detalle||[],emptyMsg:'Sin registros de acceso hoy',render:v=>[
          h('strong',{key:'p'},v.nombre),' · ',v.contratista||'—',' · Ingresó: ',v.hora_ingreso?v.hora_ingreso.slice(0,5):'—',v.activo?' · Activo':' · Salió'
        ]}),
        showSinSalida&&h(DetalleLista,{items:pendAcceso,emptyMsg:'Nadie dentro sin salida ahora',render:v=>[
          h('strong',{key:'p'},v.nombre),' · ',v.contratista||'—',' · Ingresó: ',v.hora_ingreso||'—',' (',v.fecha,')'
        ]}),
        showAccesoDiasAnt&&h(DetalleLista,{items:resumen.control_acceso.dias_anteriores_detalle||[],emptyMsg:'Sin pendientes de días anteriores',render:v=>[
          h('span',{key:'d',className:'pill',style:{background:v.dias>=5?'#fee2e2':'#fef3c7',color:v.dias>=5?'#991b1b':'#92400e',marginRight:6}},v.dias+(v.dias===1?' día':' días')),
          h('strong',{key:'p'},v.nombre),' · ',v.contratista||'—',' · ',fmtDate(v.fecha),' ',v.hora_ingreso?v.hora_ingreso.slice(0,5):''
        ]}),
        showProvHoy&&h(DetalleLista,{items:resumen.proveedores.hoy_detalle||[],emptyMsg:'Sin registros de proveedores hoy',render:v=>[
          h('strong',{key:'p'},v.placa||'Sin placa'),' · ',v.conductor||'—',' · Ingresó: ',v.hora_ingreso?v.hora_ingreso.slice(0,5):'—',' · ',v.estado,
          v.empresas&&h('div',{key:'e',style:{marginTop:2,color:'#0e7490',fontWeight:600}},v.empresas)
        ]}),
        showMuelle&&h(DetalleLista,{items:resumen.proveedores.en_muelle_detalle||[],emptyMsg:'Ninguno en este momento',render:v=>[
          h('strong',{key:'p'},v.placa||'Sin placa'),' · ',v.conductor||'—',
          v.muelle&&(' · Muelle '+v.muelle),' · Ingresó: ',v.hora_ingreso?v.hora_ingreso.slice(0,5):'—',
          v.empresas&&h('div',{key:'e',style:{marginTop:2,color:'#0e7490',fontWeight:600}},v.empresas)
        ]}),
        showVisitantesHoy&&h(DetalleLista,{items:resumen.visitantes.hoy_detalle||[],emptyMsg:'Sin registros de visitantes hoy',render:v=>[
          h('strong',{key:'p'},v.nombre),' · ',v.empresa||'—',' · Ingresó: ',v.hora_ingreso?v.hora_ingreso.slice(0,5):'—',v.activo?' · Activo':' · Salió'
        ]})
      ),
      (()=>{
        const showFlotaPend  = !isGuardaPeatonal;
        const showAccesoPend = !isGuardaVehicular && !isGuardaBodega;
        const hayFlota  = showFlotaPend  && flotaPend>0;
        const hayAcceso = showAccesoPend && accesoPend>0;
        if(!hayFlota && !hayAcceso) return null;
        return h('div',{className:'dash-section',style:{marginTop:4}},
          h('p',{className:'sec-ttl'},h(Ico,{n:'alert',s:12}),' Pendientes de cierre'),
          h('div',{style:{background:'#fffbeb',border:'1.5px solid #fcd34d',borderRadius:12,padding:12}},
            hayFlota&&h('div',null,
              h('p',{style:{fontSize:12,fontWeight:600,color:'#1e4570',marginBottom:4}},`${flotaPend} vehículo(s) fuera sin llegada:`),
              pendFlota.map((v,i)=>h('div',{key:i,style:{fontSize:11,color:'var(--slate)',padding:'3px 8px',background:'#f8fafc',borderRadius:6,marginBottom:3}},
                h('strong',null,v.placa),' · ',v.conductor||'—',' · Salió: ',v.hora_salida||'—',' (',v.fecha,')'
              ))
            ),
            hayFlota&&hayAcceso&&h('div',{style:{height:1,background:'#fde68a',margin:'8px 0'}}),
            hayAcceso&&h('div',null,
              h('p',{style:{fontSize:12,fontWeight:600,color:'#7c3aed',marginBottom:4}},`${accesoPend} persona(s) dentro sin salida:`),
              pendAcceso.map((v,i)=>h('div',{key:i,style:{fontSize:11,color:'var(--slate)',padding:'3px 8px',background:'#f8fafc',borderRadius:6,marginBottom:3}},
                h('strong',null,v.nombre),' · ',v.contratista||'—',' · Ingresó: ',v.hora_ingreso||'—',' (',v.fecha,')'
              ))
            )
          )
        );
      })(),
      showTiempoAutoregistro&&h('div',{className:'dash-section',style:{marginTop:4}},
        h('p',{className:'sec-ttl'},h(Ico,{n:'clock',s:12}),' Indicadores'),
        h('div',{style:{background:'#fff',borderRadius:12,padding:'14px 14px',boxShadow:'0 1px 4px rgba(0,0,0,0.07)'}},
          !tiempoAutoregistro
            ? h(LoadingDots)
            : tiempoAutoregistro.muestras===0
              ? h('p',{style:{fontSize:12,color:'var(--slate)'}},'Aún no hay suficientes autorregistros por QR para calcular este indicador.')
              : h('div',null,
                  h('div',{style:{display:'flex',alignItems:'baseline',gap:6,flexWrap:'wrap'}},
                    h('span',{style:{fontSize:26,fontWeight:800,fontFamily:'Syne,sans-serif',color:'#1e4570',lineHeight:1}},tiempoAutoregistro.mediana_minutos+' min'),
                    h('span',{style:{fontSize:11,color:'var(--slate)',fontWeight:600}},'tiempo mediano de autorregistro por QR')
                  ),
                  h('p',{style:{fontSize:11,color:'var(--slate)',marginTop:5}},
                    `Promedio: ${tiempoAutoregistro.promedio_minutos} min · ${tiempoAutoregistro.muestras} registro${tiempoAutoregistro.muestras===1?'':'s'}`
                  )
                )
        )
      ),
      !resumen&&h('div',{style:{padding:'40px 14px',textAlign:'center',color:'var(--slate)',fontSize:13}},
        h(LoadingDots)
      )
    ),
    (tab==='modulos'||isRecorredor)&&h('div',{className:'pad'},
      h('p',{className:'sec-ttl'},h(Ico,{n:'home',s:12}),' Módulos'),
      h('div',{className:'mgrid'},
        mods.map(m=>h('button',{key:m.id,className:`mcard ${m.cls}`,onClick:()=>setPage(m.id)},
          m.cnt!=null&&h('span',{className:'mcnt'},m.cnt),
          h('div',{className:'mcard-icon'},h(Ico,{n:m.icon,s:20})),
          h('h4',null,m.label),h('p',null,m.desc)
        ))
      )
    )
  );
}
