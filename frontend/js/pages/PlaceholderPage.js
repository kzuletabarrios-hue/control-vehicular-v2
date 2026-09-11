// ── PLACEHOLDER PAGE ──
// Extraído de frontend/index.html (líneas 5632-5650, comentario
// "/* ── PLACEHOLDER PAGE ── */" del <script> monolítico). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado (ver notas de la Fase 2 del plan de migración) -- este módulo es
// una copia autocontenida, lista para que la Fase 6 lo importe cuando quede
// conectado vía <script type="module">.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';

const h = React.createElement;

export function PlaceholderPage({label,setPage}){
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>setPage('home'),style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Inicio'
        ),
        h('div',{className:'header-brand'},h('h1',null,label))
      )
    ),
    h('div',{className:'scroll-body pad',style:{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:12,paddingTop:60}},
      h(Ico,{n:'clock',s:48,style:{color:'var(--slate)',opacity:.4}}),
      h('p',{style:{color:'var(--slate)',fontSize:14,fontWeight:600}},label),
      h('p',{style:{color:'var(--slate)',fontSize:12,opacity:.7}},'Módulo disponible en próxima entrega'),
      h('button',{onClick:()=>setPage('home'),style:{marginTop:8,background:'var(--navy2)',color:'#fff',border:'none',borderRadius:8,padding:'10px 20px',fontSize:13,fontWeight:700,cursor:'pointer',fontFamily:'inherit'}},'Volver al inicio')
    )
  );
}
