// ── DETALLE TIEMPOS (línea de tiempo de 6 pasos del ciclo de un proveedor) ──
// Extraído de frontend/index.html (líneas 479-499, función DetalleTiempos,
// justo antes de "/* ── LOGIN PAGE ── */"). Contenido idéntico al original:
// el código viejo en index.html NO fue tocado ni borrado -- este módulo es
// una copia autocontenida, lista para que la Fase 6 lo importe cuando quede
// conectado vía <script type="module">.
//
// Cita -> llegada -> ingreso confirmado -> salida de muelle -> salida del
// CEDI. Puramente informativo/solo lectura -- se inserta dentro de la vista
// de detalle de ProveedoresPage (view 'form', tanto para guarda_bodega como
// para el resto de roles) como un agregado, sin tocar el formulario editable
// ni sus acciones. Reutiliza .fcard/.sec-ttl/.pill y las variables de color
// ya establecidas en la hoja de estilos (nada de paleta nueva).
//
// Único consumidor exclusivo de Proveedores en el monolito (h(DetalleTiempos,
// {registro:form}) en las dos variantes de la vista 'form', líneas ~3146 y
// ~3195 del index.html actual) -- no estaba en la lista de 4 archivos del
// encargo del lote 7a, pero califica como "subcomponente adicional de uso
// exclusivo de proveedores" (desviación documentada, ver reporte del lote).
//
// A diferencia de MuelleLineaTiempo (Muelles), SÍ incluye el paso "Salida"
// (hora_salida) porque en Proveedores el vehículo sí completa su salida del
// CEDI; Muelles no llega a ese punto porque deja de aparecer en el tablero
// antes.
//
// Importa Ico (core/icons.js) y hhmmT/LineaTiempoPasos (core/utils.js,
// promovidas ahí en la Fase 5 lote 7 paso 0 -- antes vivían duplicadas en
// index.html líneas 443-478, fuente original de ambas funciones).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { hhmmT, LineaTiempoPasos } from '../../core/utils.js';

const h = React.createElement;

export function DetalleTiempos({registro}){
  const r = registro||{};
  const pasos = [
    {icon:'calendar',    titulo:'Cita',              hora:hhmmT(r.hora_cita),               desc:'Hora que digitó el conductor'},
    {icon:'qrCode',      titulo:'Llegada',            hora:hhmmT(r.hora_ingreso),            desc:'Autorregistro por QR en portería'},
    {icon:'upload',      titulo:'Ingresado a WPS',    hora:hhmmT(r.hora_wps),                desc:'Registrado en el sistema WPS'},
    {icon:'checkCircle', titulo:'Ingreso confirmado', hora:hhmmT(r.hora_ingreso_confirmado), desc:'Confirmado por el guarda vehicular'},
    {icon:'truck',       titulo:'Salida de muelle',   hora:hhmmT(r.hora_muelle_liberado),    desc:r.muelle_numero?`Liberado por el guarda de bodega — Muelle ${r.muelle_numero}`:'Liberado por el guarda de bodega'},
    {icon:'logOut',      titulo:'Salida',             hora:hhmmT(r.hora_salida),             desc:'Salida del CEDI confirmada por el guarda vehicular'},
  ];
  return h('div',{className:'fcard'},
    h('p',{className:'sec-ttl'},h(Ico,{n:'clock',s:12}),' Línea de tiempo'),
    h(LineaTiempoPasos,{pasos})
  );
}
