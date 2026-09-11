// ── BASE DATOS · PERSONAS TAB ──
// Extraído de frontend/index.html (líneas 4263-4344, función BdPersonasTab
// del <script> monolítico, primer tab dentro de "BASE DATOS PAGE"). El
// código original en index.html NO fue tocado ni borrado.
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

export function PersonasTab(){
  const [view,setView]       = useState('list');
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const [selected,setSelected]= useState(null);
  const emptyF = {cedula:'',nombre:'',contratista:'',estado:'ACTIVO'};
  const [form,setForm] = useState(emptyF);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/maestros/control-acceso').then(setRecords).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    if(!form.cedula||!form.nombre) return setAlert({type:'err',msg:'Cédula y nombre son requeridos'});
    setSaving(true);
    try{
      if(selected) await api.put(`/maestros/control-acceso/${selected.cedula}`,{nombre:form.nombre,contratista:form.contratista,estado:form.estado});
      else await api.post('/maestros/control-acceso',{...form,cedula:parseInt(form.cedula)});
      setAlert({type:'ok',msg:'Registro guardado'});
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'user',s:12}),' Datos de la persona'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Cédula',h('span',{className:'req'},'*')),
            h('input',{type:'number',value:form.cedula,onChange:e=>setForm(p=>({...p,cedula:e.target.value})),placeholder:'Número',disabled:!!selected})
          ),
          h('div',{className:'fg'},h('label',null,'Estado'),
            h('select',{value:form.estado,onChange:e=>setForm(p=>({...p,estado:e.target.value}))},
              h('option',{value:'ACTIVO'},'ACTIVO'),h('option',{value:'INACTIVO'},'INACTIVO')
            )
          )
        ),
        h('div',{className:'fg'},h('label',null,'Nombre',h('span',{className:'req'},'*')),h('input',{type:'text',value:form.nombre,onChange:e=>setForm(p=>({...p,nombre:e.target.value})),onBlur:()=>setForm(p=>({...p,nombre:capitalizarNombre(p.nombre)})),placeholder:'Nombre completo'})),
        h('div',{className:'fg'},h('label',null,'Contratista / Empresa'),h('input',{type:'text',value:form.contratista,onChange:e=>setForm(p=>({...p,contratista:e.target.value})),placeholder:'Empresa'}))
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
      records.length===0?h('div',{className:'empty'},h(Ico,{n:'users',s:44}),h('p',null,'Sin registros')):
      records.map(r=>h('div',{key:r.cedula,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#dbeafe'}},h(Ico,{n:'user',s:18,style:{color:'#1d4ed8'}})),
        h('div',{className:'li-body',onClick:()=>{setForm({cedula:String(r.cedula),nombre:r.nombre,contratista:r.contratista||'',estado:r.estado||'ACTIVO'});setSelected(r);setView('form');}},
          h('div',{className:'li-title'},r.nombre),
          h('div',{className:'li-sub'},r.contratista||'Sin empresa')
        ),
        h('div',{className:'li-right'},
          h('span',{className:`pill ${r.estado==='ACTIVO'?'pill-green':'pill-slate'}`},r.estado||'ACTIVO'),
          h('div',{style:{display:'flex',alignItems:'center',gap:4,marginTop:4}},
            h('span',{style:{fontSize:10,color:'var(--slate)'}},r.cedula),
            h('button',{title:'Desactivar',onClick:(e)=>{e.stopPropagation();setConfirm(r.cedula);},className:'li-act li-act-danger'},h(Ico,{n:'trash',s:13}))
          )
        )
      ))
    ),
    confirm&&h(ConfirmSheet,{msg:'Se marcará como INACTIVO.',onOk:async()=>{await api.del(`/maestros/control-acceso/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Persona desactivada'});},onCancel:()=>setConfirm(null)})
  );
}
