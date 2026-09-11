// ── ENTRY POINT ──
// Punto de entrada de la app modularizada (Fase 6 del plan de Alejandro).
// Reemplaza el <script> monolítico de frontend/index.html: monta el árbol
// de React igual que lo hacía el monolito (`ReactDOM.createRoot(...).render(...)`),
// pero ahora resolviendo App() desde ./App.js vía import de ES Modules
// nativos (sin bundler).
//
// Depende de React/ReactDOM como globals UMD (cargados por los <script src=
// "https://cdn..."> en el <head> de index.html) -- no se importan como
// módulos ES porque esas libs se sirven como build UMD, no ESM. xlsx y
// html5-qrcode también se cargan igual, como globals, para los módulos que
// los usan (CargaMasivaPage, QRScanner).

import { App } from './App.js';

const h = React.createElement;

ReactDOM.createRoot(document.getElementById('root')).render(h(App));
