// ── ALERT ──
// Extraído de frontend/index.html (líneas 501-508, dentro de la sección
// "/* ── COMPONENTS ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2/3 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que las fases posteriores lo importen cuando
// quede conectado vía <script type="module">.
//
// Depende de React y del icono compartido Ico (core/icons.js).

import { Ico } from '../core/icons.js';

const h = React.createElement;

export function Alert({type,msg,onClose}){
  if(!msg)return null;
  const cls = type==='ok'?'alert-ok':type==='warn'?'alert-warn':'alert-err';
  const icon= type==='ok'?'check':type==='warn'?'alert':'x';
  return h('div',{className:`alert ${cls}`},h(Ico,{n:icon,s:14}),h('span',null,msg),
    onClose&&h('button',{onClick:onClose,style:{marginLeft:'auto',background:'none',border:'none',cursor:'pointer'}},h(Ico,{n:'x',s:13}))
  );
}
