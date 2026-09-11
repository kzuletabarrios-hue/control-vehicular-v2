// ── FLOTA PAGE ──
// Extraído de frontend/index.html (líneas 1045-1593, función FlotaPage del
// <script> monolítico, entre TiendaPicker y el comentario "CARGA MASIVA").
// Contenido idéntico al original: el código viejo en index.html NO fue
// tocado ni borrado -- este módulo es una copia autocontenida, lista para
// que la Fase 6 lo importe cuando quede conectado vía <script type="module">.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// useVisibilityPolling (core/hooks.js), today/ahoraHora/fmtDate/_tsBog
// (core/utils.js) y los componentes compartidos CameraField, TiendaPicker,
// Alert, LoadingDots, ConfirmSheet (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { useVisibilityPolling } from '../core/hooks.js';
import { today, ahoraHora, fmtDate, _tsBog } from '../core/utils.js';
import { CameraField } from '../shared/CameraField.js';
import { TiendaPicker } from '../shared/TiendaPicker.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { ConfirmSheet } from '../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function FlotaPage({user,online,addOffline,openId,onOpened}){
  const [view,setView]         = useState('list');
  const [records,setRecords]   = useState([]);
  const [conductores,setCond]  = useState([]);
  const [tiendas,setTiendas]   = useState([]);
  const [loading,setLoading]   = useState(true);
  const [saving,setSaving]     = useState(false);
  const [alert,setAlert]       = useState(null);
  const [confirm,setConfirm]   = useState(null);
  const [selected,setSelected] = useState(null);
  const [llegada,setLlegada]   = useState(null);
  const [horaLlegada,setHoraLlegada] = useState('');
  const [fechaLlegadaV,setFechaLlegadaV] = useState('');
  const [salida,setSalida2]          = useState(null);
  const [horaSalida2,setHoraSalida2] = useState('');
  const [fechaSalidaV,setFechaSalidaV] = useState('');
  const [selloSalida,setSelloSalida]   = useState('');
  const [tipoSelloSalida,setTipoSelloSalida] = useState('');
  const [obsSalida,setObsSalida]       = useState('');
  const [fotoSalida,setFotoSalida]     = useState(null);
  const [tempSalida,setTempSalida]     = useState('');
  const [selloLleg,setSelloLleg]     = useState('');
  const [obsLleg,setObsLleg]         = useState('');
  const [fotoLleg,setFotoLleg]       = useState(null);
  const [ultimaTiendaLleg,setUltimaTiendaLleg] = useState('');
  const [detalleVeh,setDetalleVeh] = useState(null);
  const [tipoSelloEntrada,setTipoSelloEntrada] = useState('');
  const [selloEntradaDetalle,setSelloEntradaDetalle] = useState('');
  const esBodega    = user?.rol==='guarda_bodega';
  const esVehicular = user?.rol==='guarda_vehicular';
  const esCoordinador = user?.rol==='coordinador';
  const [cedulaBusq,setCedulaBusq]   = useState('');
  const [sugerCond,setSugerCond]     = useState([]);
  const emptyF = {fecha:today(),placa:'',conductor:'',codigo_conductor:'',n_pallets:'',n_contenedores:'',cant_volumen_externo:'',muelle_cargue:'',tienda_1:'',tienda_2:'',tienda_3:'',tienda_4:'',tienda_5:'',ultima_tienda:'',protocolo:'',sello:'',tipo_sello:'',sello_entrada:'',tipo_sello_entrada:'',hora_salida_muelle:ahoraHora(),temperatura:'',hora_salida_cedi:'',hora_llegada:'',observacion:'',foto_url:null};
  const [form,setForm]         = useState(emptyF);
  const [filtro,setFiltro]      = useState('pendientes');
  const [busqueda,setBusqueda]  = useState('');

  const buscarConductor = (val)=>{
    setCedulaBusq(val);
    if(!val||val.length<2){setSugerCond([]);return;}
    const q=val.toLowerCase();
    setSugerCond(conductores.filter(c=>(c.n_cedula&&c.n_cedula.includes(q))||c.conductor.toLowerCase().includes(q)).slice(0,8));
  };
  const seleccionarConductor = (c)=>{
    setForm(p=>({...p,conductor:c.conductor,codigo_conductor:c.codigo||''}));
    setCedulaBusq(c.n_cedula||'');
    setSugerCond([]);
  };
  const limpiarForm = ()=>{setForm(emptyF);setSelected(null);setCedulaBusq('');setSugerCond([]);};

  const load = useCallback(()=>{
    Promise.all([api.get('/flota'),api.get('/conductores?activo=true&limit=200')])
      .then(([r,c])=>{setRecords(r.items||r);setCond(c);})
      .catch(()=>setAlert({type:'err',msg:'Error cargando datos'}))
      .finally(()=>setLoading(false));
    api.get('/maestros/distribucion').then(setTiendas).catch(()=>{});
  },[]);
  // Flota es operativa (guardas la usan "en vivo"): 1 min y se pausa en
  // background para no seguir consultando /flota, /conductores y
  // /maestros/distribucion con la pestaña oculta.
  useVisibilityPolling(load, 60000, [load]);

  // Abre el detalle completo (hora, fecha, tiendas/ruta, sellos) para un
  // registro. Se usa tanto al tocar la lista como al abrirlo desde la
  // búsqueda global -- ahí siempre se muestra este detalle sin importar el
  // rol, porque es la vista que sí trae hora, fecha y ruta juntos.
  const abrirDetalle = (r) => {
    setDetalleVeh(r);setTipoSelloSalida(r.tipo_sello||'');setTipoSelloEntrada(r.tipo_sello_entrada||'');
    setSelloEntradaDetalle(r.sello_entrada||'');setSelloSalida(r.sello||'');setTempSalida(r.temperatura||'');
    setObsSalida(r.obs_salida||'');setObsLleg(r.obs_llegada||'');setUltimaTiendaLleg(r.ultima_tienda||'');
  };

  // Viene de la búsqueda global (lupa): pide el registro puntual por id --
  // no depende de que esté en la página cargada de la lista, que solo trae
  // los más recientes.
  useEffect(()=>{
    if(!openId) return;
    api.get(`/flota/${openId}`)
      .then(r=>abrirDetalle(r))
      .catch(()=>setAlert({type:'err',msg:'No se pudo abrir el registro'}))
      .finally(()=>onOpened&&onOpened());
  },[openId]);

  const fld = (name,label,type='text',req=false,opts=null) => h('div',{className:'fg'},
    h('label',null,label,req&&h('span',{className:'req'},'*')),
    opts
      ? h('select',{name,value:form[name]||'',onChange:e=>setForm(p=>({...p,[name]:e.target.value}))},
          h('option',{value:''},'Seleccionar...'), ...opts.map(o=>h('option',{key:o.id||o.codigo,value:o.id||String(o.codigo)},o.name||o.conductor))
        )
      : h('input',{type,name,value:form[name]||'',onChange:e=>setForm(p=>({...p,[name]:e.target.value})),placeholder:'—'})
  );

  const handleSave = async()=>{
    if(!form.placa) return setAlert({type:'err',msg:'La placa es obligatoria'});
    setSaving(true);
    const body = Object.fromEntries(Object.entries(form).filter(([,v])=>v!=null&&v!==''));
    if(!selected){const ts=await _tsBog();body.fecha=ts.fecha;body.hora_salida_muelle=ts.hora;}
    try{
      if(!online){
        addOffline({endpoint:selected?`/flota/${selected.id}`:'/flota/',method:selected?'PUT':'POST',body});
        setAlert({type:'warn',msg:'Sin conexión — guardado en cola para sincronizar'});
        setTimeout(()=>{setView('list');setForm(emptyF);setSelected(null);},1500);
        return;
      }
      if(selected) await api.put(`/flota/${selected.id}`,body);
      else await api.post('/flota',body);
      setAlert({type:'ok',msg:'Registro guardado exitosamente'});
      setView('list'); setForm(emptyF); setSelected(null); load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  const handleDuplicate = (r)=>{
    const {id,created_at,updated_at,...rest} = r;
    setForm({...emptyF,...rest,fecha:today(),id:undefined});
    setSelected(null); setView('form');
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>{setView('list');setForm(emptyF);setSelected(null);},style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,selected?'Editar':'Nuevo registro'),h('span',null,'Flota Propia'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'truck',s:12}),' Vehículo y conductor'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha',h('span',{className:'req'},'*')),h('input',{type:'date',value:form.fecha,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Placa',h('span',{className:'req'},'*')),h('input',{type:'text',value:form.placa,onChange:e=>setForm(p=>({...p,placa:e.target.value.toUpperCase()})),placeholder:'ABC-123'}))
        ),
        h('div',{className:'fg',style:{position:'relative'}},
          h('label',null,'Cédula conductor'),
          h('input',{type:'text',value:cedulaBusq,onChange:e=>buscarConductor(e.target.value),onBlur:()=>setTimeout(()=>setSugerCond([]),150),placeholder:'Buscar por cédula o nombre...'}),
          sugerCond.length>0&&h('div',{style:{position:'absolute',top:'100%',left:0,right:0,background:'#fff',border:'1px solid var(--border)',borderRadius:8,zIndex:50,boxShadow:'var(--shadow)',maxHeight:180,overflowY:'auto'}},
            sugerCond.map(c=>h('div',{key:c.id,onClick:()=>seleccionarConductor(c),style:{padding:'10px 12px',cursor:'pointer',borderBottom:'1px solid var(--border)',fontSize:13}},
              h('strong',null,c.conductor),h('span',{style:{fontSize:11,color:'var(--slate)',marginLeft:8}},c.n_cedula||'')
            ))
          )
        ),
        form.conductor&&h('div',{style:{padding:'8px 10px',background:'#f0fdf4',border:'1px solid #86efac',borderRadius:8,fontSize:12,color:'#166534',marginTop:4}},
          '✓ ',form.conductor
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'package',s:12}),' Carga y muelle'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'N° Pallets'),h('input',{type:'text',value:form.n_pallets||'',onChange:e=>setForm(p=>({...p,n_pallets:e.target.value}))})),
          h('div',{className:'fg'},h('label',null,'N° Contenedores'),h('input',{type:'text',value:form.n_contenedores||'',onChange:e=>setForm(p=>({...p,n_contenedores:e.target.value}))})),
          h('div',{className:'fg'},h('label',null,'Vol. Externo'),h('input',{type:'text',value:form.cant_volumen_externo||'',onChange:e=>setForm(p=>({...p,cant_volumen_externo:e.target.value}))})),
          h('div',{className:'fg'},h('label',null,'Muelle cargue'),h('input',{type:'number',value:form.muelle_cargue||'',onChange:e=>setForm(p=>({...p,muelle_cargue:e.target.value}))}))
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},'Ruta de distribución'),
        ...['tienda_1','tienda_2','tienda_3','tienda_4','tienda_5','ultima_tienda'].map((f,i)=>
          h(TiendaPicker,{key:f,label:i<5?`Tienda ${i+1}`:'Última tienda',tiendas,value:form[f]||'',onChange:val=>setForm(p=>({...p,[f]:val}))})
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'thermometer',s:12}),' Horarios y temperatura'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Salida muelle'),h('input',{type:'time',value:form.hora_salida_muelle||'',onChange:e=>setForm(p=>({...p,hora_salida_muelle:e.target.value}))})),
          !esBodega&&h('div',{className:'fg'},h('label',null,'Salida CEDI'),h('input',{type:'time',value:form.hora_salida_cedi||'',readOnly:true,placeholder:'Usa el botón "Salida"',style:{background:'#f8fafc',cursor:'default'}})),
          !esBodega&&h('div',{className:'fg'},h('label',null,'Hora llegada'),h('input',{type:'time',value:form.hora_llegada||'',readOnly:true,placeholder:'Usa el botón "Llegada"',style:{background:'#f8fafc',cursor:'default'}})),
          !esBodega&&h('div',{className:'fg'},h('label',null,'Temperatura °C'),h('input',{type:'number',step:'0.1',value:form.temperatura||'',onChange:e=>setForm(p=>({...p,temperatura:e.target.value}))}))
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Protocolo'),h('input',{type:'text',value:form.protocolo||'',onChange:e=>setForm(p=>({...p,protocolo:e.target.value}))})),
          h('div',{className:'fg'},h('label',null,'N° Sello'),h('input',{type:'text',value:form.sello||'',onChange:e=>setForm(p=>({...p,sello:e.target.value}))}))
        ),
        h('div',{className:'fg'},h('label',null,'Observación'),h('textarea',{value:form.observacion||'',onChange:e=>setForm(p=>({...p,observacion:e.target.value})),rows:3}))
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'camera',s:12}),' Fotografía'),
        h(CameraField,{value:form.foto_url,onChange:v=>setForm(p=>({...p,foto_url:v}))})
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');limpiarForm();}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),
        saving?'Guardando...':'Guardar registro'
      )
    )
  );

  const tiendasDeRuta = r => r ? [r.tienda_1,r.tienda_2,r.tienda_3,r.tienda_4,r.tienda_5].filter(Boolean) : [];
  const tiendasRutaLleg = tiendasDeRuta(llegada);
  const tiendasRutaDetalle = tiendasDeRuta(detalleVeh);

  const nPend = records.filter(r=>!r.hora_llegada).length;
  const visibles = records
    .filter(r=>filtro==='pendientes'?!r.hora_llegada:true)
    .filter(r=>{if(!busqueda.trim())return true;const q=busqueda.trim().toLowerCase();return (r.placa&&r.placa.toLowerCase().includes(q))||(r.conductor_nombre&&r.conductor_nombre.toLowerCase().includes(q))||(r.conductor&&r.conductor.toLowerCase().includes(q));});
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('div',{style:{display:'flex',gap:8,padding:'8px 14px 6px',flexWrap:'wrap'}},
        !esVehicular&&!esCoordinador&&h('button',{onClick:()=>api.exportar('flota'),style:{background:'none',border:'1.5px solid var(--slate)',color:'var(--slate)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
          h(Ico,{n:'download',s:14}),' Excel'
        ),
        !esVehicular&&h('div',{style:{marginLeft:'auto',display:'flex',gap:6,alignItems:'center',flexShrink:0}},
          h('button',{onClick:()=>setFiltro('pendientes'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='pendientes'?'var(--navy)':'transparent',color:filtro==='pendientes'?'#fff':'var(--slate)',borderColor:filtro==='pendientes'?'var(--navy)':'var(--border)'}},`Activos (${nPend})`),
          h('button',{onClick:()=>setFiltro('todos'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='todos'?'var(--navy)':'transparent',color:filtro==='todos'?'#fff':'var(--slate)',borderColor:filtro==='todos'?'var(--navy)':'var(--border)'}},`Todos (${records.length})`)
        ),
        !esVehicular&&!esCoordinador&&h('button',{onClick:()=>setView('form'),style:{background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
          h(Ico,{n:'plus',s:15}),esBodega?' Nuevo en bodega':' Nuevo'
        ),
        esVehicular&&h('p',{style:{fontSize:12,color:'var(--slate)',marginLeft:'auto',alignSelf:'center'}},'Registra salida y regreso de vehículos'),
        esCoordinador&&h('p',{style:{fontSize:12,color:'var(--slate)',marginLeft:'auto',alignSelf:'center'}},'Solo lectura')
      ),
      h('div',{style:{padding:'0 14px 8px',position:'relative'}},
        h(Ico,{n:'search',s:14,style:{position:'absolute',left:24,top:'50%',transform:'translateY(-50%)',color:'var(--slate)',pointerEvents:'none'}}),
        h('input',{type:'text',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar placa o conductor...',style:{width:'100%',paddingLeft:30,fontSize:12,boxSizing:'border-box'}})
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:'truck',s:44}),h('p',null,busqueda.trim()?'Sin resultados para "'+busqueda.trim()+'"':filtro==='pendientes'?'Sin vehículos activos':'Sin registros hoy')):
      visibles.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:'#dbeafe'}},h(Ico,{n:'truck',s:18,c:'',style:{color:'#1d4ed8'}})),
        h('div',{className:'li-body',onClick:esCoordinador?undefined:()=>{ if(esVehicular){abrirDetalle(r);}else{setForm({...emptyF,...r});setSelected(r);setView('form');} }},
          h('div',{className:'li-title'},r.placa,
            h('span',{style:{fontSize:10,fontWeight:600,marginLeft:6,padding:'2px 6px',borderRadius:4,
              background:r.hora_llegada?'#d1fae5':r.hora_salida_cedi?'#fef3c7':'#dbeafe',
              color:r.hora_llegada?'#065f46':r.hora_salida_cedi?'#92400e':'#1e40af'
            }},r.hora_llegada?'Regresó':r.hora_salida_cedi?'En ruta':'En bodega')
          ),
          h('div',{className:'li-sub'},r.conductor_nombre||r.conductor||'Sin conductor'),
          r.ultima_tienda_nombre&&h('div',{className:'li-route'},'→ '+r.ultima_tienda_nombre)
        ),
        h('div',{className:'li-right'},
          h('span',{className:'li-date'},fmtDate(r.fecha),
            r.fecha_salida&&r.fecha_salida!==r.fecha&&h('span',{style:{display:'block',fontSize:9,color:'#d97706',fontWeight:600}},'Sale: '+fmtDate(r.fecha_salida)),
            r.fecha_llegada&&r.fecha_llegada!==r.fecha&&h('span',{style:{display:'block',fontSize:9,color:'#059669',fontWeight:600}},'Regr: '+fmtDate(r.fecha_llegada))
          ),
          !esCoordinador&&h('div',{style:{display:'flex',gap:6,marginTop:3,alignItems:'center'}},
            esVehicular&&!r.hora_salida_cedi&&h('button',{
              title:'Ver detalle y registrar salida',
              onClick:(e)=>{e.stopPropagation();abrirDetalle(r);},
              style:{background:'#059669',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
            },'Salida'),
            esVehicular&&r.hora_salida_cedi&&!r.hora_llegada&&h('button',{
              title:'Ver detalle y registrar llegada',
              onClick:(e)=>{e.stopPropagation();abrirDetalle(r);},
              style:{background:'#f59e0b',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
            },'Llegada'),
            !esVehicular&&r.hora_salida_cedi&&!r.hora_llegada&&h('button',{
              title:'Registrar llegada',
              onClick:(e)=>{e.stopPropagation();setLlegada(r);setHoraLlegada(ahoraHora());setFechaLlegadaV(today());setUltimaTiendaLleg(r.ultima_tienda||'');},
              style:{background:'#f59e0b',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
            },'Llegada'),
            !user?.rol?.startsWith('guarda_')&&h('button',{title:'Duplicar',onClick:()=>handleDuplicate(r),className:'li-act li-act-neutral'},h(Ico,{n:'copy',s:14})),
            !user?.rol?.startsWith('guarda_')&&h('button',{title:'Eliminar',onClick:()=>setConfirm(r.id),className:'li-act li-act-danger'},h(Ico,{n:'trash',s:14}))
          )
        )
      ))
    ),
    llegada&&h('div',{className:'overlay',onClick:()=>setLlegada(null)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'Registrar llegada'),
          h('button',{className:'btn-icon',onClick:()=>setLlegada(null)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:12}},llegada.placa,' · ',llegada.conductor||''),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Fecha de llegada'),
            h('input',{type:'date',value:fechaLlegadaV,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          ),
          h('div',{className:'fg'},
            h('label',null,'Hora de llegada'),
            h('input',{type:'time',value:horaLlegada,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'Última tienda visitada (opcional)'),
          h('select',{value:ultimaTiendaLleg,onChange:e=>setUltimaTiendaLleg(e.target.value)},
            h('option',{value:''},'Seleccionar...'),
            tiendasRutaLleg.map(tid=>{
              const t=tiendas.find(x=>x.id===tid);
              return h('option',{key:tid,value:tid},t?(t.codigo?`${t.codigo} - ${t.name}`:t.name):'—');
            })
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'N° Sello de regreso',h('span',{className:'req'},'*')),
          h('input',{type:'text',value:selloLleg,onChange:e=>setSelloLleg(e.target.value),placeholder:'Ej: 123456',style:selloLleg?{background:'#f0fdf4',borderColor:'#86efac'}:{}})
        ),
        h('div',{className:'fg'},
          h('label',null,'Observaciones (opcional)'),
          h('textarea',{value:obsLleg,onChange:e=>setObsLleg(e.target.value),rows:2,placeholder:'—'})
        ),
        h('div',{className:'fg'},
          h('label',null,'Foto (opcional)'),
          h(CameraField,{value:fotoLleg,onChange:setFotoLleg})
        ),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          h('button',{className:'btn-cancel',onClick:()=>{setLlegada(null);setDetalleVeh(null);},disabled:saving},'Cancelar'),
          h('button',{className:'btn-primary',disabled:saving,onClick:async()=>{
            if(!selloLleg.trim()) return setAlert({type:'err',msg:'El número de sello de regreso es obligatorio'});
            setSaving(true);
            try{
              const ts=await _tsBog();const body={hora_llegada:ts.hora,fecha_llegada:ts.fecha,sello_entrada:selloLleg,obs_llegada:obsLleg||undefined,foto_llegada:fotoLleg||undefined};
              if(ultimaTiendaLleg) body.ultima_tienda=ultimaTiendaLleg;
              await api.put(`/flota/${llegada.id}`,body);
              setLlegada(null);setDetalleVeh(null);setSelloLleg('');setObsLleg('');setFotoLleg(null);setUltimaTiendaLleg('');load();setAlert({type:'ok',msg:'Llegada registrada'});
            }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
            finally{setSaving(false);}
          }},saving?h('div',{className:'spinner'}):h(Ico,{n:'checkCircle',s:16}),saving?'Guardando...':'Confirmar llegada')
        )
      )
    ),
    salida&&h('div',{className:'overlay',onClick:()=>setSalida2(null)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'Registrar salida'),
          h('button',{className:'btn-icon',onClick:()=>setSalida2(null)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:12}},salida.placa,' · ',salida.conductor||''),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Fecha de salida'),
            h('input',{type:'date',value:fechaSalidaV,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          ),
          h('div',{className:'fg'},
            h('label',null,'Hora de salida CEDI'),
            h('input',{type:'time',value:horaSalida2,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'N° Sello de salida',h('span',{className:'req'},'*')),
            h('input',{type:'text',value:selloSalida,onChange:e=>setSelloSalida(e.target.value),placeholder:'Ej: 123456'})
          ),
          h('div',{className:'fg'},
            h('label',null,'Temperatura °C'),
            h('input',{type:'number',step:'0.1',value:tempSalida,onChange:e=>setTempSalida(e.target.value),placeholder:'Ej: 4.5'})
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
          h('button',{className:'btn-cancel',onClick:()=>{setSalida2(null);setDetalleVeh(null);},disabled:saving},'Cancelar'),
          h('button',{className:'btn-primary',style:{background:'#059669'},disabled:saving,onClick:async()=>{
            if(!selloSalida.trim()) return setAlert({type:'err',msg:'El número de sello de salida es obligatorio'});
            setSaving(true);
            try{
            const ts=await _tsBog();const body={hora_salida_cedi:ts.hora,fecha_salida:ts.fecha,sello:selloSalida,obs_salida:obsSalida||undefined,foto_salida:fotoSalida||undefined};
            if(tempSalida) body.temperatura=tempSalida;
            await api.put(`/flota/${salida.id}`,body);
            setSalida2(null);setDetalleVeh(null);setSelloSalida('');setObsSalida('');setFotoSalida(null);setTempSalida('');load();setAlert({type:'ok',msg:'Salida registrada'});
            }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
            finally{setSaving(false);}
          }},saving?h('div',{className:'spinner'}):h(Ico,{n:'checkCircle',s:16}),saving?'Guardando...':'Confirmar salida')
        )
      )
    ),
    confirm&&h(ConfirmSheet,{msg:'Se eliminará el registro de flota.',onOk:async()=>{await api.del(`/flota/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Eliminado'});},onCancel:()=>setConfirm(null)}),
    detalleVeh&&h('div',{className:'overlay',onClick:()=>setDetalleVeh(null),style:(salida||llegada)?{pointerEvents:'none'}:{}},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},detalleVeh.placa),
          h('button',{className:'btn-icon',onClick:()=>setDetalleVeh(null)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:4}},detalleVeh.conductor_nombre||detalleVeh.conductor||'Sin conductor'),
        h('span',{style:{fontSize:11,fontWeight:600,padding:'2px 8px',borderRadius:4,
          background:detalleVeh.hora_llegada?'#d1fae5':detalleVeh.hora_salida_cedi?'#fef3c7':'#dbeafe',
          color:detalleVeh.hora_llegada?'#065f46':detalleVeh.hora_salida_cedi?'#92400e':'#1e40af'
        }},detalleVeh.hora_llegada?'Regresó':detalleVeh.hora_salida_cedi?'En ruta':'En bodega'),
        h('div',{style:{marginTop:12,display:'flex',flexWrap:'wrap',gap:'6px 16px',fontSize:12,color:'var(--slate)'}},
          h('div',null,h('strong',{style:{color:'var(--navy)'}},'Fecha: '),fmtDate(detalleVeh.fecha)),
          detalleVeh.hora_salida_muelle&&h('div',null,h('strong',{style:{color:'var(--navy)'}},'Salida muelle: '),detalleVeh.hora_salida_muelle),
          detalleVeh.hora_salida_cedi&&h('div',null,h('strong',{style:{color:'var(--navy)'}},'Salida CEDI: '),detalleVeh.hora_salida_cedi),
          detalleVeh.hora_llegada&&h('div',null,h('strong',{style:{color:'var(--navy)'}},'Llegada: '),detalleVeh.hora_llegada)
        ),
        h('div',{style:{marginTop:14,background:'#f8fafc',borderRadius:10,padding:'12px 14px'}},
          h('p',{style:{fontSize:11,fontWeight:700,color:'var(--navy)',marginBottom:8,textTransform:'uppercase',letterSpacing:'0.05em'}},'Ruta de distribución'),
          (()=>{
            const nombTs = ['tienda_1','tienda_2','tienda_3','tienda_4','tienda_5']
              .map((f,i)=>({label:`Tienda ${i+1}`,id:detalleVeh[f]}))
              .filter(x=>x.id)
              .map(x=>{const t=tiendas.find(t=>t.id===x.id);return {...x,nombre:t?(t.codigo?`${t.codigo} - ${t.name}`:t.name):'—'};});
            const ultima = detalleVeh.ultima_tienda
              ? tiendas.find(t=>t.id===detalleVeh.ultima_tienda)
              : null;
            const ultimaNombre = ultima?(ultima.codigo?`${ultima.codigo} - ${ultima.name}`:ultima.name):null;
            return nombTs.length===0&&!ultimaNombre
              ? h('p',{style:{fontSize:12,color:'var(--slate)'}},'Sin tiendas asignadas')
              : h('div',null,
                  nombTs.map((x,i)=>h('div',{key:i,style:{display:'flex',gap:8,alignItems:'center',padding:'4px 0',borderBottom:'1px solid var(--border)',fontSize:12}},
                    h('span',{style:{color:'var(--slate)',minWidth:60}},'Tienda '+(i+1)),
                    h('span',{style:{fontWeight:600,color:'var(--navy)'}},x.nombre)
                  )),
                  ultimaNombre&&h('div',{style:{display:'flex',gap:8,alignItems:'center',padding:'4px 0',fontSize:12}},
                    h('span',{style:{color:'#059669',minWidth:60}},'Última'),
                    h('span',{style:{fontWeight:700,color:'#059669'}},ultimaNombre)
                  )
                );
          })()
        ),
        h('div',{style:{marginTop:10,background:'#f8fafc',borderRadius:10,padding:'12px 14px'}},
          h('p',{style:{fontSize:11,fontWeight:700,color:'var(--navy)',marginBottom:8,textTransform:'uppercase',letterSpacing:'0.05em'}},'Sellos'),
          h('div',{className:'fgrid2',style:{alignItems:'flex-end'}},
            h('div',{className:'fg',style:{margin:0}},
              h('label',{style:{fontSize:10,color:'var(--slate)',marginBottom:2,display:'block'}},'N° Sello salida'),
              detalleVeh.hora_salida_cedi
                ? h('p',{style:{fontSize:14,fontWeight:700,color:detalleVeh.sello?'var(--navy)':'var(--slate)',margin:0}},detalleVeh.sello||'—')
                : h('input',{
                    type:'text',value:selloSalida,
                    onChange:e=>setSelloSalida(e.target.value),
                    onBlur:async e=>{
                      const val=e.target.value.trim();
                      if(val&&val!==detalleVeh.sello){
                        try{await api.put(`/flota/${detalleVeh.id}`,{sello:val});setDetalleVeh(p=>({...p,sello:val}));}
                        catch(err){setAlert({type:'err',msg:'No se pudo guardar el N° de sello'});}
                      }
                    },
                    placeholder:'Ej: 123456',style:{fontSize:13,fontWeight:600}
                  })
            ),
            h('div',{className:'fg',style:{margin:0}},
              h('label',{style:{fontSize:10,color:'var(--slate)',marginBottom:2,display:'block'}},'Tipo sello salida'),
              detalleVeh.hora_llegada
                ? h('span',{style:{fontSize:12,fontWeight:700,padding:'2px 8px',borderRadius:4,
                    background:detalleVeh.tipo_sello==='Digital'?'#dbeafe':detalleVeh.tipo_sello==='Plástico'?'#fef9c3':'#f1f5f9',
                    color:detalleVeh.tipo_sello==='Digital'?'#1e40af':detalleVeh.tipo_sello==='Plástico'?'#854d0e':'var(--slate)'
                  }},detalleVeh.tipo_sello||'—')
                : h('select',{
                    value:tipoSelloSalida,
                    onChange:async e=>{
                      const val=e.target.value;setTipoSelloSalida(val);
                      if(val){try{await api.put(`/flota/${detalleVeh.id}`,{tipo_sello:val});setDetalleVeh(p=>({...p,tipo_sello:val}));load();}
                      catch(err){setAlert({type:'err',msg:'No se pudo guardar el tipo de sello de salida'});}}
                    },style:{fontSize:13,fontWeight:600}
                  },
                  h('option',{value:''},'— Seleccionar —'),
                  h('option',{value:'Digital'},'Digital'),
                  h('option',{value:'Plástico'},'Plástico')
                )
            )
          ),
          detalleVeh.hora_salida_cedi&&h('div',{style:{marginTop:10,paddingTop:10,borderTop:'1px solid var(--border)'}},
            h('div',{className:'fgrid2',style:{alignItems:'flex-end'}},
              h('div',{className:'fg',style:{margin:0}},
                h('label',{style:{fontSize:10,color:'#059669',marginBottom:2,display:'block'}},'N° Sello entrada'),
                detalleVeh.hora_llegada
                  ? h('p',{style:{fontSize:14,fontWeight:700,color:'#059669',margin:0}},detalleVeh.sello_entrada||'—')
                  : h('input',{
                      type:'text',
                      value:selloEntradaDetalle,
                      onChange:e=>setSelloEntradaDetalle(e.target.value),
                      onBlur:async e=>{
                        const val=e.target.value.trim();
                        if(val&&val!==detalleVeh.sello_entrada){
                          try{await api.put(`/flota/${detalleVeh.id}`,{sello_entrada:val});setDetalleVeh(p=>({...p,sello_entrada:val}));}
                          catch(err){setAlert({type:'err',msg:'No se pudo guardar el sello de entrada'});}
                        }
                      },
                      placeholder:'Ej: 654321',
                      style:{fontSize:13,fontWeight:600}
                    })
              ),
              h('div',{className:'fg',style:{margin:0}},
                h('label',{style:{fontSize:10,color:'#059669',marginBottom:2,display:'block'}},'Tipo sello entrada'),
                detalleVeh.hora_llegada
                  ? h('span',{style:{fontSize:12,fontWeight:700,padding:'2px 8px',borderRadius:4,
                      background:detalleVeh.tipo_sello_entrada==='Digital'?'#d1fae5':detalleVeh.tipo_sello_entrada==='Plástico'?'#fef9c3':'#f1f5f9',
                      color:detalleVeh.tipo_sello_entrada==='Digital'?'#065f46':detalleVeh.tipo_sello_entrada==='Plástico'?'#854d0e':'var(--slate)'
                    }},detalleVeh.tipo_sello_entrada||'—')
                  : h('select',{
                      value:tipoSelloEntrada,
                      onChange:async e=>{
                        const val=e.target.value;setTipoSelloEntrada(val);
                        if(val){try{await api.put(`/flota/${detalleVeh.id}`,{tipo_sello_entrada:val});setDetalleVeh(p=>({...p,tipo_sello_entrada:val}));load();}
                        catch(err){setAlert({type:'err',msg:'No se pudo guardar el tipo de sello de entrada'});}}
                      },style:{fontSize:13,fontWeight:600}
                    },
                    h('option',{value:''},'— Seleccionar —'),
                    h('option',{value:'Digital'},'Digital'),
                    h('option',{value:'Plástico'},'Plástico')
                  )
              )
            )
          )
        ),
        !detalleVeh.hora_salida_cedi&&h('div',{className:'fg',style:{marginTop:10}},
          h('label',null,'Temperatura °C (opcional)'),
          h('input',{type:'number',step:'0.1',value:tempSalida,onChange:e=>setTempSalida(e.target.value),placeholder:'Ej: 4.5'})
        ),
        !detalleVeh.hora_salida_cedi&&h('div',{className:'fg',style:{marginTop:10}},
          h('label',null,'Observaciones (opcional)'),
          h('textarea',{value:obsSalida,onChange:e=>setObsSalida(e.target.value),rows:2,placeholder:'—'})
        ),
        detalleVeh.hora_salida_cedi&&!detalleVeh.hora_llegada&&h('div',{className:'fg',style:{marginTop:10}},
          h('label',null,'Última tienda visitada (opcional)'),
          h('select',{value:ultimaTiendaLleg,onChange:e=>setUltimaTiendaLleg(e.target.value)},
            h('option',{value:''},'Seleccionar...'),
            tiendasRutaDetalle.map(tid=>{
              const t=tiendas.find(x=>x.id===tid);
              return h('option',{key:tid,value:tid},t?(t.codigo?`${t.codigo} - ${t.name}`:t.name):'—');
            })
          )
        ),
        detalleVeh.hora_salida_cedi&&!detalleVeh.hora_llegada&&h('div',{className:'fg',style:{marginTop:10}},
          h('label',null,'Observaciones llegada (opcional)'),
          h('textarea',{value:obsLleg,onChange:e=>setObsLleg(e.target.value),rows:2,placeholder:'—'})
        ),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          !detalleVeh.hora_salida_cedi&&h('button',{className:'btn-primary',style:{background:'#059669',flex:1},onClick:async()=>{
            const sello=(selloSalida||detalleVeh.sello||'').trim();
            if(!sello) return setAlert({type:'err',msg:'Ingresa el N° de sello de salida antes de registrar'});
            try{
              const ts=await _tsBog();
              const body={hora_salida_cedi:ts.hora,fecha_salida:ts.fecha,sello};
              if(tempSalida) body.temperatura=tempSalida;
              if(obsSalida.trim()) body.obs_salida=obsSalida.trim();
              await api.put(`/flota/${detalleVeh.id}`,body);
              setDetalleVeh(null);setSelloSalida('');setTempSalida('');setObsSalida('');load();setAlert({type:'ok',msg:'Salida registrada ✓'});
            }catch(e){setAlert({type:'err',msg:'Error al registrar salida'});}
          }},h(Ico,{n:'truck',s:14}),' Registrar salida'),
          detalleVeh.hora_salida_cedi&&!detalleVeh.hora_llegada&&h('button',{className:'btn-primary',style:{flex:1},onClick:async()=>{
            const sello=(detalleVeh.sello_entrada||selloEntradaDetalle||'').trim();
            if(!sello) return setAlert({type:'err',msg:'Ingresa el N° de sello de entrada antes de registrar llegada'});
            const ts=await _tsBog();
            const body={hora_llegada:ts.hora,fecha_llegada:ts.fecha,sello_entrada:sello};
            if(obsLleg.trim()) body.obs_llegada=obsLleg.trim();
            if(ultimaTiendaLleg) body.ultima_tienda=ultimaTiendaLleg;
            await api.put(`/flota/${detalleVeh.id}`,body);
            setDetalleVeh(null);setSelloEntradaDetalle('');setObsLleg('');setUltimaTiendaLleg('');load();setAlert({type:'ok',msg:'Llegada registrada ✓'});
          }},h(Ico,{n:'checkCircle',s:14}),' Registrar llegada'),
          h('button',{className:'btn-cancel',onClick:()=>setDetalleVeh(null)},'Cerrar')
        )
      )
    )
  );
}
