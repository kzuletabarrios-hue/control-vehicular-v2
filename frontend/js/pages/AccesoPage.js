// ── ACCESO PAGE (control de acceso vehicular/peatonal) ──
// Extraído de frontend/index.html (líneas 1963-2278, función AccesoPage
// del <script> monolítico, entre el comentario final de ItemAccesoPage y
// el comentario "/* ── VISITANTES PAGE ── */"). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado -- este
// módulo es una copia autocontenida, lista para que la Fase 6 lo importe
// cuando quede conectado vía <script type="module">.
//
// Es probablemente la página más usada del sistema (guardas peatonal/
// vehicular). Incluye el flujo de anulación de registros: `puedeAnularAcceso`
// (core/utils.js) controla solo la UX (mostrar/ocultar el botón "Anular"),
// el backend re-valida siempre con 403 -- ver el comentario de esa función
// en core/utils.js para el detalle completo.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// today/ahoraHora/fmtDate/fmtDateHora/_tsBog/capitalizarNombre/
// textoErrorAnulacion/puedeAnularAcceso (core/utils.js) y los componentes
// compartidos Alert, LoadingDots, CameraField, ConfirmSheet (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { today, ahoraHora, fmtDate, fmtDateHora, _tsBog, capitalizarNombre, textoErrorAnulacion, puedeAnularAcceso } from '../core/utils.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { CameraField } from '../shared/CameraField.js';
import { ConfirmSheet } from '../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback, useRef } = React;
const h = React.createElement;

export function AccesoPage({user,online,addOffline}){
  const [tab,setTab] = useState('personas');
  const [view,setView]       = useState('list');
  const [records,setRecords] = useState([]);
  const [loading,setLoading] = useState(true);
  const [saving,setSaving]   = useState(false);
  const [alert,setAlert]     = useState(null);
  const [confirm,setConfirm] = useState(null);
  const [selected,setSelected]= useState(null);
  const [salida,setSalida]         = useState(null);
  const [horaSalida,setHoraSalida] = useState('');
  const [fechaSalidaA,setFechaSalidaA] = useState('');
  const [obsSalida,setObsSalida]   = useState('');
  const [fotoSalida,setFotoSalida] = useState(null);
  const [sugerencias,setSugerencias] = useState([]);
  const [contratistas,setContratistas] = useState([]);
  const emptyF = {fecha:today(),cedula:'',nombre:'',contratista:'',hora_ingreso:ahoraHora(),hora_salida:'',observaciones:''};
  const [form,setForm] = useState(emptyF);
  const [filtro,setFiltro] = useState('pendientes');
  const [busqueda,setBusqueda] = useState('');
  const esCoordinador = user?.rol==='coordinador';

  // ── Anulación ──
  const [anular,setAnular]           = useState(null);   // registro activo en el modal de anulación
  const [motivoAnular,setMotivoAnular]= useState('');
  const [anulando,setAnulando]       = useState(false);
  const [errorAnular,setErrorAnular] = useState(null);
  const anulandoRef = useRef(false);  // guarda dura contra doble-click (independiente del re-render de setAnulando)
  const [anuladosRecords,setAnuladosRecords] = useState([]);
  const [loadingAnulados,setLoadingAnulados]  = useState(false);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/control-acceso').then(r=>setRecords(r.items||r)).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>{
    load();
    api.get('/maestros/control-acceso').then(rows=>{
      const uniq=[...new Set(rows.filter(r=>r.contratista).map(r=>r.contratista.trim()))].sort();
      setContratistas(uniq);
    }).catch(()=>{});
  },[]);

  // GET /control-acceso ya no trae anulados por defecto: para el historial
  // hay que pedirlos aparte con incluir_anulados=true. Se carga solo cuando
  // el guarda entra a la pestaña "Anulados" (lazy), no en cada visita a la página.
  const cargarAnulados = useCallback(()=>{
    setLoadingAnulados(true);
    api.get('/control-acceso?incluir_anulados=true')
      .then(r=>setAnuladosRecords((r.items||r).filter(x=>x.anulado)))
      .catch(()=>setAlert({type:'err',msg:'Error cargando el historial de anulados'}))
      .finally(()=>setLoadingAnulados(false));
  },[]);
  useEffect(()=>{ if(filtro==='anulados') cargarAnulados(); },[filtro]);

  const cerrarModalAnular = ()=>{ if(anulando) return; setAnular(null); setMotivoAnular(''); setErrorAnular(null); };

  const confirmarAnular = async ()=>{
    const motivo = motivoAnular.trim();
    if(!motivo || anulandoRef.current) return;
    anulandoRef.current = true;
    setAnulando(true); setErrorAnular(null);
    try{
      await api.put(`/control-acceso/${anular.id}/anular`,{motivo});
      setAnular(null); setMotivoAnular('');
      load();
      if(filtro==='anulados') cargarAnulados();
      setAlert({type:'ok',msg:'Registro anulado correctamente'});
    }catch(e){
      setErrorAnular(textoErrorAnulacion(e));
    }finally{
      anulandoRef.current = false;
      setAnulando(false);
    }
  };

  const buscarCedula = async(val)=>{
    const prev = form.cedula||'';
    setForm(p=>({...p,cedula:val}));
    if(val.length<3){setSugerencias([]);return;}
    try{
      const res = await api.get(`/control-acceso/bd/buscar?q=${val}`);
      setSugerencias(res);
      if(res.length===1 && val.length>=prev.length){setForm(p=>({...p,cedula:String(res[0].cedula),nombre:res[0].nombre,contratista:res[0].contratista||''}));setSugerencias([]);}
    }catch(e){}
  };

  const handleSave = async()=>{
    if(!form.nombre) return setAlert({type:'err',msg:'El nombre es obligatorio'});
    if(!form.contratista) return setAlert({type:'err',msg:'Selecciona un contratista'});
    setSaving(true);
    const body = Object.fromEntries(Object.entries(form).filter(([,v])=>v!=null&&v!==''));
    if(body.cedula) body.cedula = parseInt(body.cedula);
    if(!selected){const ts=await _tsBog();body.fecha=ts.fecha;body.hora_ingreso=ts.hora;}
    try{
      if(selected) await api.put(`/control-acceso/${selected.id}`,body);
      else await api.post('/control-acceso',body);
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
        h('div',{className:'header-brand'},h('h1',null,esCoordinador?'Ver registro':(selected?'Editar':'Nuevo registro')),h('span',null,'Control Acceso'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      esCoordinador&&h('p',{style:{fontSize:12,color:'var(--slate)',margin:'0 0 8px'}},'Solo lectura'),
      h('div',{style:{pointerEvents:esCoordinador?'none':undefined}},
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'userCheck',s:12}),' Identificación'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha'),h('input',{type:'date',value:form.fecha,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg',style:{position:'relative'}},
            h('label',null,'Cédula'),
            h('input',{type:'number',value:form.cedula,onChange:e=>buscarCedula(e.target.value),onBlur:()=>setTimeout(()=>setSugerencias([]),150),placeholder:'Número de cédula'}),
            sugerencias.length>0&&h('div',{style:{position:'absolute',top:'100%',left:0,right:0,background:'#fff',border:'1px solid var(--border)',borderRadius:8,zIndex:50,boxShadow:'var(--shadow)',maxHeight:180,overflowY:'auto'}},
              sugerencias.map(s=>h('div',{key:s.cedula,onClick:()=>{setForm(p=>({...p,cedula:String(s.cedula),nombre:s.nombre,contratista:s.contratista||''}));setSugerencias([]);},
                style:{padding:'10px 12px',cursor:'pointer',borderBottom:'1px solid var(--border)',fontSize:13}},
                h('strong',null,s.nombre),' · ',s.contratista||'',h('span',{style:{fontSize:11,color:'var(--slate)',marginLeft:8}},s.cedula)
              ))
            )
          )
        ),
        h('div',{className:'fg'},h('label',null,'Nombre',h('span',{className:'req'},'*')),h('input',{type:'text',value:form.nombre,onChange:e=>setForm(p=>({...p,nombre:e.target.value})),onBlur:()=>setForm(p=>({...p,nombre:capitalizarNombre(p.nombre)})),placeholder:'Nombre completo'})),
        h('div',{className:'fg'},
          h('label',null,'Contratista',h('span',{className:'req'},'*')),
          h('select',{value:form.contratista,onChange:e=>setForm(p=>({...p,contratista:e.target.value}))},
            h('option',{value:''},'Seleccionar contratista...'),
            contratistas.map(c=>h('option',{key:c,value:c},c))
          )
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'clock',s:12}),' Horarios'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Hora ingreso'),h('input',{type:'time',value:form.hora_ingreso,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Hora salida'),h('input',{type:'time',value:form.hora_salida||'',readOnly:true,placeholder:'Usa el botón "Salida"',style:{background:'#f8fafc',cursor:'default'}}))
        ),
        h('div',{className:'fg'},h('label',null,'Observaciones'),h('textarea',{value:form.observaciones,onChange:e=>setForm(p=>({...p,observaciones:e.target.value})),rows:3,placeholder:'—'}))
      )
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);}},h(Ico,{n:'x',s:15})),
      !esCoordinador&&h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar registro'
      )
    )
  );

  const hoyStr = today();
  const nPend = records.filter(r=>!r.hora_salida).length;
  const nDiasAnteriores = records.filter(r=>!r.hora_salida && r.fecha!==hoyStr).length;
  const diasAbiertos = f => Math.round((new Date(hoyStr+'T00:00:00') - new Date(f+'T00:00:00'))/86400000);
  const esVistaAnulados = filtro==='anulados';
  const visibles = (esVistaAnulados ? anuladosRecords : records)
    .filter(r=>{
      if(esVistaAnulados) return true;
      if(filtro==='dias_anteriores') return !r.hora_salida && r.fecha!==hoyStr;
      if(filtro==='pendientes') return !r.hora_salida;
      return true;
    })
    .filter(r=>{if(!busqueda.trim())return true;const q=busqueda.trim().toLowerCase();return (r.nombre&&r.nombre.toLowerCase().includes(q))||(r.cedula&&String(r.cedula).includes(q));});
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('div',{style:{display:'flex',gap:8,padding:'8px 14px 6px',flexWrap:'wrap'}},
        h('div',{style:{display:'flex',gap:6,alignItems:'center',flexWrap:'wrap'}},
          h('button',{onClick:()=>setFiltro('pendientes'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='pendientes'?'var(--navy)':'transparent',color:filtro==='pendientes'?'#fff':'var(--slate)',borderColor:filtro==='pendientes'?'var(--navy)':'var(--border)'}},`Activos (${nPend})`),
          nDiasAnteriores>0&&h('button',{onClick:()=>setFiltro('dias_anteriores'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='dias_anteriores'?'#b91c1c':'#fee2e2',color:filtro==='dias_anteriores'?'#fff':'#991b1b',borderColor:filtro==='dias_anteriores'?'#b91c1c':'#fecaca'}},`⚠ Días anteriores (${nDiasAnteriores})`),
          h('button',{onClick:()=>setFiltro('todos'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='todos'?'var(--navy)':'transparent',color:filtro==='todos'?'#fff':'var(--slate)',borderColor:filtro==='todos'?'var(--navy)':'var(--border)'}},`Todos (${records.length})`),
          h('button',{onClick:()=>setFiltro('anulados'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='anulados'?'var(--slate)':'transparent',color:filtro==='anulados'?'#fff':'var(--slate)',borderColor:filtro==='anulados'?'var(--slate)':'var(--border)',display:'flex',alignItems:'center',gap:4}},h(Ico,{n:'ban',s:11}),'Anulados')
        ),
        !esCoordinador&&h('button',{onClick:()=>setView('form'),style:{marginLeft:'auto',background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
          h(Ico,{n:'plus',s:15}),' Nuevo'
        ),
        esCoordinador&&h('p',{style:{fontSize:12,color:'var(--slate)',marginLeft:'auto',alignSelf:'center'}},'Solo lectura')
      ),
      h('div',{style:{padding:'0 14px 8px',position:'relative'}},
        h(Ico,{n:'search',s:14,style:{position:'absolute',left:24,top:'50%',transform:'translateY(-50%)',color:'var(--slate)',pointerEvents:'none'}}),
        h('input',{type:'text',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar nombre o cédula para salida rápida...',style:{width:'100%',paddingLeft:30,fontSize:12,boxSizing:'border-box'}})
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      (esVistaAnulados?loadingAnulados:loading)?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:esVistaAnulados?'ban':'userCheck',s:44}),h('p',null,busqueda.trim()?'Sin resultados para "'+busqueda.trim()+'"':esVistaAnulados?'Sin registros anulados':filtro==='dias_anteriores'?'Sin pendientes de días anteriores':filtro==='pendientes'?'Sin personas activas':'Sin registros hoy')):
      visibles.map(r=> esVistaAnulados ? h('div',{key:r.id,className:'list-item',style:{cursor:'default',opacity:.85}},
        h('div',{className:'li-icon',style:{background:'#f1f5f9'}},
          h(Ico,{n:'ban',s:18,style:{color:'var(--slate)'}})
        ),
        h('div',{className:'li-body'},
          h('span',{className:'pill pill-slate',style:{marginBottom:3,display:'inline-block'}},'Anulado'),
          h('div',{className:'li-title',style:{textDecoration:'line-through',color:'var(--slate)'}},r.nombre),
          h('div',{className:'li-sub'},r.contratista||'Sin empresa'),
          h('div',{className:'li-sub',style:{color:'#991b1b'}},'Motivo: ',r.anulado_motivo||'—')
        ),
        h('div',{className:'li-right'},
          h('span',{className:'li-date'},r.cedula||'—'),
          h('span',{style:{fontSize:9,color:'var(--slate)',marginTop:2}},fmtDateHora(r.anulado_at))
        )
      ) : h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background: r.hora_salida?'#dcfce7':'#dbeafe'}},
          h(Ico,{n:'userCheck',s:18,style:{color: r.hora_salida?'#16a34a':'#1d4ed8'}})
        ),
        h('div',{className:'li-body',onClick:()=>{setForm({...emptyF,...r,cedula:r.cedula?String(r.cedula):'',hora_ingreso:r.hora_ingreso||'',hora_salida:r.hora_salida||''});setSelected(r);setView('form');}},
          !r.hora_salida&&r.fecha!==hoyStr&&h('span',{className:'pill',style:{background:diasAbiertos(r.fecha)>=5?'#fee2e2':'#fef3c7',color:diasAbiertos(r.fecha)>=5?'#991b1b':'#92400e',marginBottom:3,display:'inline-block'}},diasAbiertos(r.fecha)+(diasAbiertos(r.fecha)===1?' día':' días')+' · '+fmtDate(r.fecha)),
          h('div',{className:'li-title'},r.nombre),
          h('div',{className:'li-sub'},r.contratista||'Sin empresa'),
          r.hora_ingreso&&h('div',{className:'li-sub'},'Ingreso: ',r.hora_ingreso,r.hora_salida&&(' · Salida: '+r.hora_salida))
        ),
        h('div',{className:'li-right'},
          h('span',{className:'li-date'},r.cedula||'—',
            r.fecha_salida&&r.fecha_salida!==r.fecha&&h('span',{style:{display:'block',fontSize:9,color:'#059669',fontWeight:600}},'Sale: '+fmtDate(r.fecha_salida))
          ),
          !esCoordinador&&h('div',{style:{display:'flex',gap:6,marginTop:3,alignItems:'center'}},
            r.hora_ingreso&&!r.hora_salida&&h('button',{
              title:'Registrar salida',
              onClick:(e)=>{e.stopPropagation();setSalida(r);setHoraSalida(ahoraHora());setFechaSalidaA(today());},
              style:{background:'#16a34a',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
            },'Salida'),
            !r.anulado&&puedeAnularAcceso(user)&&h('button',{
              title:'Anular registro',
              onClick:(e)=>{e.stopPropagation();setAnular(r);setMotivoAnular('');setErrorAnular(null);},
              style:{background:'none',border:'1.5px solid #fecaca',cursor:'pointer',color:'#b91c1c',padding:'3px 7px',borderRadius:6,fontSize:11,fontWeight:700,display:'flex',alignItems:'center',gap:3}
            },h(Ico,{n:'ban',s:11}),'Anular'),
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
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:12}},salida.nombre,' · ',salida.contratista||''),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Fecha de salida'),
            h('input',{type:'date',value:fechaSalidaA,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
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
          h('button',{className:'btn-primary',style:{background:'#16a34a'},disabled:saving,onClick:async()=>{
            setSaving(true);
            try{
              const ts=await _tsBog();const upd={hora_salida:ts.hora,fecha_salida:ts.fecha};
              if(obsSalida) upd.observaciones=obsSalida;
              if(fotoSalida) upd.foto_url=fotoSalida;
              await api.put(`/control-acceso/${salida.id}`,upd);
              setSalida(null);setObsSalida('');setFotoSalida(null);load();setAlert({type:'ok',msg:'Salida registrada'});
            }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
            finally{setSaving(false);}
          }},saving?h('div',{className:'spinner'}):h(Ico,{n:'checkCircle',s:16}),saving?'Guardando...':'Confirmar salida')
        )
      )
    ),
    anular&&h('div',{className:'overlay',onClick:cerrarModalAnular},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-handle'}),
        h('div',{style:{padding:'0 0 4px',textAlign:'center'}},
          h('div',{className:'confirm-icon'},h(Ico,{n:'ban',s:22})),
          h('h3',{style:{fontSize:16,fontWeight:700,marginBottom:6}},'Anular registro'),
          h('p',{style:{fontSize:12,color:'var(--slate)',marginBottom:14,lineHeight:1.5}},anular.nombre,' · ',anular.contratista||'Sin empresa',' · Ingreso ',fmtDate(anular.fecha),' ',anular.hora_ingreso||'')
        ),
        h('div',{style:{background:'#fef3c7',border:'1px solid #fcd34d',borderRadius:10,padding:'10px 12px',display:'flex',gap:8,marginBottom:14,alignItems:'flex-start',textAlign:'left'}},
          h(Ico,{n:'alert',s:15,style:{color:'#92400e',flexShrink:0,marginTop:1}}),
          h('p',{style:{fontSize:11.5,color:'#78350f',lineHeight:1.5}},
            'Esta acción queda asociada a tu usuario y ',h('strong',null,'no se puede deshacer'),'. El registro no se elimina: pasa al historial marcado como anulado.'
          )
        ),
        h('div',{className:'fg',style:{textAlign:'left'}},
          h('label',null,'Motivo de la anulación',h('span',{className:'req'},'*')),
          h('textarea',{
            value:motivoAnular,
            onChange:e=>{setMotivoAnular(e.target.value); if(errorAnular) setErrorAnular(null);},
            rows:3,
            placeholder:'Ej: se registró por error, el ingreso corresponde a otra persona...',
            autoFocus:true,
            disabled:anulando
          })
        ),
        errorAnular&&h(Alert,{type:'err',msg:errorAnular,onClose:()=>setErrorAnular(null)}),
        h('div',{style:{display:'flex',gap:8,marginTop:4}},
          h('button',{className:'btn-cancel',style:{flex:1},disabled:anulando,onClick:cerrarModalAnular},'Cancelar'),
          h('button',{className:'btn-primary',style:{background:(anulando||!motivoAnular.trim())?'#94a3b8':'var(--red)'},disabled:anulando||!motivoAnular.trim(),onClick:confirmarAnular},
            anulando?h('div',{className:'spinner'}):h(Ico,{n:'ban',s:16}),anulando?'Anulando...':'Confirmar anulación'
          )
        )
      )
    ),
    confirm&&h(ConfirmSheet,{msg:'Se eliminará el registro.',onOk:async()=>{await api.del(`/control-acceso/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Eliminado'});},onCancel:()=>setConfirm(null)})
  );
}
