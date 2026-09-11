// ── MUELLE CELDA (celda numerada del tablero de muelles) ──
// Extraído de frontend/index.html (líneas 5964-5992, función MuelleCelda,
// dentro de la sección "/* ── MUELLES (tablero de ocupación, solo lectura)
// ── */"). Contenido idéntico al original: el código viejo en index.html NO
// fue tocado ni borrado -- este módulo es una copia autocontenida, lista
// para que la Fase 6 lo importe cuando quede conectado vía
// <script type="module">.
//
// Se usa en dos tableros del monolito: MuellesPage (muelles 1-18) y
// MuellesLogisticaInversaSection (muelles 19-21, ver LogisticaInversaSection.js)
// -- por eso vive en su propio archivo en vez de anidarse dentro de
// index.js o de LogisticaInversaSection.js.
//
// Importa Ico (core/icons.js) y TipoCargaBadgeMini (shared/badges.js).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { TipoCargaBadgeMini } from '../../shared/badges.js';

const h = React.createElement;

// Celda compacta y numerada (56-64px) que reemplaza a la card vertical de
// antes -- ver comentario en .muelle-grid (arriba, en la hoja de estilos)
// sobre por qué se hizo el cambio. Solo las celdas "ocupado" son clickeables:
// las libres no tienen nada que mostrar en el panel de detalle, así que se
// renderizan como <button disabled> (informativas, no interactivas).
export function MuelleCelda({muelle:m, seleccionado, onSeleccionar}){
  const ocupado = m.estado==='ocupado';
  // Discordancia = el proveedor que ocupa el muelle trae un tipo de carga
  // distinto al habitual de ese muelle. Es solo informativo (no bloquea
  // nada, la vista es de solo lectura); en la celda se reduce a un punto
  // azul sutil en la esquina (.muelle-celda-dot) para no competir con el
  // ámbar de "tiempo excedido", que es la señal prioritaria del tablero. El
  // detalle textual completo se muestra en MuelleDetallePanel al seleccionar.
  const discordancia = ocupado && m.tipo_carga_habitual && m.tipo_carga && m.tipo_carga_habitual!==m.tipo_carga;
  const clases = ['muelle-celda', m.alerta_tiempo?'alerta':(ocupado?'ocupado':'libre')];
  if(seleccionado) clases.push('selected');
  return h('button',{
    type:'button',
    className:clases.join(' '),
    disabled:!ocupado,
    'aria-pressed':ocupado?!!seleccionado:undefined,
    onClick:ocupado?()=>onSeleccionar(m.id):undefined,
    title:`Muelle ${m.numero} — ${ocupado?(m.alerta_tiempo?'ocupado, tiempo excedido':'ocupado'):'libre'}`
  },
    discordancia&&h('span',{className:'muelle-celda-dot','aria-hidden':'true'}),
    h('span',{className:'muelle-celda-num'},m.numero),
    m.tipo_carga_habitual&&h(TipoCargaBadgeMini,{tipo:m.tipo_carga_habitual})
  );
}
