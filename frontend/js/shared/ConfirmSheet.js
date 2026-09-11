// ── CONFIRM SHEET ──
// Extraído de frontend/index.html (líneas 509-524, dentro de la sección
// "/* ── COMPONENTS ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2/3 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que las fases posteriores lo importen cuando
// quede conectado vía <script type="module">.
//
// Depende de React y del icono compartido Ico (core/icons.js). Lo importa
// también ConfirmarMuelleSheet.js (otro componente de shared/) para el paso
// de "confirmar muelle ocupado" -- se referencia desde ahí, no se duplica.

import { Ico } from '../core/icons.js';

const h = React.createElement;

export function ConfirmSheet({msg,onOk,onCancel,icon='trash',titulo='¿Eliminar registro?',textoOk='Eliminar',colorOk='var(--red)'}){
  return h('div',{className:'overlay',onClick:onCancel},
    h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
      h('div',{className:'sheet-handle'}),
      h('div',{style:{padding:'0 0 8px',textAlign:'center'}},
        h('div',{className:'confirm-icon'},h(Ico,{n:icon,s:22})),
        h('h3',{style:{fontSize:16,fontWeight:700,marginBottom:6}},titulo),
        h('p',{style:{fontSize:12,color:'var(--slate)',marginBottom:20,lineHeight:1.5}},msg||'Esta acción no se puede deshacer.'),
        h('div',{style:{display:'flex',gap:8}},
          h('button',{className:'btn-cancel btn-primary',style:{background:'none',border:'1.5px solid var(--navy2)',color:'var(--navy2)',flex:1},onClick:onCancel},'Cancelar'),
          h('button',{className:'btn-primary',style:{background:colorOk},onClick:onOk},h(Ico,{n:icon,s:16}),textoOk)
        )
      )
    )
  );
}
