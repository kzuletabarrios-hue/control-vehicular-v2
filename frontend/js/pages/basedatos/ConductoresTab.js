// ── BASE DATOS · CONDUCTORES TAB ──
// Extraído de frontend/index.html (líneas 4502-4601, función
// BdConductoresTab del <script> monolítico, tab de "BASE DATOS PAGE"). El
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

export function ConductoresTab(){
  const [view,setView]        = useState('list');
  const [records,setRecords]  = useState([]);
  const [loading,setLoading]  = useState(true);
  const [saving,setSaving]    = useState(false);
  const [alert,setAlert]      = useState(null);
  const [confirm,setConfirm]  = useState(null);
  const [selected,setSelected]= useState(null);
  const emptyF = {conductor:'',codigo:'',n_cedula:'',celular:'',tipo:'',activo:true};
  const [form,setForm] = useState(emptyF);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/conductores').then(setRecords).catch(()=>setAlert({type:'err',msg:'Error cargando conductores'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    if(!form.conductor) return setAlert({type:'err',msg:'El nombre del conductor es requerido'});
    setSaving(true);
    try{
      const payload = {conductor:form.conductor,n_cedula:form.n_cedula,celular:form.celular,tipo:form.tipo,activo:form.activo};
      if(form.codigo) payload.codigo = parseInt(form.codigo);
      if(selected) await api.put(`/conductores/${selected.id}`,payload);
      else await api.post('/conductores',payload);
      setAlert({type:'ok',msg:'Conductor guardado'});
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'truck',s:12}),' Datos del conductor'),
        h('div',{className:'fg'},h('label',null,'Nombre',h('span',{className:'req'},'*')),
          h('input',{type:'text',value:form.conductor,onChange:e=>setForm(p=>({...p,conductor:e.target.value})),onBlur:()=>setForm(p=>({...p,conductor:capitalizarNombre(p.conductor)})),placeholder:'Nombre completo'})
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Código'),
            h('input',{type:'number',value:form.codigo,onChange:e=>setForm(p=>({...p,codigo:e.target.value})),placeholder:'001',disabled:!!selected})
          ),
          h('div',{className:'fg'},h('label',null,'Cédula'),
            h('input',{type:'text',value:form.n_cedula,onChange:e=>setForm(p=>({...p,n_cedula:e.target.value})),placeholder:'CC / NIT'})
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Celular'),
            h('input',{type:'tel',value:form.celular,onChange:e=>setForm(p=>({...p,celular:e.target.value})),placeholder:'300 000 0000'})
          ),
          h('div',{className:'fg'},h('label',null,'Tipo'),
            h('select',{value:form.tipo,onChange:e=>setForm(p=>({...p,tipo:e.target.value}))},
              h('option',{value:''},'Seleccionar...'),
              h('option',{value:'Propio'},'Propio'),
              h('option',{value:'Tercero'},'Tercero')
            )
          )
        ),
        selected&&h('div',{className:'fg'},h('label',null,'Estado'),
          h('select',{value:String(form.activo),onChange:e=>setForm(p=>({...p,activo:e.target.value==='true'}))},
            h('option',{value:'true'},'Activo'),h('option',{value:'false'},'Inactivo')
          )
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
      records.length===0?h('div',{className:'empty'},h(Ico,{n:'truck',s:44}),h('p',null,'Sin conductores registrados')):
      records.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#dbeafe'}},h(Ico,{n:'truck',s:18,style:{color:'#1d4ed8'}})),
        h('div',{className:'li-body',onClick:()=>{setForm({conductor:r.conductor,codigo:r.codigo||'',n_cedula:r.n_cedula||'',celular:r.celular||'',tipo:r.tipo||'',activo:r.activo!==false});setSelected(r);setView('form');}},
          h('div',{className:'li-title'},r.conductor),
          h('div',{className:'li-sub'},(r.tipo||'Sin tipo')+(r.n_cedula?' · CC '+r.n_cedula:''))
        ),
        h('div',{className:'li-right'},
          h('span',{className:`pill ${r.activo!==false?'pill-green':'pill-slate'}`},r.activo!==false?'Activo':'Inactivo'),
          h('div',{style:{display:'flex',alignItems:'center',gap:4,marginTop:4}},
            r.codigo&&h('span',{style:{fontSize:10,color:'var(--slate)'}},`#${r.codigo}`),
            h('button',{title:'Desactivar',onClick:e=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger'},h(Ico,{n:'trash',s:13}))
          )
        )
      ))
    ),
    confirm&&h(ConfirmSheet,{msg:'Se desactivará el conductor.',onOk:async()=>{await api.del(`/conductores/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Conductor desactivado'});},onCancel:()=>setConfirm(null)})
  );
}
