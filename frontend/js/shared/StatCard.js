// ── STAT CARD ──
// Extraído de frontend/index.html (líneas 804-815, comentario
// "/* ── HOME PAGE ── */" + función StatCard, justo antes de DetalleLista,
// del <script> monolítico). Contenido idéntico al original: el código
// viejo en index.html NO fue tocado ni borrado (ver notas de la Fase 2/3
// del plan de migración) -- este módulo es una copia autocontenida, lista
// para que las fases posteriores lo importen cuando quede conectado vía
// <script type="module">.
//
// Depende de React y del icono compartido Ico (core/icons.js).

import { Ico } from '../core/icons.js';

const h = React.createElement;

export function StatCard({label,value,color,icon,onClick,active}){
  return h('div',{onClick,style:{background:active?'#f0f9ff':'#fff',borderRadius:10,padding:'10px 10px',boxShadow:'0 1px 4px rgba(0,0,0,0.07)',display:'flex',alignItems:'center',gap:8,cursor:onClick?'pointer':'default',border:active?'1.5px solid #0891b2':'1.5px solid transparent'}},
    h('div',{style:{width:32,height:32,borderRadius:8,background:color+'22',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}},
      h(Ico,{n:icon,s:16,style:{color}})
    ),
    h('div',null,
      h('div',{style:{fontSize:18,fontWeight:800,fontFamily:'Syne,sans-serif',color,lineHeight:1}},value??'—'),
      h('div',{style:{fontSize:10,color:'var(--slate)',fontWeight:600,marginTop:1}},label)
    )
  );
}
