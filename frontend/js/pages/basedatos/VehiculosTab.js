// ── BASE DATOS · VEHÍCULOS TAB ──
// Maestro de vehículos de flota propia (tabla `vehiculos`). Permite dar de
// alta un vehículo individual, completar su tipo y desactivarlo, sin tener
// que subir un Excel por Carga Masiva. Las placas del registro de Flota
// Propia se eligen de esta lista; una placa que no esté aquí queda marcada
// como "Placa no verificada". Solo visible para admin (ver index.js).

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

const TIPOS = ['SENCILLO','BITREN','MINIMULA','TURBO','TRACTOMULA'];
const normPlaca = v => String(v||'').replace(/[\s-]+/g,'').toUpperCase();

export function VehiculosTab(){
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const emptyF = {placa:'',tipo:'',marca:''};
  const [form,setForm] = useState(emptyF);
  const [editingId,setEditingId] = useState(null);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/maestros/vehiculos?activo=true').then(setRecords)
      .catch(()=>setAlert({type:'err',msg:'Error cargando vehículos'}))
      .finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const editar = r => { setForm({placa:r.placa,tipo:r.tipo||'',marca:r.marca||''}); setEditingId(r.id); };

  const handlePlaca = val => {
    const p = normPlaca(val);
    setForm(f=>({...f,placa:p}));
    const existente = records.find(r=>r.placa===p);
    if(existente) editar(existente);
    else if(editingId) setEditingId(null);
  };

  const handleSave = async()=>{
    if(!form.placa) return setAlert({type:'err',msg:'La placa es requerida'});
    setSaving(true);
    try{
      const body = {placa:form.placa, tipo:form.tipo||null, marca:form.marca.trim()||null};
      if(editingId) await api.put(`/maestros/vehiculos/${editingId}`,body);
      else await api.post('/maestros/vehiculos',body);
      setAlert({type:'ok',msg:editingId?'Vehículo actualizado':'Vehículo agregado'});
      setForm(emptyF);setEditingId(null);load();
    }catch(e){setAlert({type:'err',msg:e.message||'No se pudo guardar'});}
    finally{setSaving(false);}
  };

  const sinTipo = records.filter(r=>!r.tipo).length;

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'plus',s:12}),editingId?' Editar vehículo':' Nuevo vehículo'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Placa'),
            h('input',{type:'text',value:form.placa,onChange:e=>handlePlaca(e.target.value),placeholder:'ABC123',maxLength:10})
          ),
          h('div',{className:'fg'},
            h('label',null,'Tipo de vehículo'),
            h('select',{value:form.tipo,onChange:e=>setForm(p=>({...p,tipo:e.target.value}))},
              h('option',{value:''},'Por definir'),
              TIPOS.map(t=>h('option',{key:t,value:t},t))
            )
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'Marca (opcional)'),
          h('input',{type:'text',value:form.marca,onChange:e=>setForm(p=>({...p,marca:e.target.value})),placeholder:'Marca',onKeyDown:e=>e.key==='Enter'&&handleSave()})
        ),
        h('div',{style:{display:'flex',gap:8,justifyContent:'flex-end'}},
          editingId&&h('button',{onClick:()=>{setForm(emptyF);setEditingId(null);},style:{background:'none',border:'1px solid var(--border)',borderRadius:8,padding:'11px 16px',cursor:'pointer',fontWeight:700,fontSize:13,fontFamily:'inherit'}},'Cancelar'),
          h('button',{onClick:handleSave,disabled:saving,style:{background:'var(--navy2)',color:'#fff',border:'none',borderRadius:8,padding:'11px 16px',cursor:'pointer',fontWeight:700,fontSize:13,fontFamily:'inherit',display:'flex',alignItems:'center',gap:5,flexShrink:0}},
            saving?h('div',{className:'spinner'}):h(Ico,{n:editingId?'save':'plus',s:15}),editingId?'Guardar':'Agregar'
          )
        )
      ),
      !loading&&sinTipo>0&&h('p',{style:{fontSize:12,color:'#92400e',background:'#fef3c7',borderRadius:8,padding:'8px 12px',margin:'0 0 10px'}},
        `${sinTipo} vehículo(s) sin tipo definido. Tócalos para completarlo.`),
      loading?h(LoadingDots):
      records.length===0?h('div',{className:'empty'},h(Ico,{n:'truck',s:44}),h('p',null,'Sin vehículos registrados')):
      records.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#dbeafe'}},h(Ico,{n:'truck',s:18,style:{color:'#1d4ed8'}})),
        h('div',{className:'li-body',onClick:()=>editar(r)},
          h('div',{className:'li-title'},r.placa),
          h('div',{className:'li-sub',style:r.tipo?null:{color:'#b45309',fontWeight:700}},
            (r.tipo||'Tipo por definir')+(r.marca?` · ${r.marca}`:''))
        ),
        h('button',{title:'Desactivar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger'},h(Ico,{n:'trash',s:14}))
      ))
    ),
    confirm&&h(ConfirmSheet,{msg:'El vehículo se desactivará y ya no aparecerá en la lista de placas de Flota. Sus viajes no se borran.',onOk:async()=>{try{await api.del(`/maestros/vehiculos/${confirm}`);setAlert({type:'ok',msg:'Vehículo desactivado'});}catch(e){setAlert({type:'err',msg:e.message});}setConfirm(null);load();},onCancel:()=>setConfirm(null)})
  );
}
