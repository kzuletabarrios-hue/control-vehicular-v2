// ── DETALLE LISTA ──
// Extraído de frontend/index.html (líneas 817-823, sección
// "/* ── HOME PAGE ── */" del <script> monolítico, justo después de
// StatCard). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado (ver notas de la Fase 2/3 del plan
// de migración) -- este módulo es una copia autocontenida, lista para que
// las fases posteriores lo importen cuando quede conectado vía
// <script type="module">.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.
// No usa Ico ni ninguna otra utilidad de core/.

const h = React.createElement;

export function DetalleLista({items,render,emptyMsg}){
  return h('div',{style:{marginTop:8,background:'#ecfeff',border:'1.5px solid #a5f3fc',borderRadius:12,padding:12}},
    items.length===0
      ? h('p',{style:{fontSize:12,color:'var(--slate)'}},emptyMsg||'Sin registros')
      : items.map((v,i)=>h('div',{key:i,style:{fontSize:11,color:'var(--slate)',padding:'5px 8px',background:'#fff',borderRadius:6,marginBottom:3}},render(v)))
  );
}
