// ── MUELLE DETALLE PANEL (panel de detalle del muelle seleccionado) ──
// Extraído de frontend/index.html (líneas 5994-6061, comentarios + funciones
// MuelleLineaTiempo y MuelleDetallePanel, dentro de la sección "/* ── MUELLES
// (tablero de ocupación, solo lectura) ── */"). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado -- este
// módulo es una copia autocontenida, lista para que la Fase 6 lo importe
// cuando quede conectado vía <script type="module">.
//
// `hhmmT` y `LineaTiempoPasos` se promovieron a core/utils.js en la Fase 5
// (lote 7, paso 0): dejaron de duplicarse aquí y ahora este archivo las
// importa desde ahí, igual que LogisticaInversaSection.js y los componentes
// de pages/proveedores/ (DetalleTiempos y afines), que también las
// necesitan. Ver core/utils.js para el detalle de la desviación original.
//
// `MuelleLineaTiempo` es un helper privado de este archivo (solo lo usa
// MuelleDetallePanel), igual que el criterio ya usado con
// MuelleBotonConfirmar dentro de shared/ConfirmarMuelleSheet.js -- no se
// exporta por separado.
//
// Importa Ico (core/icons.js), hhmmT/LineaTiempoPasos (core/utils.js) y
// TipoCargaBadge (shared/badges.js).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { hhmmT, LineaTiempoPasos } from '../../core/utils.js';
import { TipoCargaBadge } from '../../shared/badges.js';

const h = React.createElement;

// Panel de detalle del muelle seleccionado (placa/conductor/empresas/tiempo)
// -- lo que antes mostraba cada card, ahora aparece solo bajo demanda porque
// la celda de 56-64px no tiene espacio para esa información. Un solo muelle
// seleccionado a la vez; se cierra con el botón X o tocando la misma celda.
// Línea de tiempo del vehículo que ocupa el muelle -- mismo patrón que
// DetalleTiempos en Proveedores (LineaTiempoPasos, línea ~778), con el
// mismo subconjunto de pasos salvo que NO incluye "Salida" (hora_salida)
// porque el vehículo sigue dentro del CEDI mientras aparece en este
// tablero -- ese paso todavía no aplica.
// No se usa .fcard (a diferencia de DetalleTiempos) porque este bloque ya
// vive dentro de .muelle-detalle, que es una tarjeta en sí misma -- envolver
// con otra tarjeta anidada duplicaría fondo/sombra/borde sin necesidad.
function MuelleLineaTiempo({muelle:m}){
  const pasos = [
    {icon:'calendar',    titulo:'Cita',              hora:hhmmT(m.hora_cita),               desc:'Hora que digitó el conductor'},
    {icon:'qrCode',      titulo:'Llegada/portería',  hora:hhmmT(m.hora_ingreso),            desc:'Autorregistro por QR en portería'},
    {icon:'upload',      titulo:'Ingresado a WPS',   hora:hhmmT(m.hora_wps),                desc:'Registrado en el sistema WPS'},
    {icon:'checkCircle', titulo:'Ingreso confirmado',hora:hhmmT(m.hora_ingreso_confirmado), desc:'Confirmado por el guarda vehicular'},
    {icon:'truck',       titulo:'Salida de muelle',  hora:hhmmT(m.hora_muelle_liberado),    desc:'Liberado por el guarda de bodega'},
  ];
  return h(React.Fragment,null,
    h('p',{className:'sec-ttl'},h(Ico,{n:'clock',s:12}),' Línea de tiempo'),
    h(LineaTiempoPasos,{pasos})
  );
}
export function MuelleDetallePanel({muelle:m, onCerrar, puedeLiberar, onLiberar}){
  const discordancia = m.tipo_carga_habitual && m.tipo_carga && m.tipo_carga_habitual!==m.tipo_carga;
  return h('div',{className:'muelle-detalle'},
    h('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:8,marginBottom:8}},
      h('div',{style:{minWidth:0}},
        h('p',{style:{fontWeight:800,fontSize:16,fontFamily:'Syne,sans-serif',lineHeight:1.15}},'Muelle '+m.numero),
        m.zona&&h('p',{style:{fontSize:11,color:'var(--slate)',marginTop:2}},m.zona)
      ),
      h('div',{style:{display:'flex',alignItems:'center',gap:6,flexShrink:0}},
        h('span',{className:'pill',style:{background:'var(--amber)',color:'var(--navy)'}},'Ocupado'),
        h('button',{type:'button',onClick:onCerrar,'aria-label':'Cerrar detalle del muelle',
          style:{background:'none',border:'none',cursor:'pointer',padding:4,color:'var(--slate)',display:'flex'}
        },h(Ico,{n:'x',s:16}))
      )
    ),
    m.tipo_carga_habitual&&h('div',{style:{marginBottom:8}},h(TipoCargaBadge,{tipo:m.tipo_carga_habitual})),
    h('p',{style:{fontSize:14,fontWeight:700}},m.placa_vehiculo||'Sin placa'),
    m.nombre_conductor&&h('p',{style:{fontSize:12,color:'var(--text2)',marginTop:1}},m.nombre_conductor),
    m.empresas&&h('p',{style:{fontSize:11,color:'#0e7490',fontWeight:600,marginTop:3}},m.empresas),
    m.tipo_carga&&h('div',{style:{marginTop:6}},h(TipoCargaBadge,{tipo:m.tipo_carga})),
    h('div',{style:{display:'flex',alignItems:'center',flexWrap:'wrap',gap:6,marginTop:8}},
      h('span',{style:{display:'inline-flex',alignItems:'center',gap:4,color:m.alerta_tiempo?'var(--red)':'var(--text2)'}},
        h(Ico,{n:'clock',s:12}),
        h('span',{style:{fontSize:11,fontWeight:700}},m.minutos_ocupado!=null?`${m.minutos_ocupado} min ocupado`:'—')
      ),
      m.alerta_tiempo&&h('span',{className:'pill pill-red'},'Tiempo excedido')
    ),
    discordancia&&h('div',{className:'muelle-discordancia'},
      h(Ico,{n:'alert',s:12}),
      h('span',null,'Carga distinta a la habitual de este muelle')
    ),
    h(MuelleLineaTiempo,{muelle:m}),
    // Acción operativa (libera un andén físico) -- gateada por el mismo
    // permiso "muelles":"liberar" que ya usa Proveedores (ver ProveedoresPage,
    // botón "Liberar muelle"), no un rol literal. proveedor_id viaja en el
    // payload de GET /muelles desde el cambio de backend que habilitó esto.
    puedeLiberar&&m.proveedor_id&&h('button',{
      type:'button',
      onClick:()=>onLiberar(m),
      style:{marginTop:12,width:'100%',background:'var(--purple)',border:'none',cursor:'pointer',color:'#fff',padding:'8px 12px',borderRadius:8,fontSize:12,fontWeight:700,display:'flex',alignItems:'center',justifyContent:'center',gap:6}
    },h(Ico,{n:'truck',s:14}),'Liberar muelle')
  );
}
