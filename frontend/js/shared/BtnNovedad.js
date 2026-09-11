// ── BOTÓN FLOTANTE NOVEDAD ──
// Extraído de frontend/index.html (líneas 4936-5013, sección
// "/* ── BOTÓN FLOTANTE NOVEDAD ── */" del <script> monolítico). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado (ver notas de la Fase 2/3 del plan de migración) -- este módulo
// es una copia autocontenida, lista para que las fases posteriores lo
// importen cuando quede conectado vía <script type="module">.
//
// Depende de React (useState/useEffect globales), del icono compartido Ico
// (core/icons.js), del cliente `api` (core/api-client.js), y de los
// componentes compartidos Alert (./Alert.js) y CameraField (./CameraField.js).

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { Alert } from './Alert.js';
import { CameraField } from './CameraField.js';

const { useState, useEffect } = React;
const h = React.createElement;

export function BtnNovedad({user,moduloActual}){
  const [open,setOpen]     = useState(false);
  const [saving,setSaving] = useState(false);
  const [alert,setAlert]   = useState(null);
  const emptyF = {modulo_origen:moduloActual||'general',categoria:'otro',descripcion:'',fotografia:null};
  const [form,setForm]     = useState(emptyF);

  useEffect(()=>{ setForm(p=>({...p,modulo_origen:moduloActual||'general'})); },[moduloActual]);

  const handleSave = async()=>{
    if(!form.descripcion.trim()) return setAlert({type:'err',msg:'La descripción es requerida'});
    setSaving(true);
    try{
      await api.post('/novedades',form);
      setAlert({type:'ok',msg:'Novedad registrada correctamente'});
      setTimeout(()=>{ setOpen(false); setAlert(null); setForm(emptyF); },1400);
    }catch(e){ setAlert({type:'err',msg:'Error: '+e.message}); }
    finally{ setSaving(false); }
  };

  return h(React.Fragment,null,
    h('button',{
      onClick:()=>setOpen(true),
      title:'Registrar novedad',
      style:{position:'fixed',bottom:'68px',right:'14px',width:46,height:46,
        background:'var(--amber)',color:'var(--navy)',border:'none',borderRadius:'50%',
        cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',
        boxShadow:'0 4px 16px rgba(245,158,11,0.55)',zIndex:90}
    }, h(Ico,{n:'bell',s:19})),

    open&&h('div',{style:{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',zIndex:200,display:'flex',alignItems:'flex-end'}},
      h('div',{style:{background:'var(--white)',borderRadius:'20px 20px 0 0',width:'100%',maxHeight:'92vh',overflowY:'auto'}},
        h('div',{className:'sheet-handle'}),
        h('div',{className:'sheet-header',style:{padding:'0 16px 12px'}},
          h('h2',null,h(Ico,{n:'bell',s:16}),' Registrar Novedad'),
          h('button',{className:'btn-icon',onClick:()=>{setOpen(false);setAlert(null);}},h(Ico,{n:'x',s:15}))
        ),
        h('div',{style:{padding:'0 16px 24px'}},
          alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
          h('div',{className:'fg'},
            h('label',null,'Módulo de origen'),
            h('select',{value:form.modulo_origen,onChange:e=>setForm(p=>({...p,modulo_origen:e.target.value}))},
              h('option',{value:'general'},'General'),
              h('option',{value:'flota'},'Flota Propia'),
              h('option',{value:'proveedores'},'Proveedores'),
              h('option',{value:'acceso'},'Control Acceso'),
              h('option',{value:'visitantes'},'Visitantes'),
              h('option',{value:'ronda'},'Ronda')
            )
          ),
          h('div',{className:'fg'},
            h('label',null,'Categoría'),
            h('select',{value:form.categoria,onChange:e=>setForm(p=>({...p,categoria:e.target.value}))},
              h('option',{value:'seguridad'},'Seguridad'),
              h('option',{value:'mantenimiento'},'Mantenimiento'),
              h('option',{value:'logistica'},'Logística'),
              h('option',{value:'otro'},'Otro')
            )
          ),
          h('div',{className:'fg'},
            h('label',null,'Descripción',h('span',{className:'req'},'*')),
            h('textarea',{value:form.descripcion,onChange:e=>setForm(p=>({...p,descripcion:e.target.value})),
              rows:4,placeholder:'Describe la novedad encontrada...'})
          ),
          h('div',{className:'fg'},
            h('label',null,'Foto de evidencia (opcional)'),
            h(CameraField,{value:form.fotografia,onChange:v=>setForm(p=>({...p,fotografia:v}))})
          ),
          h('button',{className:'btn-primary',onClick:handleSave,disabled:saving,style:{width:'100%',marginTop:4}},
            saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),
            saving?'Guardando...':'Registrar novedad'
          )
        )
      )
    )
  );
}
