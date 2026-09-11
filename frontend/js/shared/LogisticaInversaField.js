// ── LOGÍSTICA INVERSA (catálogo + campo compartido) ──
// Extraído de frontend/index.html (líneas 71-115, sección
// "/* ── LOGÍSTICA INVERSA (catálogo + campo compartido) ── */" del
// <script> monolítico). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado (ver notas de la Fase 2/3 del plan de
// migración) -- este módulo es una copia autocontenida, lista para que las
// fases posteriores lo importen cuando quede conectado vía
// <script type="module">.
//
// TIPOS_LOGISTICA_INVERSA se exporta además de LogisticaInversaField porque
// otro componente compartido (LogisticaInversaBadge, en badges.js) lo
// reutiliza para traducir value -> label; así se evita duplicar el
// catálogo en dos archivos.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

const h = React.createElement;

export const TIPOS_LOGISTICA_INVERSA = [
  {value:'estibas',      label:'Estibas'},
  {value:'canastillas',  label:'Canastillas'},
  {value:'devoluciones', label:'Devoluciones'},
  {value:'donaciones',   label:'Donaciones'},
  {value:'garantias',    label:'Garantías'},
  {value:'otros',        label:'Otros'},
];

// value: string[] | null   -- null = sin responder, [] = respondido "ninguno"
// onChange: (nuevoArray: string[] | null) => void
export function LogisticaInversaField({ value, onChange, required = true }) {
  const noAplica = Array.isArray(value) && value.length === 0;

  const toggleTipo = (tipo) => {
    const actual = Array.isArray(value) ? value : [];
    const yaMarcado = actual.includes(tipo);
    onChange(yaMarcado ? actual.filter(t => t !== tipo) : [...actual, tipo]);
  };

  const toggleNoAplica = () => onChange(noAplica ? null : []);

  return h('div', {className:'fg'},
    h('label', null, '¿Después del descargue recoge alguno de estos elementos?', required && h('span',{className:'req'},'*')),
    h('p', {style:{fontSize:11,color:'var(--slate)',margin:'-2px 0 2px'}}, 'Marca todas las que apliquen a esta visita.'),
    h('div', {className:'chk-grid'},
      ...TIPOS_LOGISTICA_INVERSA.map(op => {
        const checked = Array.isArray(value) && value.includes(op.value);
        return h('label', {key:op.value, className:'chk-opt'+(checked?' checked':'')},
          h('input', {type:'checkbox', checked, onChange:()=>toggleTipo(op.value)}),
          h('span', null, op.label)
        );
      }),
      h('label', {className:'chk-opt chk-noaplica'+(noAplica?' checked':'')},
        h('input', {type:'checkbox', checked:noAplica, onChange:toggleNoAplica}),
        h('span', null, 'No aplica a este vehículo')
      )
    ),
    noAplica && h('div', {style:{marginTop:6,padding:'6px 9px',borderRadius:7,fontSize:11,fontWeight:600,
      display:'flex',alignItems:'center',gap:5,background:'#f1f5f9',color:'#475569',border:'1px solid #e2e8f0'}},
      'Registrado: no aplica ningún tipo de logística inversa.'
    )
  );
}
