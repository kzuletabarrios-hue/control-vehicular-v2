// ── BASE DATOS · PROVEEDORES TAB ──
// Extraído de frontend/index.html (líneas 4346-4419, función
// BdProveedoresTab del <script> monolítico, tab de "BASE DATOS PAGE"). El
// código original en index.html NO fue tocado ni borrado.
//
// IMPORTANTE - no confundir con pages/proveedores/: este componente es el
// CRUD de catálogo de proveedores (maestros, tab dentro de BaseDatosPage).
// La futura carpeta pages/proveedores/ (ProveedoresPage, línea ~2743 del
// index.html actual) es la vista OPERATIVA de proveedores (agenda de
// citas, muelles, etc.), un módulo completamente distinto que no depende
// de este archivo ni comparte lógica con él.
//
// Importa Ico (core/icons.js), api (core/api-client.js), capitalizarNombre
// (core/utils.js) y los componentes compartidos Alert, LoadingDots,
// ConfirmSheet (shared/).
//
// Depende de React como global UMD, igual que el monolito original.

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { capitalizarNombre } from '../../core/utils.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function ProveedoresTab(){
  const [view,setView]       = useState('list');
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const [selected,setSelected]= useState(null);
  const emptyF = {nombre:'',nit:'',contacto:'',celular:''};
  const [form,setForm] = useState(emptyF);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/maestros/proveedores').then(setRecords).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    if(!form.nombre) return setAlert({type:'err',msg:'El nombre es requerido'});
    setSaving(true);
    try{
      if(selected) await api.put(`/maestros/proveedores/${selected.id}`,form);
      else await api.post('/maestros/proveedores',form);
      setAlert({type:'ok',msg:'Registro guardado'});
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'package',s:12}),' Datos del proveedor'),
        h('div',{className:'fg'},h('label',null,'Nombre / Razón social',h('span',{className:'req'},'*')),h('input',{type:'text',value:form.nombre,onChange:e=>setForm(p=>({...p,nombre:e.target.value})),placeholder:'Nombre'})),
        h('div',{className:'fg'},h('label',null,'NIT'),h('input',{type:'text',value:form.nit,onChange:e=>setForm(p=>({...p,nit:e.target.value})),placeholder:'900123456-7'})),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Contacto'),h('input',{type:'text',value:form.contacto,onChange:e=>setForm(p=>({...p,contacto:e.target.value})),onBlur:()=>setForm(p=>({...p,contacto:capitalizarNombre(p.contacto)})),placeholder:'Nombre'})),
          h('div',{className:'fg'},h('label',null,'Celular'),h('input',{type:'tel',value:form.celular,onChange:e=>setForm(p=>({...p,celular:e.target.value})),placeholder:'300 000 0000'}))
        )
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar')
    )
  );

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{display:'flex',padding:'8px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('button',{onClick:()=>setView('form'),style:{marginLeft:'auto',background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
        h(Ico,{n:'plus',s:15}),' Nuevo'
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      records.length===0?h('div',{className:'empty'},h(Ico,{n:'package',s:44}),h('p',null,'Sin proveedores')):
      records.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#fde68a'}},h(Ico,{n:'package',s:18,style:{color:'#d97706'}})),
        h('div',{className:'li-body',onClick:()=>{setForm({nombre:r.nombre,nit:r.nit||'',contacto:r.contacto||'',celular:r.celular||''});setSelected(r);setView('form');}},
          h('div',{className:'li-title'},r.nombre),
          h('div',{className:'li-sub'},r.nit?'NIT: '+r.nit:'Sin NIT'),
          r.contacto&&h('div',{className:'li-sub'},r.contacto+(r.celular?' · '+r.celular:''))
        ),
        h('div',{className:'li-right'},
          h('span',{className:`pill ${r.activo?'pill-green':'pill-slate'}`},r.activo?'Activo':'Inactivo'),
          h('button',{title:'Desactivar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger',style:{marginTop:6}},h(Ico,{n:'trash',s:13}))
        )
      ))
    ),
    confirm&&h(ConfirmSheet,{msg:'Se desactivará el proveedor.',onOk:async()=>{await api.del(`/maestros/proveedores/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Proveedor desactivado'});},onCancel:()=>setConfirm(null)})
  );
}
