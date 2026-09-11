// ── SUSTANCIAS / HERRAMIENTAS SUB-PAGE ──
// Extraído de frontend/index.html (líneas 1805-1960, función
// ItemAccesoPage del <script> monolítico, entre el comentario
// "SUSTANCIAS / HERRAMIENTAS SUB-PAGE" y el comentario "ACCESO PAGE").
// Contenido idéntico al original: el código viejo en index.html NO fue
// tocado ni borrado -- este módulo es una copia autocontenida, lista para
// que la Fase 6 lo importe cuando quede conectado vía <script
// type="module">.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// today/ahoraHora/fmtDate/_tsBog/capitalizarNombre (core/utils.js) y los
// componentes compartidos Alert, LoadingDots, CameraField, ConfirmSheet
// (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { today, ahoraHora, fmtDate, _tsBog, capitalizarNombre } from '../core/utils.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { CameraField } from '../shared/CameraField.js';
import { ConfirmSheet } from '../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function ItemAccesoPage({tipo,user}){
  const cfg = tipo==='sustancias'
    ? {endpoint:'/control-acceso/sustancias',titulo:'Sustancias',icono:'alert',color:'#e11d48',bg:'#fee2e2'}
    : {endpoint:'/control-acceso/herramientas',titulo:'Herramientas',icono:'key',color:'#d97706',bg:'#fef3c7'};

  const [view,setView]       = useState('list');
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const [selected,setSelected]= useState(null);
  const [salidaItem,setSalidaItem]       = useState(null);
  const [horaSalidaItem,setHoraSalidaItem] = useState('');
  const [fechaSalidaItem,setFechaSalidaItem] = useState('');
  const emptyF = {fecha:today(),descripcion:'',cantidad:'',responsable:'',observaciones:'',foto_url:null,es_consumible:false};
  const [form,setForm]       = useState(emptyF);
  const [filtro,setFiltro]   = useState('pendientes');
  const [busqueda,setBusqueda] = useState('');

  const load = useCallback(()=>{
    setLoading(true);
    api.get(cfg.endpoint).then(setRecords).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[cfg.endpoint]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    if(!form.descripcion.trim()) return setAlert({type:'err',msg:'La descripción es obligatoria'});
    setSaving(true);
    try{
      if(selected) await api.put(`${cfg.endpoint}/${selected.id}`,form);
      else await api.post(cfg.endpoint,form);
      setAlert({type:'ok',msg:'Registro guardado'});
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:cfg.icono,s:12}),' Datos del registro'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha'),h('input',{type:'date',value:form.fecha,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Cantidad'),h('input',{type:'text',value:form.cantidad,onChange:e=>setForm(p=>({...p,cantidad:e.target.value})),placeholder:'Ej: 2 unidades'}))
        ),
        h('div',{className:'fg'},
          h('label',null,'Descripción',h('span',{className:'req'},'*')),
          h('input',{type:'text',value:form.descripcion,onChange:e=>setForm(p=>({...p,descripcion:e.target.value})),placeholder:tipo==='sustancias'?'Ej: Thinner, pintura...':'Ej: Taladro, llave inglesa...'})
        ),
        h('div',{className:'fg'},h('label',null,'Responsable / Persona asociada'),h('input',{type:'text',value:form.responsable,onChange:e=>setForm(p=>({...p,responsable:e.target.value})),onBlur:()=>setForm(p=>({...p,responsable:capitalizarNombre(p.responsable)})),placeholder:'Nombre'})),
        h('div',{className:'fg'},h('label',null,'¿Es consumible?'),
          h('select',{value:form.es_consumible?'si':'no',onChange:e=>setForm(p=>({...p,es_consumible:e.target.value==='si'}))},
            h('option',{value:'no'},'No — debe salir'),h('option',{value:'si'},'Sí — se queda/se gasta')
          )
        ),
        h('div',{className:'fg'},h('label',null,'Observaciones'),h('textarea',{value:form.observaciones,onChange:e=>setForm(p=>({...p,observaciones:e.target.value})),rows:3,placeholder:'—'}))
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'camera',s:12}),' Foto (opcional)'),
        h(CameraField,{value:form.foto_url,onChange:v=>setForm(p=>({...p,foto_url:v}))})
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar'
      )
    )
  );

  const nPend = records.filter(r=>!r.hora_salida&&!r.es_consumible).length;
  const visibles = records
    .filter(r=>filtro==='pendientes'?(!r.hora_salida&&!r.es_consumible):true)
    .filter(r=>{if(!busqueda.trim())return true;const q=busqueda.trim().toLowerCase();return (r.descripcion&&r.descripcion.toLowerCase().includes(q))||(r.responsable&&r.responsable.toLowerCase().includes(q));});
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('div',{style:{display:'flex',gap:8,padding:'8px 14px 6px',flexWrap:'wrap'}},
        h('button',{onClick:()=>api.exportar(tipo),style:{background:'none',border:'1.5px solid var(--slate)',color:'var(--slate)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
          h(Ico,{n:'download',s:14}),' Excel'
        ),
        h('div',{style:{marginLeft:'auto',display:'flex',gap:6,alignItems:'center',flexShrink:0}},
          h('button',{onClick:()=>setFiltro('pendientes'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='pendientes'?'var(--navy)':'transparent',color:filtro==='pendientes'?'#fff':'var(--slate)',borderColor:filtro==='pendientes'?'var(--navy)':'var(--border)'}},`Activos (${nPend})`),
          h('button',{onClick:()=>setFiltro('todos'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='todos'?'var(--navy)':'transparent',color:filtro==='todos'?'#fff':'var(--slate)',borderColor:filtro==='todos'?'var(--navy)':'var(--border)'}},`Todos (${records.length})`)
        ),
        h('button',{onClick:()=>setView('form'),style:{background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
          h(Ico,{n:'plus',s:15}),' Nuevo'
        )
      ),
      h('div',{style:{padding:'0 14px 8px',position:'relative'}},
        h(Ico,{n:'search',s:14,style:{position:'absolute',left:24,top:'50%',transform:'translateY(-50%)',color:'var(--slate)',pointerEvents:'none'}}),
        h('input',{type:'text',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar descripción o responsable...',style:{width:'100%',paddingLeft:30,fontSize:12,boxSizing:'border-box'}})
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:cfg.icono,s:44}),h('p',null,busqueda.trim()?'Sin resultados para "'+busqueda.trim()+'"':'Sin registros')):
      visibles.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:r.hora_salida?'#dcfce7':cfg.bg}},h(Ico,{n:cfg.icono,s:18,style:{color:r.hora_salida?'#16a34a':cfg.color}})),
        h('div',{className:'li-body',onClick:()=>{setForm({...emptyF,...r});setSelected(r);setView('form');}},
          r.es_consumible&&h('span',{className:'pill pill-slate',style:{marginBottom:3,display:'inline-block'}},'Consumible'),
          h('div',{className:'li-title'},r.descripcion),
          h('div',{className:'li-sub'},r.cantidad?`Cantidad: ${r.cantidad}`:''),
          r.responsable&&h('div',{className:'li-sub'},'Responsable: ',r.responsable),
          r.hora_salida&&h('div',{className:'li-sub'},'Salida: ',r.hora_salida)
        ),
        h('div',{className:'li-right'},
          h('span',{className:'li-date'},fmtDate(r.fecha),
            r.fecha_salida&&r.fecha_salida!==r.fecha&&h('span',{style:{display:'block',fontSize:9,color:'#059669',fontWeight:600}},'Sale: '+fmtDate(r.fecha_salida))
          ),
          h('div',{style:{display:'flex',gap:6,marginTop:3,alignItems:'center'}},
            !r.hora_salida&&!r.es_consumible&&h('button',{
              title:'Registrar salida',
              onClick:(e)=>{e.stopPropagation();setSalidaItem(r);setHoraSalidaItem(ahoraHora());setFechaSalidaItem(today());},
              style:{background:cfg.color,border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
            },'Salida'),
            !user?.rol?.startsWith('guarda_')&&h('button',{title:'Eliminar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger',style:{marginTop:4}},h(Ico,{n:'trash',s:14}))
          )
        )
      ))
    ),
    salidaItem&&h('div',{className:'overlay',onClick:()=>setSalidaItem(null)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'Registrar salida'),
          h('button',{className:'btn-icon',onClick:()=>setSalidaItem(null)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:12}},salidaItem.descripcion,' · ',salidaItem.responsable||''),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Fecha de salida'),
            h('input',{type:'date',value:fechaSalidaItem,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          ),
          h('div',{className:'fg'},
            h('label',null,'Hora de salida'),
            h('input',{type:'time',value:horaSalidaItem,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          )
        ),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          h('button',{className:'btn-cancel',onClick:()=>setSalidaItem(null),disabled:saving},'Cancelar'),
          h('button',{className:'btn-primary',style:{background:cfg.color},disabled:saving,onClick:async()=>{
            setSaving(true);
            try{
              const ts=await _tsBog();await api.put(`${cfg.endpoint}/${salidaItem.id}`,{hora_salida:ts.hora,fecha_salida:ts.fecha});
              setSalidaItem(null);load();setAlert({type:'ok',msg:'Salida registrada'});
            }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
            finally{setSaving(false);}
          }},saving?h('div',{className:'spinner'}):h(Ico,{n:'check',s:16}),saving?'Guardando...':'Confirmar salida')
        )
      )
    ),
    confirm&&h(ConfirmSheet,{msg:`Se eliminará el registro de ${cfg.titulo.toLowerCase()}.`,onOk:async()=>{await api.del(`${cfg.endpoint}/${confirm}`);setConfirm(null);load();},onCancel:()=>setConfirm(null)})
  );
}
