// ── LOADING DOTS ──
// Extraído de frontend/index.html (línea 500, dentro de la sección
// "/* ── COMPONENTS ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2/3 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que las fases posteriores lo importen cuando
// quede conectado vía <script type="module">.
//
// No estaba en el listado inicial de componentes compartidos de Alejandro
// (LogisticaInversaField, CameraField, badges, ConfirmSheet, Alert,
// StatCard, DetalleLista, TiendaPicker, QRScanner, BtnNovedad,
// ConfirmarMuelleSheet) pero se extrae aparte porque se usa en 26 puntos
// del monolito, en prácticamente todas las páginas (Home, Flota, Acceso,
// Proveedores, Muelles, Visitantes, Ronda, etc.) y también lo necesita
// CameraField.js (otro componente de esta misma carpeta) mientras sube una
// foto -- exportarlo en su propio archivo evita duplicar este componente
// de 1 línea o crear una dependencia entre CameraField.js y algún otro
// archivo de shared/ que no le corresponde.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

const h = React.createElement;

export function LoadingDots(){
  return h('div',{className:'loading-dots'},h('span'),h('span'),h('span'));
}
