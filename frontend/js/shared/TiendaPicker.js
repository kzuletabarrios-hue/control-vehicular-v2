// ── SELECTOR DE TIENDA (autocompletar por código o nombre) ──
// Extraído de frontend/index.html (líneas 1012-1042, sección
// "/* ── SELECTOR DE TIENDA (autocompletar por código o nombre) ── */" del
// <script> monolítico). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado (ver notas de la Fase 2/3 del plan
// de migración) -- este módulo es una copia autocontenida, lista para que
// las fases posteriores lo importen cuando quede conectado vía
// <script type="module">.
//
// Depende de React (con useState global) y del icono compartido Ico
// (core/icons.js).

import { Ico } from '../core/icons.js';

const { useState } = React;
const h = React.createElement;

export function TiendaPicker({label,tiendas,value,onChange}){
  const cur = tiendas.find(t=>t.id===value);
  const curLabel = cur ? (cur.codigo?`${cur.codigo} - ${cur.name}`:cur.name) : '';
  const [q,setQ]           = useState('');
  const [editing,setEditing] = useState(false);
  const sugs = (editing && q.trim().length>0)
    ? tiendas.filter(t=>(t.codigo!=null && String(t.codigo).includes(q.trim())) || t.name.toLowerCase().includes(q.trim().toLowerCase())).slice(0,8)
    : [];
  return h('div',{className:'fg',style:{position:'relative'}},
    h('label',null,label),
    h('div',{style:{display:'flex',gap:6}},
      h('input',{
        type:'text',
        value: editing ? q : curLabel,
        placeholder:'Buscar por código o nombre...',
        onFocus:()=>{setEditing(true);setQ('');},
        onChange:e=>setQ(e.target.value),
        onBlur:()=>setTimeout(()=>setEditing(false),150)
      }),
      curLabel&&h('button',{type:'button',onClick:()=>{onChange('');setQ('');},title:'Quitar',style:{background:'none',border:'none',cursor:'pointer',color:'#94a3b8',padding:'0 6px'}},h(Ico,{n:'x',s:14}))
    ),
    editing&&q.trim().length>0&&h('div',{style:{position:'absolute',top:'100%',left:0,right:0,background:'#fff',border:'1px solid var(--border)',borderRadius:8,zIndex:50,boxShadow:'var(--shadow)',maxHeight:180,overflowY:'auto'}},
      sugs.length>0
        ? sugs.map(t=>h('div',{key:t.id,onClick:()=>{onChange(t.id);setQ('');setEditing(false);},style:{padding:'10px 12px',cursor:'pointer',borderBottom:'1px solid var(--border)',fontSize:13}},
            t.codigo!=null&&h('strong',null,t.codigo+' '),t.name
          ))
        : h('div',{style:{padding:'10px 12px',fontSize:12,color:'var(--slate)'}},'Sin resultados')
    )
  );
}
