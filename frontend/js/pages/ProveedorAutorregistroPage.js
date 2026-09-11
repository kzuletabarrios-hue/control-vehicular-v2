// ── AUTORREGISTRO PÚBLICO DE PROVEEDORES (sin login) ──
// Extraído de frontend/index.html (líneas 5652-5955, comentario
// "/* ── AUTORREGISTRO PÚBLICO DE PROVEEDORES (sin login) ── */" del
// <script> monolítico). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado (ver notas de la Fase 2 del plan de
// migración) -- este módulo es una copia autocontenida, lista para que la
// Fase 6 lo importe cuando quede conectado vía <script type="module">.
//
// Es la página de menor riesgo de todo el Lote 1 (señalado por Alejandro):
// ni siquiera requiere login -- se llega por el token del QR de portería.
// Importa api (core/api-client.js), Ico (core/icons.js), capitalizarNombre
// y fechaValida (core/utils.js), y los componentes compartidos Alert,
// LoadingDots y LogisticaInversaField (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { api } from '../core/api-client.js';
import { Ico } from '../core/icons.js';
import { capitalizarNombre, fechaValida } from '../core/utils.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { LogisticaInversaField } from '../shared/LogisticaInversaField.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function ProveedorAutorregistroPage({token}){
  const [estado,setEstado]   = useState('validando'); // validando | valido | invalido | enviado
  const [tokenSesion,setTokenSesion] = useState(null);
  const [errorMsg,setErrorMsg] = useState('');
  const [saving,setSaving]   = useState(false);
  const tiposVehiculo = ['Camión','Camioneta','Moto','Furgón','Tractomula','Otro'];
  const tiposDocumento = ['CC','NIT','Otro'];
  const tiposCarga = ['Seca','Refrigerada','Mixta'];
  const formatosCarga = ['Paletizada','Granel','Mixta'];
  const manejosCarga = ['Conductor con certificado de montacargas','Reciservicios','Ercol','Operador logístico externo'];
  const emptyVeh = {placa_vehiculo:'',nombre_conductor:'',tipo_documento:'CC',cedula_conductor:'',telefono_conductor:'',tipo_vehiculo:'',hora_cita:'',
    fecha_pago_arl:'',epp_cumple:'',tipo_carga:'',formato_carga:'',cantidad_pallets:'',manejo_carga:'',tipos_logistica_inversa:null};
  const emptyOrd = {empresa:'',numero_orden_compra:''};
  const [vehiculo,setVehiculo] = useState(emptyVeh);
  const [ordenes,setOrdenes]   = useState([]);
  const [ordenDraft,setOrdenDraft] = useState(emptyOrd);
  const [frecuente,setFrecuente] = useState(null); // true|false|null (null = aun no se busco)
  // null | {estado:'buscando'} | {estado:'encontrado',proveedor,hora} | {estado:'no_encontrado'} | {estado:'error'}
  const [citaOrdenInfo,setCitaOrdenInfo] = useState(null);

  const buscarFrecuente = async(cedula)=>{
    setFrecuente(null);
    if(!cedula||cedula.trim().length<5||!tokenSesion) return;
    try{
      const r = await api.get(`/proveedores-publico/conductor-frecuente?cedula=${encodeURIComponent(cedula.trim())}&token=${encodeURIComponent(tokenSesion)}`);
      if(r.encontrado){
        setVehiculo(p=>({
          ...p,
          nombre_conductor: p.nombre_conductor||r.nombre_conductor||'',
          telefono_conductor: p.telefono_conductor||r.telefono||'',
          tipo_vehiculo: p.tipo_vehiculo||r.tipo_vehiculo||'',
        }));
        setFrecuente(true);
      } else {
        setFrecuente(false);
      }
    }catch(_){ setFrecuente(false); }
  };

  useEffect(()=>{
    if(!token){ setEstado('invalido'); setErrorMsg('Falta el código del QR. Escanéalo de nuevo desde la portería.'); return; }
    api.get(`/proveedores-publico/token-info?token=${encodeURIComponent(token)}`)
      .then(r=>{ setTokenSesion(r.token_sesion); setEstado('valido'); })
      .catch(e=>{ setEstado('invalido'); let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{} setErrorMsg(msg); });
  },[token]);

  /* El conductor nunca escribe el proveedor ni la hora de cita a mano: en
     cuanto completa los 10 dígitos del número de orden se busca (con
     debounce, para no disparar un request por cada tecla) contra las citas
     programadas de HOY. Si no hay match no hay fallback manual -- a
     diferencia del formulario del guarda, aquí la orden queda bloqueada
     (la autoridad real de todos modos es el servidor en POST /autorregistro,
     esto es solo UX). buscarCita queda aparte (no solo dentro del efecto)
     para que el estado 'error' de red pueda ofrecer un botón "Reintentar"
     sin obligar al conductor a borrar y volver a escribir el número. */
  const buscarCita = useCallback((numero)=>{
    if(!tokenSesion) return;
    setCitaOrdenInfo({estado:'buscando'});
    api.get(`/proveedores-publico/citas/buscar?numero_orden_compra=${encodeURIComponent(numero)}&token=${encodeURIComponent(tokenSesion)}`)
      .then(r=>{
        if(r&&r.encontrado) setCitaOrdenInfo({estado:'encontrado',proveedor:r.proveedor_nombre,hora:r.hora_cita_inicio||null});
        else setCitaOrdenInfo({estado:'no_encontrado'});
      })
      .catch(()=>setCitaOrdenInfo({estado:'error'}));
  },[tokenSesion]);

  useEffect(()=>{
    const numero = ordenDraft.numero_orden_compra;
    if(!/^4\d{9}$/.test(numero)||!tokenSesion){ setCitaOrdenInfo(null); return; }
    setCitaOrdenInfo({estado:'buscando'});
    const t = setTimeout(()=>buscarCita(numero),500);
    return ()=>clearTimeout(t);
  },[ordenDraft.numero_orden_compra,tokenSesion,buscarCita]);

  const agregarOrden = ()=>{
    if(!ordenDraft.numero_orden_compra.trim()){ setErrorMsg('El número de orden de compra es obligatorio'); return; }
    if(!/^4\d{9}$/.test(ordenDraft.numero_orden_compra.trim())){ setErrorMsg('El número de orden debe empezar en 4 y tener 10 dígitos (ej. 4001234567)'); return; }
    if(citaOrdenInfo?.estado!=='encontrado'){
      setErrorMsg('Esta orden no aparece en las citas programadas de hoy. Acércate a la caseta para que el guarda registre tu ingreso.');
      return;
    }
    const horaOrden = citaOrdenInfo.hora || null;
    const esPrimeraOrden = ordenes.length===0;
    const avisoHora = !esPrimeraOrden && horaOrden && vehiculo.hora_cita && horaOrden!==vehiculo.hora_cita;
    setOrdenes(p=>[...p,{
      empresa: citaOrdenInfo.proveedor,
      numero_orden_compra: ordenDraft.numero_orden_compra.trim(),
      _horaCita: horaOrden,
      _avisoHora: avisoHora,
    }]);
    // Hora de cita: campo único del vehículo, la fija la PRIMERA orden con
    // match. Si una orden posterior trae una hora distinta no se pisa -- solo
    // se marca el aviso informativo guardado arriba en _avisoHora.
    if(esPrimeraOrden && horaOrden) setVehiculo(p=>({...p,hora_cita:horaOrden}));
    setOrdenDraft({...emptyOrd});
    setCitaOrdenInfo(null);
    setErrorMsg('');
  };
  const quitarOrden = (i)=>setOrdenes(p=>{
    const n = p.filter((_,idx)=>idx!==i);
    // si se quita la primera orden (la que fijó la hora), la hora del
    // vehículo se re-deriva de la nueva primera orden con hora conocida (o
    // queda vacía si ya no queda ninguna).
    const nuevaPrimeraHora = n.find(o=>o._horaCita)?._horaCita || '';
    setVehiculo(pv=>({...pv,hora_cita:nuevaPrimeraHora}));
    return n;
  });

  const enviar = async()=>{
    setErrorMsg('');
    if(!vehiculo.placa_vehiculo.trim()) return setErrorMsg('La placa es obligatoria');
    if(!/^[A-Z]+[0-9]+$/.test(vehiculo.placa_vehiculo)) return setErrorMsg('La placa debe escribirse solo con letras seguidas de números, sin espacios ni caracteres especiales (ejemplo: ABC123)');
    if(!vehiculo.nombre_conductor.trim()) return setErrorMsg('El nombre del conductor es obligatorio');
    if(!vehiculo.tipo_documento) return setErrorMsg('Selecciona el tipo de documento');
    if(!vehiculo.cedula_conductor.trim()) return setErrorMsg('El número de documento es obligatorio');
    if(!vehiculo.telefono_conductor.trim()) return setErrorMsg('El teléfono del conductor es obligatorio');
    if(!vehiculo.tipo_vehiculo.trim()) return setErrorMsg('Selecciona el tipo de vehículo');
    if(!vehiculo.fecha_pago_arl) return setErrorMsg('La fecha de ARL es obligatoria');
    if(vehiculo.epp_cumple==='') return setErrorMsg('Indica si cuentas con los elementos de protección personal');
    if(!vehiculo.tipo_carga) return setErrorMsg('Selecciona el tipo de carga');
    if(!vehiculo.formato_carga) return setErrorMsg('Selecciona el formato de carga');
    if(!vehiculo.cantidad_pallets.trim()) return setErrorMsg('La cantidad de pallets es obligatoria');
    if(!vehiculo.manejo_carga) return setErrorMsg('Selecciona quién maneja la carga');
    if(!Array.isArray(vehiculo.tipos_logistica_inversa)) return setErrorMsg('Indica si el vehículo trae logística inversa (selecciona una opción o marca "No aplica")');
    if(ordenes.length===0) return setErrorMsg('Agrega al menos un proveedor/orden a la que vienes a entregar');
    setSaving(true);
    try{
      await api.post('/proveedores-publico/autorregistro',{
        token:tokenSesion, vehiculo:{...vehiculo,placa_vehiculo:vehiculo.placa_vehiculo.toUpperCase(),epp_cumple:vehiculo.epp_cumple==='si'}, ordenes,
      });
      setEstado('enviado');
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setErrorMsg(msg);
    }finally{ setSaving(false); }
  };

  const Shell = (...children)=>h('div',{style:{height:'100%',display:'flex',flexDirection:'column',overflow:'hidden',background:'var(--bg,#f8fafc)'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('div',{className:'header-brand'},h('h1',null,'Ingreso de Proveedores'),h('span',null,'CEDI R10'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'16px 14px',maxWidth:480,margin:'0 auto',width:'100%',boxSizing:'border-box'}},...children)
  );

  if(estado==='validando') return Shell(h('div',{style:{textAlign:'center',paddingTop:60}},h(LoadingDots)));

  if(estado==='invalido') return Shell(
    h('div',{style:{textAlign:'center',paddingTop:40}},
      h(Ico,{n:'alert',s:44,style:{color:'#dc2626',marginBottom:12}}),
      h('p',{style:{fontWeight:700,fontSize:15,marginBottom:6}},'No se pudo validar el código'),
      h('p',{style:{color:'var(--slate)',fontSize:13}},errorMsg||'Pide al guarda que te muestre el QR actualizado y escanéalo de nuevo.')
    )
  );

  if(estado==='enviado') return Shell(
    h('div',{style:{textAlign:'center',paddingTop:40}},
      h(Ico,{n:'checkCircle',s:44,style:{color:'#16a34a',marginBottom:12}}),
      h('p',{style:{fontWeight:700,fontSize:15,marginBottom:6}},'Registro enviado'),
      h('p',{style:{color:'var(--slate)',fontSize:13}},'El guarda confirmará tu ingreso en un momento. Puedes cerrar esta página.')
    )
  );

  return Shell(
    errorMsg&&h(Alert,{type:'err',msg:errorMsg,onClose:()=>setErrorMsg('')}),
    h('div',{className:'fcard'},
      h('p',{className:'sec-ttl'},h(Ico,{n:'truck',s:12}),' Datos del vehículo y conductor'),
      // Cédula primero (con tipo de documento): dispara buscarFrecuente()
      // ANTES de que el conductor escriba nombre/teléfono/tipo de vehículo a
      // mano, para que esos campos lleguen ya precargados si es un conductor
      // frecuente (ver buscarFrecuente arriba). Pedido explícito de Karen --
      // antes cédula era el 3er campo, y el conductor ya había escrito su
      // nombre a mano antes de llegar ahí, así que el autocompletado de
      // nombre casi nunca llegaba a tiempo de servir.
      h('div',{className:'fgrid2'},
        h('div',{className:'fg'},h('label',null,'Tipo de documento',h('span',{className:'req'},'*')),
          h('select',{value:vehiculo.tipo_documento,onChange:e=>setVehiculo(p=>({...p,tipo_documento:e.target.value}))},
            ...tiposDocumento.map(t=>h('option',{key:t,value:t},t))
          )
        ),
        h('div',{className:'fg'},h('label',null,'N° de documento',h('span',{className:'req'},'*')),
          h('input',{type:'text',value:vehiculo.cedula_conductor,
            onChange:e=>{setVehiculo(p=>({...p,cedula_conductor:e.target.value}));setFrecuente(null);},
            onBlur:e=>buscarFrecuente(e.target.value),
            placeholder:'Número'}),
          frecuente===true&&h('div',{style:{marginTop:5,padding:'5px 9px',borderRadius:7,fontSize:11,fontWeight:700,display:'flex',alignItems:'center',gap:5,background:'#d1fae5',color:'#065f46',border:'1px solid #6ee7b7'}},
            h(Ico,{n:'check',s:12}),'Te reconocimos — completa los datos que falten')
        )
      ),
      h('div',{className:'fg'},h('label',null,'Placa',h('span',{className:'req'},'*')),
        h('input',{type:'text',value:vehiculo.placa_vehiculo,onChange:e=>setVehiculo(p=>({...p,placa_vehiculo:e.target.value.toUpperCase().replace(/[^A-Z0-9]/g,'')})),placeholder:'ABC123 (letras y luego números, sin espacios ni guiones)'})
      ),
      h('div',{className:'fg'},h('label',null,'Nombre conductor',h('span',{className:'req'},'*')),h('input',{type:'text',value:vehiculo.nombre_conductor,onChange:e=>setVehiculo(p=>({...p,nombre_conductor:e.target.value})),onBlur:()=>setVehiculo(p=>({...p,nombre_conductor:capitalizarNombre(p.nombre_conductor)})),placeholder:'Nombre completo'})),
      h('div',{className:'fgrid2'},
        h('div',{className:'fg'},h('label',null,'Teléfono',h('span',{className:'req'},'*')),h('input',{type:'tel',value:vehiculo.telefono_conductor,onChange:e=>setVehiculo(p=>({...p,telefono_conductor:e.target.value})),placeholder:'Número de contacto'})),
        h('div',{className:'fg'},h('label',null,'Tipo vehículo',h('span',{className:'req'},'*')),
          h('select',{value:vehiculo.tipo_vehiculo,onChange:e=>setVehiculo(p=>({...p,tipo_vehiculo:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),...tiposVehiculo.map(t=>h('option',{key:t,value:t},t))
          )
        )
      ),
      h('div',{className:'fg'},h('label',null,'Hora de tu cita'),
        vehiculo.hora_cita
          ? h('div',{style:{padding:'8px 10px',borderRadius:8,background:'#f1f5f9',border:'1.5px dashed var(--border)',fontWeight:700,fontSize:13,color:'var(--text)',display:'flex',alignItems:'center',gap:6}},h(Ico,{n:'clock',s:13}),vehiculo.hora_cita)
          : h('div',{style:{padding:'8px 10px',borderRadius:8,background:'#f8fafc',border:'1.5px dashed var(--border)',fontSize:12,color:'var(--slate)',display:'flex',alignItems:'center',gap:6}},h(Ico,{n:'clock',s:13}),'Se completa sola al agregar tu primera orden abajo')
      )
    ),
    h('div',{className:'fcard'},
      h('p',{className:'sec-ttl'},h(Ico,{n:'checkCircle',s:12}),' Seguridad y carga'),
      h('div',{className:'fgrid2'},
        h('div',{className:'fg'},h('label',null,'Fecha ARL',h('span',{className:'req'},'*')),h('input',{type:'date',min:'2000-01-01',max:'2100-12-31',value:vehiculo.fecha_pago_arl,onChange:e=>{if(fechaValida(e.target.value))setVehiculo(p=>({...p,fecha_pago_arl:e.target.value}));}})),
        h('div',{className:'fg'},h('label',null,'¿Cuentas con EPP?',h('span',{className:'req'},'*')),
          h('select',{value:vehiculo.epp_cumple,onChange:e=>setVehiculo(p=>({...p,epp_cumple:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),h('option',{value:'si'},'Sí'),h('option',{value:'no'},'No')
          )
        )
      ),
      vehiculo.epp_cumple==='no'&&h('div',{className:'warn'},'Sin los elementos de protección personal completos, puede que no se autorice tu ingreso.'),
      h('div',{className:'fgrid2'},
        h('div',{className:'fg'},h('label',null,'Tipo de carga',h('span',{className:'req'},'*')),
          h('select',{value:vehiculo.tipo_carga,onChange:e=>setVehiculo(p=>({...p,tipo_carga:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),...tiposCarga.map(t=>h('option',{key:t,value:t},t))
          )
        ),
        h('div',{className:'fg'},h('label',null,'Formato de carga',h('span',{className:'req'},'*')),
          h('select',{value:vehiculo.formato_carga,onChange:e=>{
            const v=e.target.value;
            setVehiculo(p=>({...p,formato_carga:v,cantidad_pallets:(v==='Granel'||v==='Mixta')?'No aplica':(p.cantidad_pallets==='No aplica'?'':p.cantidad_pallets)}));
          }},
            h('option',{value:''},'Seleccionar...'),...formatosCarga.map(t=>h('option',{key:t,value:t},t))
          )
        )
      ),
      h('div',{className:'fgrid2'},
        h('div',{className:'fg'},h('label',null,'Cantidad de pallets',h('span',{className:'req'},'*')),
          h('input',{type:'text',inputMode:'numeric',value:vehiculo.cantidad_pallets,readOnly:vehiculo.formato_carga==='Granel'||vehiculo.formato_carga==='Mixta',onChange:e=>setVehiculo(p=>({...p,cantidad_pallets:e.target.value})),placeholder:'Ej: 10',style:(vehiculo.formato_carga==='Granel'||vehiculo.formato_carga==='Mixta')?{background:'#f8fafc',cursor:'default'}:null})
        ),
        h('div',{className:'fg'},h('label',null,'¿Quién maneja la carga?',h('span',{className:'req'},'*')),
          h('select',{value:vehiculo.manejo_carga,onChange:e=>setVehiculo(p=>({...p,manejo_carga:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),...manejosCarga.map(t=>h('option',{key:t,value:t},t))
          )
        )
      ),
      vehiculo.manejo_carga==='Conductor con certificado de montacargas'&&h('div',{className:'tip'},'Recuerda traer tu certificado de montacargas vigente.'),
      h(LogisticaInversaField,{value:vehiculo.tipos_logistica_inversa,onChange:v=>setVehiculo(p=>({...p,tipos_logistica_inversa:v}))})
    ),
    h('div',{className:'fcard',style:{border:'1.5px solid var(--navy)'}},
      h('p',{className:'sec-ttl',style:{color:'var(--navy)'}},h(Ico,{n:'package',s:12}),` Proveedores / órdenes que traes (${ordenes.length})`),
      ordenes.map((o,i)=>h('div',{key:i,style:{padding:'6px 0',borderBottom:'1px solid var(--border)'}},
        h('div',{style:{display:'flex',alignItems:'center',gap:8}},
          h('div',{style:{flex:1,minWidth:0}},
            h('div',{style:{fontWeight:700,fontSize:13}},o.empresa),
            h('div',{style:{fontSize:11,color:'var(--slate)'}},'OC '+o.numero_orden_compra+(o._horaCita?' · Cita '+o._horaCita:''))
          ),
          h('button',{onClick:()=>quitarOrden(i),'aria-label':'Quitar esta orden de la lista',style:{background:'#fee2e2',border:'none',cursor:'pointer',color:'#dc2626',padding:'10px',minWidth:36,minHeight:36,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:8,fontSize:11,flexShrink:0}},h(Ico,{n:'trash',s:14}))
        ),
        o._avisoHora&&h('div',{style:{marginTop:4,padding:'6px 9px',borderRadius:7,fontSize:11,fontWeight:600,display:'flex',alignItems:'flex-start',gap:5,background:'#fef3c7',color:'#92400e',border:'1px solid #fde68a'}},
          h(Ico,{n:'alert',s:12}),`Esta orden tiene una cita a las ${o._horaCita}. Ya se registró tu llegada a las ${vehiculo.hora_cita} y esa es la hora que queda — no tienes que hacer nada.`
        )
      )),
      h('div',{style:{marginTop:10,paddingTop:10,borderTop:'1px dashed var(--border)'}},
        h('div',{className:'fg'},h('label',null,'N° orden de compra',h('span',{className:'req'},'*')),
          h('input',{type:'text',inputMode:'numeric',maxLength:10,value:ordenDraft.numero_orden_compra,onChange:e=>setOrdenDraft(p=>({...p,numero_orden_compra:e.target.value.replace(/[^0-9]/g,'').slice(0,10)})),placeholder:'10 dígitos, empieza en 4 (ej. 4001234567)'})
        ),
        // El input solo dispara la búsqueda cuando calza el patrón /^4\d{9}$/;
        // si el conductor llega a 10 dígitos pero no arrancan en 4, la
        // búsqueda nunca se dispara y antes se quedaba sin ningún mensaje
        // (placeholder ya tapado, botón gris sin explicación). Este aviso
        // cubre ese hueco sin tocar la llamada al servidor.
        ordenDraft.numero_orden_compra.length===10&&!ordenDraft.numero_orden_compra.startsWith('4')&&h('div',{style:{marginTop:5,marginBottom:8,padding:'8px 10px',borderRadius:7,fontSize:12,fontWeight:600,display:'flex',alignItems:'flex-start',gap:6,background:'#fee2e2',color:'#991b1b',border:'1px solid #fca5a5'}},
          h(Ico,{n:'alert',s:14}),'El número de orden debe empezar en 4. Revisa que lo hayas escrito completo y sin errores.'
        ),
        citaOrdenInfo?.estado==='buscando'&&h('div',{style:{marginTop:5,marginBottom:8,padding:'8px 10px',borderRadius:7,fontSize:12,fontWeight:600,color:'#1e40af',display:'flex',alignItems:'center',gap:8,background:'#eff6ff',border:'1px solid #bfdbfe'}},
          h('div',{className:'loading-dots',style:{padding:0,gap:4,transform:'scale(.7)',transformOrigin:'left center'}},h('span'),h('span'),h('span')),'Buscando cita programada...'
        ),
        citaOrdenInfo?.estado==='encontrado'&&h('div',{className:'fg'},h('label',null,'Proveedor'),
          h('div',{style:{padding:'8px 10px',borderRadius:8,background:'#d1fae5',border:'1px solid #6ee7b7',color:'#065f46',fontWeight:700,fontSize:13,display:'flex',alignItems:'center',gap:6}},
            h(Ico,{n:'check',s:14}),citaOrdenInfo.proveedor
          )
        ),
        citaOrdenInfo?.estado==='no_encontrado'&&h('div',{style:{marginTop:5,marginBottom:8,padding:'8px 10px',borderRadius:7,fontSize:12,fontWeight:600,display:'flex',alignItems:'flex-start',gap:6,background:'#fee2e2',color:'#991b1b',border:'1px solid #fca5a5'}},
          h(Ico,{n:'alert',s:14}),'Esta orden no aparece en las citas programadas de hoy. Acércate a la caseta para que el guarda registre tu ingreso.'
        ),
        citaOrdenInfo?.estado==='error'&&h('div',{style:{marginTop:5,marginBottom:8,padding:'8px 10px',borderRadius:7,fontSize:12,fontWeight:600,display:'flex',alignItems:'flex-start',gap:6,background:'#fef3c7',color:'#92400e',border:'1px solid #fde68a'}},
          h(Ico,{n:'wifiOff',s:14}),
          h('div',null,
            h('p',{style:{margin:'0 0 5px'}},'No pudimos verificar esta orden — revisa tu señal.'),
            h('button',{type:'button',onClick:()=>buscarCita(ordenDraft.numero_orden_compra),style:{background:'#fff',border:'1.5px solid #92400e',color:'#92400e',borderRadius:6,padding:'5px 12px',fontSize:12,fontWeight:700,cursor:'pointer',fontFamily:'inherit'}},'Reintentar')
          )
        ),
        h('button',{
          onClick:agregarOrden,
          disabled:citaOrdenInfo?.estado!=='encontrado',
          style:{width:'100%',background:'var(--navy)',border:'none',color:'#fff',borderRadius:8,padding:'9px 14px',cursor:citaOrdenInfo?.estado!=='encontrado'?'not-allowed':'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:6,fontSize:13,fontWeight:700,fontFamily:'inherit',opacity:citaOrdenInfo?.estado!=='encontrado'?.5:1}
        },h(Ico,{n:'plus',s:14}),'Agregar a la lista')
      )
    ),
    h('button',{className:'btn-primary',style:{width:'100%',marginTop:4},onClick:enviar,disabled:saving},
      saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Enviando...':'Enviar registro de llegada'
    )
  );
}
