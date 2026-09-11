// ── LOGÍSTICA INVERSA SECTION (tablero de muelles 19-21) ──
// Extraído de frontend/index.html (líneas 6063-6290, comentarios + funciones
// MuelleLineaTiempoInversa, MuelleDetallePanelInversa y
// MuellesLogisticaInversaSection). Contenido idéntico al original: el
// código viejo en index.html NO fue tocado ni borrado -- este módulo es una
// copia autocontenida, lista para que la Fase 6 lo importe cuando quede
// conectado vía <script type="module">.
//
// Nombre real del componente en el monolito: `MuellesLogisticaInversaSection`
// (no `LogisticaInversaSection` a secas, como lo nombra el archivo por
// convención de carpeta) -- se conserva el nombre original de la función al
// exportarla para no inventar una API distinta a la que ya existe; el
// archivo se llama `LogisticaInversaSection.js` porque así lo pide la
// estructura de carpetas del encargo.
//
// `MuelleLineaTiempoInversa` y `MuelleDetallePanelInversa` son de uso
// exclusivo de esta sección (el tablero 19-21) -- no están en la lista de
// archivos del encargo porque no se usan en ningún otro lado del módulo de
// muelles, así que se quedan aquí como helpers privados del archivo, mismo
// criterio que MuelleBotonConfirmar dentro de shared/ConfirmarMuelleSheet.js.
//
// Reutiliza MuelleCelda (./MuelleCelda.js, el mismo componente de celda que
// usa el tablero 1-18 en index.js) y hhmmT/LineaTiempoPasos (core/utils.js,
// promovidas ahí en la Fase 5 lote 7 paso 0 -- antes se importaban desde
// ./MuelleDetallePanel.js, que las duplicaba temporalmente) -- no se
// duplican dentro de este módulo de muelles.
//
// Importa Ico (core/icons.js), api (core/api-client.js), puede,
// hhmmT y LineaTiempoPasos (core/utils.js), useVisibilityPolling
// (core/hooks.js), TipoCargaBadge y LogisticaInversaBadge
// (shared/badges.js), Alert, LoadingDots y ConfirmSheet (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { puede, hhmmT, LineaTiempoPasos } from '../../core/utils.js';
import { useVisibilityPolling } from '../../core/hooks.js';
import { TipoCargaBadge, LogisticaInversaBadge } from '../../shared/badges.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';
import { MuelleCelda } from './MuelleCelda.js';

const { useState, useCallback } = React;
const h = React.createElement;

// Timeline y panel de detalle propios del tablero 19-21 -- mismo patrón que
// MuelleLineaTiempo/MuelleDetallePanel pero con el subconjunto de pasos y
// campos que expone /muelles/logistica-inversa (sin zona/tipo_carga_habitual,
// con tipos_logistica_inversa y sus dos horas propias). Se mantienen
// separados de los originales para no alterar el tablero 1-18.
function MuelleLineaTiempoInversa({muelle:m}){
  const pasos = [
    {icon:'mapPin', titulo:'Asignado a logística inversa', hora:hhmmT(m.hora_logistica_inversa_asignado),
     desc:'Muelle asignado tras liberar el andén de descargue'},
    {icon:'truck',  titulo:'Liberado', hora:hhmmT(m.hora_logistica_inversa_liberado),
     desc:'Cargue de logística inversa finalizado'},
  ];
  return h(React.Fragment,null,
    h('p',{className:'sec-ttl'},h(Ico,{n:'clock',s:12}),' Línea de tiempo'),
    h(LineaTiempoPasos,{pasos})
  );
}

function MuelleDetallePanelInversa({muelle:m, onCerrar, puedeLiberar, onLiberar}){
  return h('div',{className:'muelle-detalle'},
    h('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:8,marginBottom:8}},
      h('p',{style:{fontWeight:800,fontSize:16,fontFamily:'Syne,sans-serif',lineHeight:1.15}},'Muelle '+m.numero),
      h('div',{style:{display:'flex',alignItems:'center',gap:6,flexShrink:0}},
        h('span',{className:'pill',style:{background:'var(--amber)',color:'var(--navy)'}},'Ocupado'),
        h('button',{type:'button',onClick:onCerrar,'aria-label':'Cerrar detalle del muelle',
          style:{background:'none',border:'none',cursor:'pointer',padding:4,color:'var(--slate)',display:'flex'}
        },h(Ico,{n:'x',s:16}))
      )
    ),
    h('div',{style:{marginBottom:8}},h(LogisticaInversaBadge,{tipos:m.tipos_logistica_inversa})),
    h('p',{style:{fontSize:14,fontWeight:700}},m.placa_vehiculo||'Sin placa'),
    m.nombre_conductor&&h('p',{style:{fontSize:12,color:'var(--text2)',marginTop:1}},m.nombre_conductor),
    m.empresas&&h('p',{style:{fontSize:11,color:'#0e7490',fontWeight:600,marginTop:3}},m.empresas),
    m.tipo_carga&&h('div',{style:{marginTop:6}},h(TipoCargaBadge,{tipo:m.tipo_carga})),
    h('div',{style:{display:'flex',alignItems:'center',flexWrap:'wrap',gap:6,marginTop:8}},
      h('span',{style:{display:'inline-flex',alignItems:'center',gap:4,color:m.alerta_tiempo?'var(--red)':'var(--text2)'}},
        h(Ico,{n:'clock',s:12}),
        h('span',{style:{fontSize:11,fontWeight:700}},m.minutos_ocupado!=null?`${m.minutos_ocupado} min ocupado`:'—')
      ),
      m.alerta_tiempo&&h('span',{className:'pill pill-red'},'Tiempo excedido')
    ),
    h(MuelleLineaTiempoInversa,{muelle:m}),
    // Mismo criterio que MuelleDetallePanel: acción operativa gateada por
    // "muelles":"liberar", usando proveedor_id del payload de
    // GET /muelles/logistica-inversa.
    puedeLiberar&&m.proveedor_id&&h('button',{
      type:'button',
      onClick:()=>onLiberar(m),
      style:{marginTop:12,width:'100%',background:'var(--navy3)',border:'none',cursor:'pointer',color:'#fff',padding:'8px 12px',borderRadius:8,fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',gap:6}
    },h(Ico,{n:'truck',s:14}),'Liberar muelle inversa')
  );
}

// Sección independiente del tablero 19-21 (logística inversa) -- mismo
// patrón de polling/estado que MuellesPage pero aislada en su propio
// componente porque consume un endpoint distinto (/muelles/logistica-inversa)
// y no comparte estado con el tablero 1-18. Se monta como último hijo del
// .scroll-body de MuellesPage.
export function MuellesLogisticaInversaSection({user}){
  const [muelles,setMuelles] = useState([]);
  const [loading,setLoading] = useState(true);
  const [error,setError]     = useState(null);
  const [seleccionId,setSeleccionId] = useState(null);
  const [liberando,setLiberando] = useState(null);
  const [alert,setAlert]         = useState(null);
  const puedeLiberar = puede(user,'muelles','liberar');

  const load = useCallback(()=>{
    api.get('/muelles/logistica-inversa')
      .then(r=>{ setMuelles(Array.isArray(r)?r:(r.items||[])); setError(null); })
      .catch(()=>setError('No se pudo cargar el tablero de logística inversa'))
      .finally(()=>setLoading(false));
  },[]);
  useVisibilityPolling(load, 60000, [load]);

  const ocupados = muelles.filter(m=>m.estado==='ocupado').length;
  const muelleSeleccionado = seleccionId!=null ? muelles.find(m=>m.id===seleccionId && m.estado==='ocupado') : null;

  return h('div',{style:{margin:'22px -14px 0',padding:'14px 14px 12px',borderTop:'3px solid var(--navy2)',background:'linear-gradient(180deg,rgba(26,58,92,0.06),transparent 70%)'}},
    h('div',{style:{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}},
      h('span',{style:{display:'inline-flex',alignItems:'center',justifyContent:'center',width:26,height:26,borderRadius:8,background:'var(--navy2)',color:'#fff',flexShrink:0}},
        h(Ico,{n:'package',s:14})
      ),
      h('h2',{className:'syne',style:{fontSize:15,fontWeight:800,color:'var(--navy)',margin:0}},'Logística inversa'),
      h('span',{className:'pill pill-navy',style:{fontWeight:800}},'Muelles 19–21')
    ),
    h('p',{style:{fontSize:11,color:'var(--slate)',margin:'4px 0 10px'}},
      'Vehículos que ya descargaron en 1–18 y pasaron aquí a recoger estibas, canastillas, devoluciones u otros.'
    ),
    !loading&&!error&&h('p',{style:{fontSize:11,color:'var(--text2)',fontWeight:700,marginBottom:6}},
      `${ocupados} ocupado${ocupados===1?'':'s'} de ${muelles.length}`
    ),
    !loading&&!error&&muelles.length>0&&h('div',{className:'muelle-leyenda'},
      h('span',{className:'muelle-leyenda-item'},h('span',{className:'muelle-leyenda-swatch libre','aria-hidden':'true'}),'Libre'),
      h('span',{className:'muelle-leyenda-item'},h('span',{className:'muelle-leyenda-swatch ocupado','aria-hidden':'true'}),'Ocupado'),
      h('span',{className:'muelle-leyenda-item'},h('span',{className:'muelle-leyenda-swatch alerta','aria-hidden':'true'}),'Tiempo excedido')
    ),
    error&&h(Alert,{type:'err',msg:error,onClose:()=>setError(null)}),
    alert&&h(Alert,{type:alert.type,msg:alert.msg,onClose:()=>setAlert(null)}),
    loading?h(LoadingDots):h(React.Fragment,null,
      muelleSeleccionado&&h(MuelleDetallePanelInversa,{
        muelle:muelleSeleccionado,onCerrar:()=>setSeleccionId(null),
        puedeLiberar, onLiberar:m=>setLiberando(m)
      }),
      h('div',{className:'muelle-grid'},muelles.map(m=>h(MuelleCelda,{
        key:m.id, muelle:m, seleccionado:m.id===seleccionId,
        onSeleccionar:id=>setSeleccionId(prev=>prev===id?null:id)
      })))
    ),
    liberando&&h(ConfirmSheet,{
      icon:'truck',
      titulo:`¿Liberar el muelle de logística inversa ${liberando.numero}?`,
      textoOk:'Liberar muelle',
      colorOk:'var(--navy3)',
      msg:`El vehículo ${liberando.placa_vehiculo||''} dejará de ocupar el muelle ${liberando.numero} de logística inversa.`,
      onOk:async()=>{
        try{
          await api.put(`/proveedores/${liberando.proveedor_id}/liberar-muelle-inversa`,{});
          setLiberando(null); load(); setAlert({type:'ok',msg:'Muelle de logística inversa liberado'});
        }catch(e){
          setLiberando(null); load();
          setAlert({type:'err',msg:'Error: '+e.message});
        }
      },
      onCancel:()=>setLiberando(null)
    })
  );
}
