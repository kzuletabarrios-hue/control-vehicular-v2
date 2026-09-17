// ── MUELLES PAGE (tablero de ocupación, solo lectura) ──
// Extraído de frontend/index.html (líneas 5957-5963 y 6116-6214, comentario
// de sección "/* ── MUELLES (tablero de ocupación, solo lectura) ── */" y
// función MuellesPage). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado -- este módulo es una copia
// autocontenida, lista para que la Fase 6 lo importe cuando quede conectado
// vía <script type="module">.
//
// Fase 2 de la consolidación con citas-muelles-cedi-r10: esta pantalla NO
// tiene ningún control de escritura (asignar/crear/editar muelle) a
// propósito -- decisión del arquitecto para no abrir una segunda vía de
// escritura sobre el mismo estado operativo que hoy gestionan los guardas
// en la otra app. La única acción operativa que sí expone es "liberar
// muelle" (gateada por el permiso "muelles":"liberar"), igual que ya hace
// ProveedoresPage.
//
// Este archivo es el punto de entrada de la carpeta pages/muelles/: importa
// y compone MuelleCelda (./MuelleCelda.js), MuelleDetallePanel
// (./MuelleDetallePanel.js) y MuellesLogisticaInversaSection
// (./LogisticaInversaSection.js, la sección del tablero 20-22 montada como
// último hijo del .scroll-body).
//
// Importa Ico (core/icons.js), api (core/api-client.js), puede
// (core/utils.js), useVisibilityPolling (core/hooks.js), Alert, LoadingDots
// y ConfirmSheet (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { puede } from '../../core/utils.js';
import { useVisibilityPolling } from '../../core/hooks.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';
import { MuelleCelda } from './MuelleCelda.js';
import { MuelleDetallePanel } from './MuelleDetallePanel.js';
import { MuellesLogisticaInversaSection } from './LogisticaInversaSection.js';

const { useState, useCallback } = React;
const h = React.createElement;

export function MuellesPage({user}){
  const [muelles,setMuelles] = useState([]);
  const [loading,setLoading] = useState(true);
  const [error,setError]     = useState(null);
  // Un solo muelle seleccionado a la vez para el panel de detalle. Guarda
  // el id (no el objeto completo) para que el panel siempre muestre el dato
  // más reciente tras cada refresco del polling.
  const [seleccionId,setSeleccionId] = useState(null);
  // Confirmación antes de liberar (mismo patrón que ProveedoresPage: no es
  // un solo clic para una acción operativa que libera un andén físico).
  const [liberando,setLiberando] = useState(null);
  const [alert,setAlert]         = useState(null);
  const puedeLiberar = puede(user,'muelles','liberar');

  const load = useCallback(()=>{
    api.get('/muelles')
      .then(r=>{ setMuelles(Array.isArray(r)?r:(r.items||[])); setError(null); })
      .catch(()=>setError('No se pudo cargar el estado de los muelles'))
      .finally(()=>setLoading(false));
  },[]);
  // Igual que Flota/Proveedores: es un tablero operativo (guardas y
  // coordinador lo miran para saber qué muelle está libre), así que se
  // refresca cada minuto y se pausa en background.
  useVisibilityPolling(load, 60000, [load]);

  const ocupados = muelles.filter(m=>m.estado==='ocupado').length;
  const seleccionarMuelle = id => setSeleccionId(prev=>prev===id?null:id);
  // Si el muelle seleccionado se liberó (o desapareció) en un refresco de
  // polling, no queda nada que mostrar y el panel simplemente no se pinta.
  const muelleSeleccionado = seleccionId!=null ? muelles.find(m=>m.id===seleccionId && m.estado==='ocupado') : null;

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('div',{className:'header-brand'},h('h1',null,'Muelles'),h('span',null,'Vista de consulta'))
      )
    ),
    h('div',{style:{padding:'10px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)'}},
      h('p',{style:{fontSize:11,color:'var(--slate)'}},
        'Estado de ocupación derivado del registro de ingreso de Proveedores — vista de solo consulta.'
      ),
      !loading&&!error&&muelles.length>0&&h('p',{style:{fontSize:11,color:'var(--text2)',fontWeight:700,marginTop:6}},
        `${ocupados} ocupado${ocupados===1?'':'s'} de ${muelles.length}`
      ),
      // Leyenda del tablero: solo los 4 estados/indicadores que existen hoy
      // en la grilla (ver comentario de .muelle-leyenda en la hoja de
      // estilos). No incluye REF/SEC/MIX -- esa etiqueta ya se explica sola
      // dentro de cada celda y agregarla aquí solo suma ruido a una leyenda
      // que debe leerse de un vistazo.
      !loading&&!error&&muelles.length>0&&h('div',{className:'muelle-leyenda'},
        h('span',{className:'muelle-leyenda-item'},
          h('span',{className:'muelle-leyenda-swatch libre','aria-hidden':'true'}),'Libre'
        ),
        h('span',{className:'muelle-leyenda-item'},
          h('span',{className:'muelle-leyenda-swatch ocupado','aria-hidden':'true'}),'Ocupado'
        ),
        h('span',{className:'muelle-leyenda-item'},
          h('span',{className:'muelle-leyenda-swatch alerta','aria-hidden':'true'}),'Tiempo excedido'
        ),
        h('span',{className:'muelle-leyenda-item'},
          h('span',{className:'muelle-leyenda-dot','aria-hidden':'true'}),'Carga distinta a la habitual'
        )
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      error&&h(Alert,{type:'err',msg:error,onClose:()=>setError(null)}),
      alert&&h(Alert,{type:alert.type,msg:alert.msg,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      muelles.length===0?h('div',{className:'empty'},h(Ico,{n:'mapPin',s:44}),h('p',null,'No hay muelles configurados todavía')):
      h(React.Fragment,null,
        muelleSeleccionado&&h(MuelleDetallePanel,{
          muelle:muelleSeleccionado,onCerrar:()=>setSeleccionId(null),
          puedeLiberar, onLiberar:m=>setLiberando(m)
        }),
        h('div',{className:'muelle-grid'},muelles.map(m=>h(MuelleCelda,{
          key:m.id,muelle:m,seleccionado:m.id===seleccionId,onSeleccionar:seleccionarMuelle
        })))
      ),
      h(MuellesLogisticaInversaSection,{user}),
      liberando&&h(ConfirmSheet,{
        icon:'truck',
        titulo:`¿Liberar el muelle ${liberando.numero}?`,
        textoOk:'Liberar muelle',
        colorOk:'var(--purple)',
        msg:`El vehículo ${liberando.placa_vehiculo||''} dejará de ocupar el muelle ${liberando.numero}. Esto libera el espacio para el panel de disponibilidad, pero NO registra la salida del vehículo del CEDI.`,
        onOk:async()=>{
          try{
            await api.put(`/proveedores/${liberando.proveedor_id}/liberar-muelle`,{});
            setLiberando(null); load(); setAlert({type:'ok',msg:'Muelle liberado'});
          }catch(e){
            setLiberando(null); load();
            setAlert({type:'err',msg:'Error: '+e.message});
          }
        },
        onCancel:()=>setLiberando(null)
      })
    )
  );
}
