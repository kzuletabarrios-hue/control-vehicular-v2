// ── NOVEDADES PAGE ──
// Extraído de frontend/index.html (líneas 5531-5630, función NovedadesPage
// del <script> monolítico, marcada con el comentario
// "/* ── NOVEDADES PAGE ── */", entre el cierre de RondaPanelPage y
// "/* ── PLACEHOLDER PAGE ── */"). Contenido idéntico al original: el código
// viejo en index.html NO fue tocado ni borrado -- este módulo es una copia
// autocontenida, lista para que la Fase 6 lo importe cuando quede conectado
// vía <script type="module">.
//
// Importa Ico (core/icons.js), api (core/api-client.js) y fmtDate
// (core/utils.js), y los componentes compartidos Alert, LoadingDots
// (shared/). No usa useVisibilityPolling -- carga solo con useEffect al
// montar / al cambiar los filtros, tal cual el original.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { fmtDate } from '../core/utils.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function NovedadesPage({user}){
  const [items,setItems]       = useState([]);
  const [loading,setLoading]   = useState(true);
  const [alert,setAlert]       = useState(null);
  const [filtroEst,setFiltroEst] = useState('');
  const [filtroMod,setFiltroMod] = useState('');

  const esAdmin = ['admin','supervisor'].includes(user?.rol);

  const load = useCallback(()=>{
    setLoading(true);
    let url='/novedades';
    const ps=[];
    if(filtroEst) ps.push('estado='+filtroEst);
    if(filtroMod) ps.push('modulo='+filtroMod);
    if(ps.length) url+='?'+ps.join('&');
    api.get(url).then(r=>setItems(Array.isArray(r)?r:[])).catch(()=>{}).finally(()=>setLoading(false));
  },[filtroEst,filtroMod]);
  useEffect(()=>{ load(); },[load]);

  const cambiarEstado = async(id,estado)=>{
    try{
      await api.patch(`/novedades/${id}/estado`,{estado});
      setAlert({type:'ok',msg:'Estado actualizado'});
      load();
    }catch(e){ setAlert({type:'err',msg:'Error: '+e.message}); }
  };

  const EPILLS = {
    abierta:    {cls:'pill-red',  label:'Abierta'},
    en_revision:{cls:'pill-amber',label:'En revisión'},
    cerrada:    {cls:'pill-slate',label:'Cerrada'},
  };
  const MODS = {general:'General',flota:'Flota',proveedores:'Proveedores',acceso:'Acceso',visitantes:'Visitantes',ronda:'Ronda'};
  const CATS = {seguridad:'Seguridad',mantenimiento:'Mantenimiento',logistica:'Logística',otro:'Otro'};

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('div',{className:'header-brand'},
          h('h1',null,'Novedades'),
          h('span',null,'Incidencias del sistema')
        )
      )
    ),
    h('div',{style:{display:'flex',gap:6,padding:'8px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('select',{value:filtroEst,onChange:e=>setFiltroEst(e.target.value),
        style:{flex:1,fontSize:12,padding:'6px 8px',border:'1.5px solid var(--border)',borderRadius:8,background:'#f8fafc',fontFamily:'inherit',appearance:'none'}},
        h('option',{value:''},'Todos los estados'),
        h('option',{value:'abierta'},'Abiertas'),
        h('option',{value:'en_revision'},'En revisión'),
        h('option',{value:'cerrada'},'Cerradas')
      ),
      h('select',{value:filtroMod,onChange:e=>setFiltroMod(e.target.value),
        style:{flex:1,fontSize:12,padding:'6px 8px',border:'1.5px solid var(--border)',borderRadius:8,background:'#f8fafc',fontFamily:'inherit',appearance:'none'}},
        h('option',{value:''},'Todos los módulos'),
        Object.entries(MODS).map(([v,l])=>h('option',{key:v,value:v},l))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      items.length===0?h('div',{className:'empty'},h(Ico,{n:'bell',s:44}),h('p',null,'Sin novedades')):
      items.map(item=>{
        const ep=EPILLS[item.estado]||EPILLS.abierta;
        const dotColor=item.estado==='abierta'?'#dc2626':item.estado==='en_revision'?'#d97706':'#94a3b8';
        const dotBg  =item.estado==='abierta'?'#fee2e2':item.estado==='en_revision'?'#fef3c7':'#f1f5f9';
        return h('div',{key:item.id,className:'list-item',style:{flexDirection:'column',alignItems:'stretch',gap:8,cursor:'default'}},
          h('div',{style:{display:'flex',alignItems:'flex-start',gap:10}},
            h('div',{className:'li-icon',style:{background:dotBg,flexShrink:0}},
              h(Ico,{n:'bell',s:18,style:{color:dotColor}})
            ),
            h('div',{style:{flex:1,minWidth:0}},
              h('div',{className:'li-title',style:{whiteSpace:'normal',lineHeight:1.3}},item.descripcion),
              h('div',{className:'li-sub',style:{marginTop:3}},
                (MODS[item.modulo_origen]||item.modulo_origen)+' · '+(CATS[item.categoria]||item.categoria)
              ),
              h('div',{style:{fontSize:10,color:'var(--slate)',marginTop:2}},
                (item.usuario_nombre||'—')+' · '+fmtDate(item.fecha)+(item.hora?' '+item.hora.slice(0,5):'')
              )
            ),
            h('span',{className:`pill ${ep.cls}`,style:{flexShrink:0,alignSelf:'flex-start'}},ep.label)
          ),
          item.fotografia&&h('img',{src:item.fotografia,style:{width:'100%',borderRadius:8,maxHeight:130,objectFit:'cover'}}),
          esAdmin&&item.estado!=='cerrada'&&h('div',{style:{display:'flex',gap:6,justifyContent:'flex-end'}},
            item.estado==='abierta'&&h('button',{
              onClick:()=>cambiarEstado(item.id,'en_revision'),
              style:{fontSize:11,padding:'4px 10px',borderRadius:6,border:'1.5px solid #d97706',color:'#d97706',background:'none',cursor:'pointer',fontWeight:600}
            },'En revisión'),
            h('button',{
              onClick:()=>cambiarEstado(item.id,'cerrada'),
              style:{fontSize:11,padding:'4px 10px',borderRadius:6,border:'1.5px solid var(--slate)',color:'var(--slate)',background:'none',cursor:'pointer',fontWeight:600}
            },'Cerrar')
          )
        );
      })
    )
  );
}
