// ── BASE DATOS · TIENDAS TAB ──
// Extraído de frontend/index.html (líneas 4421-4500, función BdTiendasTab
// del <script> monolítico, tab de "BASE DATOS PAGE"). El código original
// en index.html NO fue tocado ni borrado.
//
// Importa Ico (core/icons.js), api (core/api-client.js) y los componentes
// compartidos Alert, LoadingDots, ConfirmSheet (shared/).
//
// Depende de React como global UMD, igual que el monolito original.

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function TiendasTab(){
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const emptyF = {codigo:'',name:'',direccion:''};
  const [form,setForm] = useState(emptyF);
  const [editingId,setEditingId] = useState(null);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/maestros/distribucion').then(setRecords).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleCodigo = (val) => {
    setForm(p=>({...p,codigo:val}));
    const existente = records.find(r=>String(r.codigo)===String(val).trim() && val.trim()!=='');
    if(existente){
      setForm({codigo:String(existente.codigo),name:existente.name,direccion:existente.direccion||''});
      setEditingId(existente.id);
    } else if(editingId){
      setEditingId(null);
    }
  };

  const handleSave = async()=>{
    if(!form.name.trim()) return setAlert({type:'err',msg:'El nombre de la tienda es requerido'});
    setSaving(true);
    try{
      const body = {codigo:form.codigo.trim()||null, name:form.name.trim(), direccion:form.direccion.trim()||null};
      if(editingId) await api.put(`/maestros/distribucion/${editingId}`,body);
      else await api.post('/maestros/distribucion',body);
      setAlert({type:'ok',msg:editingId?'Tienda actualizada':'Tienda agregada'});
      setForm(emptyF);setEditingId(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'plus',s:12}),editingId?' Editar tienda':' Nueva tienda'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'COD'),
            h('input',{type:'text',value:form.codigo,onChange:e=>handleCodigo(e.target.value),placeholder:'1025'})
          ),
          h('div',{className:'fg'},
            h('label',null,'Nombre'),
            h('input',{type:'text',value:form.name,onChange:e=>setForm(p=>({...p,name:e.target.value})),placeholder:'Nombre de la tienda'})
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'Dirección'),
          h('input',{type:'text',value:form.direccion,onChange:e=>setForm(p=>({...p,direccion:e.target.value})),placeholder:'Dirección',onKeyDown:e=>e.key==='Enter'&&handleSave()})
        ),
        h('div',{style:{display:'flex',gap:8,justifyContent:'flex-end'}},
          editingId&&h('button',{onClick:()=>{setForm(emptyF);setEditingId(null);},style:{background:'none',border:'1px solid var(--border)',borderRadius:8,padding:'11px 16px',cursor:'pointer',fontWeight:700,fontSize:13,fontFamily:'inherit'}},'Cancelar'),
          h('button',{onClick:handleSave,disabled:saving,style:{background:'var(--navy2)',color:'#fff',border:'none',borderRadius:8,padding:'11px 16px',cursor:'pointer',fontWeight:700,fontSize:13,fontFamily:'inherit',display:'flex',alignItems:'center',gap:5,flexShrink:0}},
            saving?h('div',{className:'spinner'}):h(Ico,{n:editingId?'save':'plus',s:15}),editingId?'Guardar':'Agregar'
          )
        )
      ),
      loading?h(LoadingDots):
      records.length===0?h('div',{className:'empty'},h(Ico,{n:'database',s:44}),h('p',null,'Sin tiendas registradas')):
      records.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#f1f5f9'}},h(Ico,{n:'database',s:18,style:{color:'#475569'}})),
        h('div',{className:'li-body',onClick:()=>{setForm({codigo:r.codigo!=null?String(r.codigo):'',name:r.name,direccion:r.direccion||''});setEditingId(r.id);}},
          h('div',{className:'li-title'},r.codigo?`${r.codigo} - ${r.name}`:r.name),
          r.direccion&&h('div',{className:'li-sub'},r.direccion)
        ),
        h('button',{title:'Eliminar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger'},h(Ico,{n:'trash',s:14}))
      ))
    ),
    confirm&&h(ConfirmSheet,{msg:'Se eliminará la tienda del catálogo.',onOk:async()=>{await api.del(`/maestros/distribucion/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Tienda eliminada'});},onCancel:()=>setConfirm(null)})
  );
}
