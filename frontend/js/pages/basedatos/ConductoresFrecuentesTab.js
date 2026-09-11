// ── BASE DATOS · CONDUCTORES FRECUENTES TAB ──
// Extraído de frontend/index.html (líneas 4710-4827, función
// BdConductoresFrecuentesTab del <script> monolítico, tab de "BASE DATOS
// PAGE"). El código original en index.html NO fue tocado ni borrado.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// capitalizarNombre/fmtDate (core/utils.js) y los componentes compartidos
// Alert, LoadingDots, ConfirmSheet (shared/).
//
// Depende de React como global UMD, igual que el monolito original.

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { capitalizarNombre, fmtDate } from '../../core/utils.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function ConductoresFrecuentesTab(){
  const [records,setRecords]    = useState([]);
  const [loading,setLoading]    = useState(true);
  const [saving,setSaving]      = useState(false);
  const [alert,setAlert]        = useState(null);
  const [confirm,setConfirm]    = useState(null);
  const [view,setView]          = useState('list');
  const [selected,setSelected]  = useState(null);
  const [busqueda,setBusqueda]  = useState('');
  const tiposVeh = ['Camión','Camioneta','Moto','Furgón','Tractomula','Otro'];
  const emptyF = {cedula:'',nombre_conductor:'',telefono:'',empresa_principal:'',tipo_vehiculo:'',activo:true};
  const [form,setForm] = useState(emptyF);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/maestros/conductores-frecuentes').then(setRecords).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    if(!form.cedula.trim()||!form.nombre_conductor.trim()) return setAlert({type:'err',msg:'Cédula y nombre son requeridos'});
    setSaving(true);
    try{
      if(selected) await api.put(`/maestros/conductores-frecuentes/${selected.id}`,form);
      else await api.post('/maestros/conductores-frecuentes',form);
      setAlert({type:'ok',msg:'Conductor guardado'});
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  const visibles = records.filter(r=>{
    if(!busqueda.trim()) return true;
    const q=busqueda.toLowerCase();
    return String(r.cedula).includes(q)||(r.nombre_conductor||'').toLowerCase().includes(q)||(r.empresa_principal||'').toLowerCase().includes(q);
  });

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'user',s:12}),selected?' Editar conductor frecuente':' Nuevo conductor frecuente'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Cédula',h('span',{className:'req'},'*')),
            h('input',{type:'text',value:form.cedula,onChange:e=>setForm(p=>({...p,cedula:e.target.value})),placeholder:'Número de cédula',
              readOnly:!!selected,style:selected?{background:'#f8fafc',cursor:'default'}:{}})
          ),
          h('div',{className:'fg'},
            h('label',null,'Nombre conductor',h('span',{className:'req'},'*')),
            h('input',{type:'text',value:form.nombre_conductor,onChange:e=>setForm(p=>({...p,nombre_conductor:e.target.value})),onBlur:()=>setForm(p=>({...p,nombre_conductor:capitalizarNombre(p.nombre_conductor)})),placeholder:'Nombre completo'})
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Teléfono'),
            h('input',{type:'tel',value:form.telefono,onChange:e=>setForm(p=>({...p,telefono:e.target.value})),placeholder:'Número de contacto (opcional)'})
          ),
          h('div',{className:'fg'},
            h('label',null,'Empresa principal'),
            h('input',{type:'text',value:form.empresa_principal,onChange:e=>setForm(p=>({...p,empresa_principal:e.target.value})),placeholder:'Empresa habitual'})
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'Tipo vehículo'),
          h('select',{value:form.tipo_vehiculo,onChange:e=>setForm(p=>({...p,tipo_vehiculo:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),...tiposVeh.map(t=>h('option',{key:t,value:t},t))
          )
        ),
        selected&&h('div',{className:'fg'},
          h('label',null,'Estado'),
          h('select',{value:form.activo?'activo':'inactivo',onChange:e=>setForm(p=>({...p,activo:e.target.value==='activo'}))},
            h('option',{value:'activo'},'Activo'),h('option',{value:'inactivo'},'Inactivo')
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
    h('div',{style:{display:'flex',gap:8,padding:'8px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0,alignItems:'center'}},
      h('div',{style:{position:'relative',flex:1}},
        h(Ico,{n:'search',s:13,style:{position:'absolute',left:9,top:'50%',transform:'translateY(-50%)',color:'var(--slate)',pointerEvents:'none'}}),
        h('input',{type:'text',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar cédula, nombre, empresa...',style:{width:'100%',paddingLeft:28,fontSize:12,boxSizing:'border-box'}})
      ),
      h('button',{onClick:()=>{setForm(emptyF);setSelected(null);setView('form');},style:{flexShrink:0,background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
        h(Ico,{n:'plus',s:15}),' Nuevo'
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:'user',s:44}),h('p',null,busqueda.trim()?`Sin resultados para "${busqueda}"`: 'Sin conductores frecuentes registrados')):
      visibles.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:r.activo?'#d1fae5':'#f1f5f9'}},
          h(Ico,{n:'user',s:18,style:{color:r.activo?'#059669':'#94a3b8'}})
        ),
        h('div',{className:'li-body',onClick:()=>{
          setForm({cedula:r.cedula||'',nombre_conductor:r.nombre_conductor||'',telefono:r.telefono||'',empresa_principal:r.empresa_principal||'',tipo_vehiculo:r.tipo_vehiculo||'',activo:r.activo});
          setSelected(r);setView('form');
        }},
          h('div',{className:'li-title'},r.nombre_conductor),
          h('div',{className:'li-sub'},'CC '+r.cedula+(r.empresa_principal?' · '+r.empresa_principal:'')+(r.tipo_vehiculo?' · '+r.tipo_vehiculo:'')+(r.telefono?' · 📞 '+r.telefono:'')),
          r.ultima_visita&&h('div',{className:'li-sub',style:{color:'#059669',fontWeight:600}},'Última visita: '+fmtDate(r.ultima_visita))
        ),
        h('div',{className:'li-right'},
          h('span',{className:`pill ${r.activo?'pill-green':'pill-slate'}`},r.activo?'Activo':'Inactivo'),
          h('button',{title:'Desactivar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger',style:{marginTop:6}},h(Ico,{n:'trash',s:13}))
        )
      ))
    ),
    confirm&&h(ConfirmSheet,{msg:'Se marcará como inactivo este conductor frecuente.',onOk:async()=>{await api.del(`/maestros/conductores-frecuentes/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Conductor desactivado'});},onCancel:()=>setConfirm(null)})
  );
}
