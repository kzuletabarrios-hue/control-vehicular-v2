// ── KIOSCO QR (pantalla fija de portería con el QR de autorregistro) ──
// Extraído de frontend/index.html (líneas 2962-2981, rama
// `if(view==='qr') return ...` dentro de ProveedoresPage, sección
// "/* ── PROVEEDORES PAGE ── */"). Contenido idéntico al original: el
// código viejo en index.html NO fue tocado ni borrado -- este módulo es una
// copia autocontenida, lista para que la Fase 6 lo importe cuando quede
// conectado vía <script type="module">.
//
// A diferencia de EditarRegistro/NuevoIngreso/CitasWMS (ver desviación
// documentada en el reporte del lote 7a), esta vista SÍ es un fragmento
// realmente autocontenido dentro del monolito: solo lee `qrImgUrl`/`qrError`
// y dispara `setView('list')`/`setQrError(null)`, sin tocar ninguno de los
// demás ~40 states/handlers del closure de ProveedoresPage. Por eso se pudo
// extraer ya como componente puro con props, sin esperar al lote 7b.
//
// El fetch del QR (`fetchQr`, useVisibilityPolling cada 90s) y su estado
// (`qrImgUrl`/`qrError`) NO viajan con este componente -- siguen en
// ProveedoresPage (o, en el lote 7b, en el futuro contenedor de
// pages/proveedores/index.js), que es quien sabe cuándo `view==='qr'` está
// activa y debe encender/apagar el polling. KioscoQR solo recibe el
// resultado ya resuelto vía props, igual que MuelleDetallePanel recibe
// `muelle` ya resuelto de MuellesPage.
//
// Importa Ico (core/icons.js), Alert y LoadingDots (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';

const h = React.createElement;

// `onVolver`: handler del botón "Volver" (en el monolito: `()=>setView('list')`).
// `onDismissError`: handler para cerrar el Alert de error (en el monolito:
// `()=>setQrError(null)`).
export function KioscoQR({qrImgUrl, qrError, onVolver, onDismissError}){
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:onVolver,style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,'QR Ingreso Proveedores'),h('span',null,'Portería'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'24px 14px',display:'flex',flexDirection:'column',alignItems:'center',textAlign:'center'}},
      h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:16,maxWidth:340}},
        'Pega esta pantalla en la portería para que los conductores de proveedores escaneen el QR y registren su ingreso. El código se renueva solo cada 60 segundos — una foto guardada del QR deja de funcionar en poco tiempo.'
      ),
      qrError&&h(Alert,{type:'err',msg:qrError,onClose:onDismissError}),
      qrImgUrl
        ? h('img',{src:qrImgUrl,style:{width:280,height:280,background:'#fff',border:'1px solid var(--border)',borderRadius:16,padding:16}})
        : h(LoadingDots),
      h('p',{style:{fontSize:11,color:'var(--slate)',marginTop:16}},'Se actualiza automáticamente. No cierres esta pantalla.')
    )
  );
}
