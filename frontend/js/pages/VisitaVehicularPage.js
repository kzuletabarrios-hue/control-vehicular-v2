// ── VISITA VEHICULAR PAGE ──
// Extraído de frontend/index.html (líneas 2465-2641, función
// VisitaVehicularPage del <script> monolítico, entre el comentario
// "/* ── VISITA VEHICULAR PAGE ── */" y el comentario "/* ── TABLERO DE
// MUELLES PARA CONFIRMAR INGRESO (guarda vehicular) ── */"). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado -- este módulo es una copia autocontenida, lista para que la
// Fase 6 lo importe cuando quede conectado vía <script type="module">.
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

export function VisitaVehicularPage({user,online,addOffline}){
  const [view,setView]       = useState('list');
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const [selected,setSelected]= useState(null);
  const [salida,setSalida]         = useState(null);
  const [horaSalida,setHoraSalida] = useState('');
  const [fechaSalidaVV,setFechaSalidaVV] = useState('');
  const [obsSalida,setObsSalida]   = useState('');
  const [fotoSalida,setFotoSalida] = useState(null);
  const emptyF = {fecha:today(),placa:'',conductor:'',empresa_pertenece:'',motivo_visita:'',dependencia_autoriza:'',hora_ingreso:ahoraHora(),hora_salida:'',observaciones:'',foto_url:null};
  const [form,setForm] = useState(emptyF);
  const [filtro,setFiltro] = useState('pendientes');
  const [busqueda,setBusqueda] = useState('');

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/visita-vehicular').then(r=>setRecords(r.items||r)).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    if(!form.placa||!form.conductor) return setAlert({type:'err',msg:'Placa y conductor son obligatorios'});
    setSaving(true);
    const body = Object.fromEntries(Object.entries(form).filter(([,v])=>v!=null&&v!==''));
    if(!selected){const ts=await _tsBog();body.fecha=ts.fecha;body.hora_ingreso=ts.hora;}
    try{
      if(selected) await api.put(`/visita-vehicular/${selected.id}`,body);
      else await api.post('/visita-vehicular',body);
      setAlert({type:'ok',msg:'Registro guardado'});
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>{setView('list');setForm(emptyF);setSelected(null);},style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,selected?'Editar visita':'Nueva visita vehicular'),h('span',null,'Visita Vehicular'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'truck',s:12}),' Datos del vehículo'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha'),h('input',{type:'date',value:form.fecha,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Placa',h('span',{className:'req'},'*')),h('input',{type:'text',value:form.placa,onChange:e=>setForm(p=>({...p,placa:e.target.value.toUpperCase()})),placeholder:'ABC123'}))
        ),
        h('div',{className:'fg'},h('label',null,'Conductor',h('span',{className:'req'},'*')),h('input',{type:'text',value:form.conductor,onChange:e=>setForm(p=>({...p,conductor:e.target.value})),onBlur:()=>setForm(p=>({...p,conductor:capitalizarNombre(p.conductor)})),placeholder:'Nombre completo'})),
        h('div',{className:'fg'},h('label',null,'Empresa a la que pertenece'),h('input',{type:'text',value:form.empresa_pertenece||'',onChange:e=>setForm(p=>({...p,empresa_pertenece:e.target.value})),placeholder:'Empresa del conductor'})),
        h('div',{className:'fg'},h('label',null,'Motivo de la visita'),h('input',{type:'text',value:form.motivo_visita,onChange:e=>setForm(p=>({...p,motivo_visita:e.target.value})),placeholder:'Ej: visita a empleado, entidad de gobierno...'})),
        h('div',{className:'fg'},h('label',null,'Quién autoriza'),h('input',{type:'text',value:form.dependencia_autoriza||'',onChange:e=>setForm(p=>({...p,dependencia_autoriza:e.target.value})),placeholder:'Nombre o dependencia que autoriza'}))
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'check',s:12}),' Horarios'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Hora ingreso'),h('input',{type:'time',value:form.hora_ingreso,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Hora salida'),h('input',{type:'time',value:form.hora_salida||'',readOnly:true,placeholder:'Usa el botón "Salida"',style:{background:'#f8fafc',cursor:'default'}}))
        ),
        h('div',{className:'fg'},h('label',null,'Observaciones'),h('textarea',{value:form.observaciones,onChange:e=>setForm(p=>({...p,observaciones:e.target.value})),rows:3,placeholder:'—'}))
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'camera',s:12}),' Fotografía'),
        h(CameraField,{value:form.foto_url,onChange:v=>setForm(p=>({...p,foto_url:v}))})
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar registro'
      )
    )
  );

  const nPend = records.filter(r=>!r.hora_salida).length;
  const visibles = records
    .filter(r=>filtro==='pendientes'?!r.hora_salida:true)
    .filter(r=>{if(!busqueda.trim())return true;const q=busqueda.trim().toLowerCase();return (r.placa&&r.placa.toLowerCase().includes(q))||(r.conductor&&r.conductor.toLowerCase().includes(q));});
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('div',{style:{display:'flex',gap:8,padding:'8px 14px 6px',flexWrap:'wrap'}},
        h('button',{onClick:()=>api.exportar('visita-vehicular'),style:{background:'none',border:'1.5px solid var(--slate)',color:'var(--slate)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
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
        h('input',{type:'text',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar placa o conductor para salida rápida...',style:{width:'100%',paddingLeft:30,fontSize:12,boxSizing:'border-box'}})
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:'truck',s:44}),h('p',null,busqueda.trim()?'Sin resultados para "'+busqueda.trim()+'"':filtro==='pendientes'?'Sin visitas activas':'Sin visitas vehiculares hoy')):
      visibles.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#e0f2fe'}},
          h(Ico,{n:'truck',s:18,style:{color:'#0284c7'}})
        ),
        h('div',{className:'li-body',onClick:()=>{setForm({...emptyF,...r,hora_ingreso:r.hora_ingreso||'',hora_salida:r.hora_salida||''});setSelected(r);setView('form');}},
          h('div',{className:'li-title'},r.placa),
          h('div',{className:'li-sub'},r.conductor,r.empresa_pertenece&&(' · '+r.empresa_pertenece)),
          r.dependencia_autoriza&&h('div',{className:'li-sub'},'Autoriza: '+r.dependencia_autoriza),
          r.hora_ingreso&&h('div',{className:'li-sub'},'Ingreso: ',r.hora_ingreso,r.hora_salida&&(' · Salida: '+r.hora_salida))
        ),
        h('div',{className:'li-right'},
          h('span',{className:'li-date'},r.motivo_visita||'—',
            r.fecha_salida&&r.fecha_salida!==r.fecha&&h('span',{style:{display:'block',fontSize:9,color:'#059669',fontWeight:600}},'Sale: '+fmtDate(r.fecha_salida))
          ),
          h('div',{style:{display:'flex',gap:6,marginTop:3,alignItems:'center'}},
            r.hora_ingreso&&!r.hora_salida&&h('button',{
              title:'Registrar salida',
              onClick:(e)=>{e.stopPropagation();setSalida(r);setHoraSalida(ahoraHora());setFechaSalidaVV(today());},
              style:{background:'#0284c7',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
            },'Salida'),
            !user?.rol?.startsWith('guarda_')&&h('button',{title:'Eliminar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger'},h(Ico,{n:'trash',s:14}))
          )
        )
      ))
    ),
    salida&&h('div',{className:'overlay',onClick:()=>setSalida(null)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'Registrar salida'),
          h('button',{className:'btn-icon',onClick:()=>setSalida(null)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:12}},salida.placa,' · ',salida.conductor||''),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Fecha de salida'),
            h('input',{type:'date',value:fechaSalidaVV,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          ),
          h('div',{className:'fg'},
            h('label',null,'Hora de salida'),
            h('input',{type:'time',value:horaSalida,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'Observaciones (opcional)'),
          h('textarea',{value:obsSalida,onChange:e=>setObsSalida(e.target.value),rows:2,placeholder:'—'})
        ),
        h('div',{className:'fg'},
          h('label',null,'Foto (opcional)'),
          h(CameraField,{value:fotoSalida,onChange:setFotoSalida})
        ),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          h('button',{className:'btn-cancel',onClick:()=>setSalida(null),disabled:saving},'Cancelar'),
          h('button',{className:'btn-primary',style:{background:'#0284c7'},disabled:saving,onClick:async()=>{
            setSaving(true);
            try{
              const ts=await _tsBog();const upd={hora_salida:ts.hora,fecha_salida:ts.fecha};
              if(obsSalida) upd.observaciones=obsSalida;
              if(fotoSalida) upd.foto_url=fotoSalida;
              await api.put(`/visita-vehicular/${salida.id}`,upd);
              setSalida(null);setObsSalida('');setFotoSalida(null);load();setAlert({type:'ok',msg:'Salida registrada'});
            }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
            finally{setSaving(false);}
          }},saving?h('div',{className:'spinner'}):h(Ico,{n:'check',s:16}),saving?'Guardando...':'Confirmar salida')
        )
      )
    ),
    confirm&&h(ConfirmSheet,{msg:'Se eliminará el registro de visita vehicular.',onOk:async()=>{await api.del(`/visita-vehicular/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Eliminado'});},onCancel:()=>setConfirm(null)})
  );
}
