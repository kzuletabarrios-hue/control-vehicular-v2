// ── BUSQUEDA SHEET ──
// Extraído de frontend/index.html (líneas 709-771). En el monolito, esta
// función queda bajo el comentario de sección "/* ── HEADER COMPONENT ──
// */" (línea 708), que agrupa tanto BusquedaSheet como AppHeader -- se
// documenta la desviación: aquí se separa en su propio módulo porque es un
// sheet independiente (búsqueda global por placa/cédula/nombre), no parte
// del layout del header en sí. Contenido idéntico al original: el código
// viejo en index.html NO fue tocado ni borrado (ver notas de la Fase 2 del
// plan de migración) -- este módulo es una copia autocontenida, lista para
// que la Fase 6 lo importe cuando quede conectado vía <script type="module">.

import { api } from '../core/api-client.js';
import { Ico } from '../core/icons.js';

const { useState, useEffect } = React;
const h = React.createElement;

export function BusquedaSheet({onClose,onAbrirFlota}){
  const [q,setQ]           = useState('');
  const [items,setItems]   = useState([]);
  const [loading,setLoading]=useState(false);
  const [err,setErr]       = useState(null);

  useEffect(()=>{
    const term = q.trim();
    if(term.length<2){ setItems([]); setErr(null); return; }
    setLoading(true);
    const t = setTimeout(async()=>{
      try{
        const r = await api.get('/busqueda?q='+encodeURIComponent(term));
        setItems(r.items||[]); setErr(null);
      }catch(e){ setErr('Error al buscar'); }
      finally{ setLoading(false); }
    },350);
    return ()=>clearTimeout(t);
  },[q]);

  const estadoColor = (estado)=> (estado==='Dentro'||estado==='En ruta') ? 'pill-amber'
    : (estado==='Salió'||estado==='Regresó') ? 'pill-slate'
    : (estado==='En bodega') ? 'pill-blue' : 'pill-slate';

  return h('div',{className:'overlay',onClick:onClose},
    h('div',{className:'sheet',style:{maxHeight:'85vh',display:'flex',flexDirection:'column'},onClick:e=>e.stopPropagation()},
      h('div',{className:'sheet-handle'}),
      h('div',{className:'sheet-header',style:{padding:'0 16px 10px'}},
        h('h2',null,h(Ico,{n:'search',s:16}),' Buscar ingreso'),
        h('button',{className:'btn-icon',onClick:onClose},h(Ico,{n:'x',s:15}))
      ),
      h('div',{style:{padding:'0 16px 10px'}},
        h('input',{
          autoFocus:true, value:q, onChange:e=>setQ(e.target.value),
          placeholder:'Placa, cédula o nombre...',
          style:{width:'100%',padding:'10px 12px',borderRadius:8,border:'1.5px solid var(--border)',fontSize:14}
        })
      ),
      h('div',{style:{padding:'0 16px 20px',overflowY:'auto',flex:1}},
        loading&&h('div',{style:{textAlign:'center',padding:20,color:'var(--slate)',fontSize:13}},'Buscando...'),
        err&&h('div',{style:{textAlign:'center',padding:20,color:'var(--red)',fontSize:13}},err),
        !loading&&!err&&q.trim().length>=2&&items.length===0&&
          h('div',{style:{textAlign:'center',padding:20,color:'var(--slate)',fontSize:13}},'Sin resultados'),
        !loading&&q.trim().length<2&&
          h('div',{style:{textAlign:'center',padding:20,color:'var(--slate)',fontSize:12}},'Escribe al menos 2 caracteres'),
        items.map((it,i)=>{
          const esFlota = it.modulo==='flota';
          return h('div',{key:it.modulo+it.id+i,onClick:esFlota?()=>{onAbrirFlota(it.id);onClose();}:undefined,style:{
            display:'flex',justifyContent:'space-between',alignItems:'center',
            padding:'10px 12px',borderRadius:8,background:'#f8fafc',marginBottom:6,
            cursor:esFlota?'pointer':'default'
          }},
            h('div',null,
              h('div',{style:{fontWeight:700,fontSize:13}},it.identificador||'—'),
              h('div',{style:{fontSize:11,color:'var(--slate)'}},[it.detalle,it.modulo_label,it.fecha].filter(Boolean).join(' · '))
            ),
            h('span',{className:'pill '+estadoColor(it.estado)},it.estado)
          );
        })
      )
    )
  );
}
