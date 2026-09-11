// ── TABLERO DE MUELLES PARA CONFIRMAR INGRESO (guarda vehicular) ──
// Extraído de frontend/index.html (líneas 2643-2740, sección
// "/* ── TABLERO DE MUELLES PARA CONFIRMAR INGRESO (guarda vehicular) ── */"
// del <script> monolítico, incluye el helper privado MuelleBotonConfirmar
// que solo usa este componente). Contenido idéntico al original: el código
// viejo en index.html NO fue tocado ni borrado (ver notas de la Fase 2/3
// del plan de migración) -- este módulo es una copia autocontenida, lista
// para que las fases posteriores lo importen cuando quede conectado vía
// <script type="module">.
//
// Alejandro lo llamó "MuelleConfirmarSheet.js" en el plan original, pero
// se usa este nombre (ConfirmarMuelleSheet.js) para que coincida con el
// nombre real del componente en el monolito (`function ConfirmarMuelleSheet`)
// y con lo que ya documentó el agente anterior en ConfirmSheet.js
// (líneas 10-11 de ese archivo).
//
// Se abre al tocar "Confirmar" en Proveedores en vez de confirmar directo:
// deja elegir el muelle en el mismo gesto, sin abrir la tarjeta completa del
// registro. Es una versión reducida a propósito de lo que ya muestra
// MuellesPage (MuelleCelda/MuelleDetallePanel) -- acá NO se muestra tiempo
// excedido, línea de tiempo ni discordancia de carga, porque eso es ruido
// en un selector pensado para tacto rápido en portería; esa información
// completa sigue viviendo solo en la pantalla dedicada de Muelles.
//
// Depende de React (useState/useEffect globales), del icono compartido Ico
// (core/icons.js), del cliente `api` (core/api-client.js), y de los
// componentes compartidos Alert (./Alert.js), LoadingDots (./LoadingDots.js),
// ConfirmSheet (./ConfirmSheet.js) y TipoCargaBadgeMini (./badges.js) --
// ninguno se duplica aquí.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { Alert } from './Alert.js';
import { LoadingDots } from './LoadingDots.js';
import { ConfirmSheet } from './ConfirmSheet.js';
import { TipoCargaBadgeMini } from './badges.js';

const { useState, useEffect } = React;
const h = React.createElement;

// Helper privado: solo lo usa ConfirmarMuelleSheet, no se comparte con
// ningún otro componente de shared/ (verificado con búsqueda en
// index.html) -- se mantiene en este mismo archivo en vez de crear un
// MuelleBotonConfirmar.js aparte.
function MuelleBotonConfirmar({muelle:m, onElegir}){
  const ocupado = m.estado==='ocupado';
  const clases = ['muelle-confirmar-celda', ocupado?'ocupado':'libre'];
  return h('button',{
    type:'button',
    className:clases.join(' '),
    onClick:()=>onElegir(m),
    'aria-label':`Muelle ${m.numero} — ${ocupado?'ocupado':'libre'}`,
    title:`Muelle ${m.numero} — ${ocupado?'ocupado':'libre'}`
  },
    h('span',{className:'muelle-confirmar-num'},m.numero),
    ocupado
      ? h('span',{className:'muelle-confirmar-sub'},(m.placa_vehiculo||'Sin placa')+(m.minutos_ocupado!=null?` · ${m.minutos_ocupado}m`:''))
      : (m.tipo_carga_habitual&&h(TipoCargaBadgeMini,{tipo:m.tipo_carga_habitual}))
  );
}

export function ConfirmarMuelleSheet({registro, onClose, onElegirMuelle, onSinMuelle, endpoint='/muelles', titulo='Elegir muelle', ocultarSinMuelle=false}){
  const [muelles,setMuelles] = useState([]);
  const [loading,setLoading] = useState(true);
  const [error,setError]     = useState(null);
  const [saving,setSaving]   = useState(false);
  const [ocupadoPend,setOcupadoPend] = useState(null); // muelle ocupado esperando el tap de confirmación

  useEffect(()=>{
    api.get(endpoint)
      .then(r=>setMuelles(Array.isArray(r)?r:(r.items||[])))
      .catch(()=>setError('No se pudo cargar el estado de los muelles'))
      .finally(()=>setLoading(false));
  },[endpoint]);

  const elegir = (m)=>{
    if(saving) return;
    if(m.estado==='ocupado'){ setOcupadoPend(m); return; }
    setSaving(true);
    onElegirMuelle(m.numero);
  };
  const confirmarOcupado = ()=>{
    if(saving||!ocupadoPend) return;
    setSaving(true);
    onElegirMuelle(ocupadoPend.numero);
  };
  const sinMuelle = ()=>{
    if(saving) return;
    setSaving(true);
    onSinMuelle();
  };

  return h('div',{className:'overlay',onClick:saving?undefined:onClose},
    h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
      h('div',{className:'sheet-header'},
        h('span',{style:{fontWeight:700,fontSize:15}},titulo),
        h('button',{className:'btn-icon',onClick:onClose,disabled:saving},h(Ico,{n:'x',s:16}))
      ),
      h('p',{style:{fontSize:12,color:'var(--slate)',marginBottom:12}},
        (registro.nombre_conductor||'Vehículo')+(registro.placa_vehiculo?' · '+registro.placa_vehiculo:'')
      ),
      error&&h(Alert,{type:'err',msg:error,onClose:()=>setError(null)}),
      loading?h(LoadingDots):
      muelles.length===0?h('div',{className:'empty'},h(Ico,{n:'mapPin',s:36}),h('p',null,'No hay muelles configurados')):
      h('div',{className:'muelle-confirmar-grid'},
        muelles.map(m=>h(MuelleBotonConfirmar,{key:m.id,muelle:m,onElegir:elegir}))
      ),
      !ocultarSinMuelle&&h('div',{style:{textAlign:'center',marginTop:16}},
        h('button',{
          type:'button',
          onClick:sinMuelle,
          disabled:saving,
          style:{background:'none',border:'none',color:'var(--slate)',fontSize:12,fontWeight:600,textDecoration:'underline',cursor:saving?'default':'pointer',padding:6}
        },saving?'Confirmando...':'Confirmar sin muelle')
      ),
      ocupadoPend&&h(ConfirmSheet,{
        icon:'alert',
        titulo:`¿Muelle ${ocupadoPend.numero} ocupado?`,
        textoOk:'Confirmar igual',
        colorOk:'#d97706',
        msg:`Muelle ${ocupadoPend.numero} ocupado por ${ocupadoPend.placa_vehiculo||'un vehículo'}${ocupadoPend.minutos_ocupado!=null?` hace ${ocupadoPend.minutos_ocupado} min`:''}. ¿Confirmar el ingreso igual en este muelle?`,
        onOk:confirmarOcupado,
        onCancel:()=>setOcupadoPend(null)
      })
    )
  );
}
