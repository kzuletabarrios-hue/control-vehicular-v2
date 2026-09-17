// ── BADGES (tipo de carga + logística inversa) ──
// Extraído de frontend/index.html (líneas 406-442, sección
// "/* ── COMPONENTS ── */" del <script> monolítico, bloque de badges antes
// de LineaTiempoPasos/DetalleTiempos). Contenido idéntico al original: el
// código viejo en index.html NO fue tocado ni borrado (ver notas de la
// Fase 2/3 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que las fases posteriores lo importen cuando
// quede conectado vía <script type="module">.
//
// Único hallazgo de "distintos badges de estado" en el monolito: solo
// existen estos 3 (TipoCargaBadge, TipoCargaBadgeMini y
// LogisticaInversaBadge) -- no hay un EstadoBadge genérico ni badges
// adicionales bajo otro nombre (verificado con búsqueda de
// `function \w*Badge\w*\(` sobre todo index.html).
//
// LogisticaInversaBadge importa TIPOS_LOGISTICA_INVERSA desde
// ./LogisticaInversaField.js en vez de duplicar el catálogo, tal como
// documentó el agente anterior en ese archivo.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { TIPOS_LOGISTICA_INVERSA } from './LogisticaInversaField.js';

const h = React.createElement;

// Estilo del badge de tipo de carga: Refrigerada resalta en frío (azul) por su
// sensibilidad logística; Seca y Mixta usan tonos neutros/de atención ya
// presentes en la paleta de pills.
const TIPO_CARGA_CLS = { Refrigerada:'pill-blue', Seca:'pill-slate', Mixta:'pill-amber' };

export function TipoCargaBadge({tipo,style}){
  if(!tipo) return null;
  return h('span',{className:`pill ${TIPO_CARGA_CLS[tipo]||'pill-slate'}`,style:{display:'inline-block',...style}},
    (tipo==='Refrigerada'?'❄ ':'')+tipo
  );
}

// Abreviatura para la etiqueta mini de tipo de carga dentro de una celda de
// muelle (56-64px, no cabe el nombre completo). Mismo color que
// TipoCargaBadge -- se combina TIPO_CARGA_CLS con .pill-mini, nunca se
// inventa una paleta nueva.
const TIPO_CARGA_ABREV = { Refrigerada:'❄ REF', Seca:'SEC', Mixta:'MIX' };
export function TipoCargaBadgeMini({tipo}){
  if(!tipo) return null;
  return h('span',{className:`pill-mini ${TIPO_CARGA_CLS[tipo]||'pill-slate'}`},TIPO_CARGA_ABREV[tipo]||tipo);
}

// Badge de los tipos de logística inversa (estibas/canastillas/devoluciones/...)
// respondidos por el conductor -- reutiliza el catálogo global
// TIPOS_LOGISTICA_INVERSA (importado de LogisticaInversaField.js) para
// traducir value -> label. Se usa tanto en el detalle del tablero 20-22
// (MuelleDetallePanelInversa) como en la card de Proveedores.
export function LogisticaInversaBadge({tipos, style}){
  if(!Array.isArray(tipos) || tipos.length===0) return null;
  const labels = tipos.map(v => TIPOS_LOGISTICA_INVERSA.find(t=>t.value===v)?.label || v);
  return h('span',{className:'pill pill-navy', style:{display:'inline-flex',alignItems:'center',gap:4,fontWeight:700,...style}},
    h(Ico,{n:'package',s:10}),
    labels.join(', ')
  );
}
