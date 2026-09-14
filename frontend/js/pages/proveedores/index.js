// ── PROVEEDORES PAGE ──
// Extraído de frontend/index.html (líneas 2743-4260, función
// `ProveedoresPage` completa, sección "/* ── PROVEEDORES PAGE ── */" del
// <script> monolítico). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado -- este módulo es una copia
// autocontenida, lista para que la Fase 6 lo importe cuando quede conectado
// vía <script type="module">.
//
// Decisión de Alejandro (arquitecto) para este lote: ProveedoresPage es un
// único closure con ~40 useState/useRef y 4 ramas de render
// (`view==='form'&&esBodega` → "Observación de descargue", `view==='form'`
// sin esa condición → "Editar/Ver Proveedor", `view==='batch'` → "Nuevo
// ingreso", y el modal `citasModal` inline → "Citas del día (WMS)"), no 3
// componentes separables sin refactor real. Se extrae TODO el componente tal
// como está hoy (mover, no rediseñar) a este único archivo -- separar
// EditarRegistro/NuevoIngreso/CitasWMS en archivos propios queda pospuesto
// formalmente a una fase de hardening futura, con tests, no en este lote.
//
// Única cirugía mecánica aplicada sobre el cuerpo copiado (sin reordenar ni
// un solo hook, sin "limpiar" el closure):
//   1. `function ProveedoresPage` -> `export function ProveedoresPage`.
//   2. La rama `if(view==='qr') return h('div', ...)` (líneas 2962-2981 del
//      original, ~20 líneas de JSX inline) se sustituyó por
//      `h(KioscoQR,{qrImgUrl,qrError,onVolver,onDismissError})`, ya que
//      KioscoQR ya fue extraído a su propio archivo en el lote 7a con esa
//      misma firma de props. El estado (`qrImgUrl`/`qrError`) y el polling
//      (`fetchQr`/`useVisibilityPolling`) NO se tocaron ni se movieron: siguen
//      viviendo en este componente, que es quien sabe cuándo `view==='qr'`
//      está activa.
//   3. `DetalleTiempos` (usado en las dos ramas `view==='form'`) y
//      `ConfirmarMuelleSheet` (usado dos veces: muelle normal en
//      `muelleSheet` y logística inversa en `muelleInversaSheet`) ya se
//      llamaban en el monolito exactamente con el mismo nombre e igual forma
//      de invocación (`h(DetalleTiempos,{registro:form})`,
//      `h(ConfirmarMuelleSheet,{...})`) -- no requirieron ningún cambio en el
//      cuerpo, solo el import.
//
// No se extrajo ningún fragmento oportunista adicional en este lote: el
// modal de citas (`citasModal`, ~14 estados/handlers propios --
// citasTab/citasRows/citasFileName/citasLoading/citasResult/citasErr/
// citasDiaFecha/citasDiaItems/citasDiaLoading/citasDiaErr/citaEditId/
// citaEditForm/citaEditSaving/citaEditErr, más los handlers
// handleCitasFile/handleCitasImport/empezarEditarCita/cancelarEditarCita/
// guardarEditarCita/cargarCitasDia) fue evaluado por Alejandro y NO cumple
// el techo de "presentacional, sin estado propio, máximo 10 props" definido
// para este lote -- queda inline a propósito. El resto del cuerpo (formulario
// de edición, nuevo ingreso, listado con sus 4 pestañas y agrupación por
// puntualidad) tampoco tiene ningún fragmento que cumpla ese techo con
// comodidad sin arrastrar varios de los ~40 estados del closure.
//
// Importa: Ico (core/icons.js); useVisibilityPolling (core/hooks.js); api,
// getToken (core/api-client.js); API_BASE (core/config.js); today,
// ahoraHora, _tsBog, playAlertSound, fmtDate, capitalizarNombre,
// normalizarMuelle, fechaValida, puede (core/utils.js); Alert, LoadingDots,
// ConfirmSheet, CameraField, LogisticaInversaField, LogisticaInversaBadge,
// ConfirmarMuelleSheet (shared/); DetalleTiempos, KioscoQR
// (pages/proveedores/, ya extraídos en el lote 7a).
//
// `window.XLSX` es global vía CDN (igual que en CargaMasivaPage.js), no
// requiere import.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se importa
// como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../../core/icons.js';
import { useVisibilityPolling } from '../../core/hooks.js';
import { api } from '../../core/api-client.js';
import { getToken } from '../../core/auth-store.js';
import { API_BASE } from '../../core/config.js';
import { today, ahoraHora, _tsBog, playAlertSound, fmtDate, capitalizarNombre, normalizarMuelle, fechaValida, puede } from '../../core/utils.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';
import { ConfirmSheet } from '../../shared/ConfirmSheet.js';
import { CameraField } from '../../shared/CameraField.js';
import { LogisticaInversaField } from '../../shared/LogisticaInversaField.js';
import { TipoCargaBadge, LogisticaInversaBadge } from '../../shared/badges.js';
import { ConfirmarMuelleSheet } from '../../shared/ConfirmarMuelleSheet.js';
import { DetalleTiempos } from './DetalleTiempos.js';
import { KioscoQR } from './KioscoQR.js';

const { useState, useCallback, useRef, useEffect } = React;
const h = React.createElement;

export function ProveedoresPage({user,online,addOffline}){
  const [view,setView]         = useState('list');
  const [records,setRecords]   = useState([]);
  const [loading,setLoading]   = useState(true);
  const [saving,setSaving]     = useState(false);
  const [alert,setAlert]       = useState(null);
  const [confirm,setConfirm]   = useState(null);
  const [liberarMuelle,setLiberarMuelle] = useState(null);
  const [deshacerWps,setDeshacerWps] = useState(null);
  const [deshacerConf,setDeshacerConf] = useState(null);
  const [muelleSheet,setMuelleSheet] = useState(null); // registro en tablero de "elegir muelle" (ver ConfirmarMuelleSheet)
  const [muelleInversaSheet,setMuelleInversaSheet] = useState(null); // registro en tablero de "elegir muelle" de logística inversa (19-21)
  const [liberarMuelleInversa,setLiberarMuelleInversa] = useState(null);
  const [selected,setSelected] = useState(null);
  const [salida,setSalida]     = useState(null);
  const [horaSalida,setHoraSalida]     = useState('');
  const [fechaSalidaP,setFechaSalidaP] = useState('');
  const [fotoSalida,setFotoSalida]     = useState(null);
  const esBodega    = user?.rol==='guarda_bodega';
  const esVehicular = user?.rol==='guarda_vehicular';
  const esCoordinador = user?.rol==='coordinador';
  const [filtro,setFiltro]     = useState(esBodega?'dentro':'confirmar'); // confirmar | dentro | todos
  const [busqueda,setBusqueda] = useState('');
  const [bdProv,setBdProv]           = useState([]);
  const [frecuenteInfo,setFrecuenteInfo] = useState(null); // {estado:'encontrado'|'inactivo'|'nuevo', data:obj}
  const [saveFrModal,setSaveFrModal]     = useState(false);
  const [frDraft,setFrDraft]             = useState({cedula:'',nombre_conductor:'',empresa_principal:'',tipo_vehiculo:''});
  const tiposVehiculo = ['Camión','Camioneta','Moto','Furgón','Tractomula','Otro'];
  const tiposCarga = ['Seca','Refrigerada','Mixta'];
  const formatosCarga = ['Paletizada','Granel','Mixta'];
  const manejosCarga = ['Conductor con certificado de montacargas','Reciservicios','Ercol','Operador logístico externo'];
  // Patrón observado en datos históricos (no una regla formal): Refrigerada
  // suele descargar en muelles 1-6, Seca en 13-18. Mixta no tiene patrón
  // claro, por eso no aparece acá -- ver aviso no bloqueante más abajo.
  const MUELLES_HABITUALES = {Refrigerada:[1,6], Seca:[13,18]};

  /* ── EDIT FORM STATE ── */
  const emptyF = {fecha:today(),placa_vehiculo:'',nombre_conductor:'',tipo_documento:'CC',cedula_conductor:'',telefono_conductor:'',tipo_vehiculo:'',hora_ingreso:ahoraHora(),hora_ingreso_confirmado:'',hora_salida:'',muelle_descargue:'',fecha_pago_arl:'',epp_cumple:'',tipo_carga:'',formato_carga:'',cantidad_pallets:'',manejo_carga:'',observaciones:'',foto_url:null};
  const [form,setForm]               = useState(emptyF);
  const [formOrdenes,setFormOrdenes] = useState([]);
  const [formOrd,setFormOrd]         = useState({empresa:'',carga_compartida:false,actividad_a_desarrollar:'',dependencia_autoriza:''});
  const [addingOrd,setAddingOrd]     = useState(false);

  /* ── NUEVO INGRESO STATE ── */
  const emptyVeh = ()=>({fecha:today(),placa_vehiculo:'',tipo_documento:'CC',cedula_conductor:'',nombre_conductor:'',telefono_conductor:'',tipo_vehiculo:'',hora_ingreso:ahoraHora(),hora_cita:'',muelle_descargue:'',fecha_pago_arl:'',epp_cumple:'',tipo_carga:'',formato_carga:'',cantidad_pallets:'',manejo_carga:'',tipos_logistica_inversa:null,observaciones:'',foto_url:null});
  const emptyOrd = {empresa:'',numero_orden_compra:'',carga_compartida:false,actividad_a_desarrollar:'',dependencia_autoriza:'',cita_id:null};
  const [vehiculoForm,setVehiculoForm]     = useState(emptyVeh);
  const [ordenes,setOrdenes]               = useState([]);
  const [ordenDraft,setOrdenDraft]         = useState(emptyOrd);
  const [ordenEditingIdx,setOrdenEditingIdx] = useState(null);
  const [citaOrdenInfo,setCitaOrdenInfo]   = useState(null); // {estado:'encontrado'|'no_encontrado'}

  /* Citas de hoy sin llegada registrada (GET /proveedores/citas/alertas).
     Alimenta la pestaña "📅 Con cita" -- render mínimo a propósito, Laura
     diseña la card final después, esto solo deja el dato disponible. */
  const [citasAlertas,setCitasAlertas] = useState({pendientes:[],por_vencer:[],atrasadas:[]});

  /* ── CARGA DIARIA DE CITAS (WMS) ──
     Sin fecha global: "Fecha Ejec." viene por fila en el archivo, el backend
     calcula las fechas distintas presentes y reemplaza cada una. */
  const [citasModal,setCitasModal]     = useState(false);
  const [citasTab,setCitasTab]         = useState('subir'); // 'subir' | 'ver' -- dos usos distintos del mismo modal (ver comentario en el render)
  const [citasRows,setCitasRows]       = useState([]);
  const [citasFileName,setCitasFileN]  = useState('');
  const [citasLoading,setCitasLoading] = useState(false);
  const [citasResult,setCitasResult]   = useState(null);
  const [citasErr,setCitasErr]         = useState('');

  /* ── LISTA DE CITAS DEL DÍA (edición manual de hora) ──
     GET /proveedores/citas?fecha=... -- a diferencia del import (que ya no
     tiene selector de fecha porque "Fecha Ejec." viaja por fila del
     archivo), acá SÍ hace falta un selector: se están consultando citas
     YA guardadas en la BD, no un archivo nuevo. Render mínimo a propósito
     -- Laura lo rediseña después, esto solo conecta el dato. */
  const [citasDiaFecha,setCitasDiaFecha]     = useState(today());
  const [citasDiaItems,setCitasDiaItems]     = useState([]);
  const [citasDiaLoading,setCitasDiaLoading] = useState(false);
  const [citasDiaErr,setCitasDiaErr]         = useState('');
  const [citaEditId,setCitaEditId]           = useState(null); // id de citas_programadas en edición
  const [citaEditForm,setCitaEditForm]       = useState({hora_cita_inicio:'',hora_cita_fin:'',motivo:''});
  const [citaEditSaving,setCitaEditSaving]   = useState(false);
  const [citaEditErr,setCitaEditErr]         = useState('');

  const load = useCallback(()=>{
    api.get('/proveedores').then(r=>setRecords(r.items||r)).catch(()=>setAlert({type:'err',msg:'Error cargando datos'})).finally(()=>setLoading(false));
    // Mismo ciclo de polling que /proveedores (no se agrega un segundo
    // intervalo): citas de hoy sin llegada registrada, para avisarle al
    // guarda que llame al proveedor.
    api.get('/proveedores/citas/alertas').then(setCitasAlertas).catch(()=>{});
  },[]);
  // Proveedores es operativa (alerta de hora de cita): 1 min y se pausa en
  // background.
  useVisibilityPolling(load, 60000, [load]);

  // Suena una alerta cuando a un proveedor por confirmar le falten ≤5 min para
  // su hora de cita (declarada por el conductor). Una sola vez por registro.
  const avisados5min = useRef(new Set());
  useEffect(()=>{
    const pendientesIds = new Set();
    records.forEach(r=>{
      if(r.estado_confirmacion!=='pendiente' || !r.hora_cita) return;
      pendientesIds.add(r.id);
      const [ch,cm] = r.hora_cita.split(':').map(Number);
      const [ah,am] = ahoraHora().split(':').map(Number);
      const diff = (ch*60+cm) - (ah*60+am);
      if(diff>=0 && diff<=5 && !avisados5min.current.has(r.id)){
        avisados5min.current.add(r.id);
        playAlertSound();
      }
    });
    // Limpia ids que ya no aplican (confirmados o fuera de la lista) para no
    // acumular memoria indefinidamente en un turno largo.
    avisados5min.current.forEach(id=>{ if(!pendientesIds.has(id)) avisados5min.current.delete(id); });
  },[records]);

  // Suena cada 7 min mientras un pendiente siga atrasado en su hora de cita
  // (diff<0) y sin marcar WPS. Independiente de avisados5min (ese es
  // proactivo/una vez; este es reactivo/repetido). Un timestamp por id, no un
  // booleano, para poder re-disparar.
  const avisadosAtraso = useRef(new Map()); // id -> ms del último aviso
  useEffect(()=>{
    const activosIds = new Set();
    const ahoraMs = Date.now();
    records.forEach(r=>{
      if(r.estado_confirmacion!=='pendiente' || !r.hora_cita) return;
      const [ch,cm] = r.hora_cita.split(':').map(Number);
      const [ah,am] = ahoraHora().split(':').map(Number);
      const diff = (ch*60+cm) - (ah*60+am);
      if(diff<0){
        activosIds.add(r.id);
        const ultimo = avisadosAtraso.current.get(r.id);
        if(ultimo==null || ahoraMs-ultimo >= 7*60*1000){
          avisadosAtraso.current.set(r.id, ahoraMs);
          playAlertSound();
        }
      }
    });
    avisadosAtraso.current.forEach((_,id)=>{ if(!activosIds.has(id)) avisadosAtraso.current.delete(id); });
  },[records]);

  useEffect(()=>{
    api.get('/maestros/proveedores').then(r=>setBdProv(Array.isArray(r)?r:(r.items||[]))).catch(()=>{});
  },[]);

  // muelle es opcional: si viene, viaja como muelle_descargue en el mismo
  // PUT que confirma (ver ConfirmarMuelleSheet, tablero que abre el botón
  // "Confirmar"). Sin muelle, el comportamiento es exactamente el de
  // siempre -- confirma sin tocar el muelle.
  const confirmarIngreso = async(id,muelle)=>{
    try{
      const body = muelle?{muelle_descargue:String(muelle)}:{};
      await api.put(`/proveedores/${id}/confirmar`,body);
      setAlert({type:'ok',msg:muelle?`Ingreso confirmado — muelle ${muelle}`:'Ingreso confirmado'});
      load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
  };

  const marcarWps = async(id)=>{
    try{
      await api.put(`/proveedores/${id}/marcar-wps`,{});
      setAlert({type:'ok',msg:'Ingreso a WPS marcado'});
      load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
  };

  /* ── QR de ingreso (kiosco de portería) ── */
  const [qrImgUrl,setQrImgUrl] = useState(null);
  const [qrError,setQrError]   = useState(null);
  // Ref (en vez de la `view` capturada en el closure) para descartar una
  // respuesta que llegue tarde después de que el usuario ya salió de esta
  // vista (o volvió a entrar y ya hay un fetch más nuevo en curso).
  const viewRef = useRef(view);
  viewRef.current = view;
  const fetchQr = useCallback(()=>{
    fetch(`${API_BASE}/proveedores/qr-imagen`,{headers:{Authorization:'Bearer '+getToken()}})
      .then(r=>{ if(!r.ok) throw new Error('No se pudo generar el QR'); return r.text(); })
      .then(svg=>{ if(viewRef.current==='qr'){ setQrError(null); setQrImgUrl('data:image/svg+xml;utf8,'+encodeURIComponent(svg)); } })
      .catch(e=>{ if(viewRef.current==='qr') setQrError(e.message); });
  },[]);
  // El QR expira a los 5 min (QR_INGRESO_TTL_SEG en el backend); 90s deja
  // margen amplio. Se limita a la vista 'qr' (enabled) y se pausa si la
  // pestaña queda oculta -- si nadie ve el kiosco, nadie va a escanearlo.
  useVisibilityPolling(fetchQr, 90000, [], view==='qr');

  // Traduce el body de error de FastAPI (string simple de HTTPException o
  // lista de errores 422 de Pydantic) a un texto legible -- mismo criterio
  // de parseo que textoErrorAnulacion.
  // Nota: se declara aquí (junto al resto de hooks del componente, arriba de
  // cualquier return condicional) porque cargarCitasDia -- un hook -- la
  // referencia; si quedara declarada más abajo, el closure de cargarCitasDia
  // podría capturarla antes de su inicialización (TDZ) en un render que
  // retorna temprano (view 'qr'/'form'/'batch').
  const _textoErrorCita = ex => {
    let m = ex.message || 'Error';
    try{
      const parsed = JSON.parse(m);
      if(typeof parsed.detail === 'string') m = parsed.detail;
      else if(Array.isArray(parsed.detail) && parsed.detail[0]) m = String(parsed.detail[0].msg||'').replace(/^Value error,\s*/i,'');
    }catch(_){}
    return m;
  };

  // ── LISTA DE CITAS DEL DÍA (edición manual de hora) ── carga de datos.
  // IMPORTANTE: este useCallback y el useEffect siguiente deben ir aquí,
  // junto con el resto de los hooks del componente, y NUNCA después de un
  // return condicional (ver bug de React error #300: "Rendered fewer hooks
  // than expected" cuando quedaron declarados más abajo, después de los
  // returns de las vistas 'qr'/'form').
  const cargarCitasDia = useCallback(()=>{
    if(!citasDiaFecha) return;
    setCitasDiaLoading(true); setCitasDiaErr('');
    api.get(`/proveedores/citas?fecha=${citasDiaFecha}`)
      .then(r=>setCitasDiaItems(r.items||[]))
      .catch(ex=>setCitasDiaErr(_textoErrorCita(ex)))
      .finally(()=>setCitasDiaLoading(false));
  },[citasDiaFecha]);

  useEffect(()=>{ if(citasModal) cargarCitasDia(); },[citasModal,cargarCitasDia]);

  if(view==='qr') return h(KioscoQR,{qrImgUrl,qrError,onVolver:()=>setView('list'),onDismissError:()=>setQrError(null)});

  const lookupConductor = async(cedula,setter)=>{
    if(!cedula||String(cedula).length<5) return;
    // 1. Buscar en catálogo de frecuentes
    try{
      const frecuentes = await api.get(`/maestros/conductores-frecuentes?cedula=${encodeURIComponent(cedula)}`);
      const flist = Array.isArray(frecuentes)?frecuentes:(frecuentes.items||[]);
      const fm = flist.find(c=>String(c.cedula)===String(cedula));
      if(fm){
        setter(p=>({...p,
          nombre_conductor:fm.nombre_conductor||p.nombre_conductor,
          tipo_vehiculo:p.tipo_vehiculo||fm.tipo_vehiculo||'',
          telefono_conductor:p.telefono_conductor||fm.telefono||'',
        }));
        if(!fm.activo){
          setFrecuenteInfo({estado:'inactivo',data:fm});
        } else {
          setFrecuenteInfo({estado:'encontrado',data:fm});
          if(fm.empresa_principal) setOrdenDraft(p=>({...p,empresa:p.empresa||fm.empresa_principal}));
        }
        return;
      }
    }catch(_){}
    // 2. Fallback: conductores internos
    try{
      const res = await api.get('/conductores?activo=true&limit=300');
      const list = Array.isArray(res)?res:(res.items||[]);
      const m = list.find(c=>String(c.cedula)===String(cedula));
      if(m) setter(p=>({...p,nombre_conductor:m.nombre_completo||m.nombre||p.nombre_conductor}));
    }catch(e){}
    setFrecuenteInfo(p=>p||{estado:'nuevo',data:null});
  };

  /* guardar vehículo editado (datos generales) */
  const handleSave = async()=>{
    if(!(form.placa_vehiculo||'').trim()) return setAlert({type:'err',msg:'La placa es obligatoria'});
    if(!(form.nombre_conductor||'').trim()) return setAlert({type:'err',msg:'El nombre del conductor es obligatorio'});
    if(!(form.cedula_conductor||'').trim()) return setAlert({type:'err',msg:'La cédula del conductor es obligatoria'});
    setSaving(true);
    const body = Object.fromEntries(Object.entries(form).filter(([,v])=>v!=null&&v!==''));
    try{
      if(selected) await api.put(`/proveedores/${selected.id}`,body);
      else await api.post('/proveedores',{vehiculo:body,ordenes:[]});
      setAlert({type:'ok',msg:'Registro guardado'});
      setView('list');setForm(emptyF);setSelected(null);setFormOrdenes([]);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  /* agregar orden al registro editado (llamada API inmediata) */
  const agregarOrdenForm = async()=>{
    if(!formOrd.empresa.trim()) return setAlert({type:'err',msg:'La empresa es obligatoria'});
    try{
      const res = await api.post(`/proveedores/${selected.id}/ordenes`,formOrd);
      setFormOrdenes(p=>[...p,{...formOrd,id:res.id,proveedor_id:selected.id}]);
      setFormOrd({empresa:'',muelle_descargue:'',carga_compartida:false,actividad_a_desarrollar:'',dependencia_autoriza:''});
      setAddingOrd(false);
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
  };

  /* eliminar orden del registro editado */
  const eliminarOrdenForm = async(oid)=>{
    try{
      await api.del(`/proveedores/${selected.id}/ordenes/${oid}`);
      setFormOrdenes(p=>p.filter(o=>o.id!==oid));
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
  };

  /* agregar orden a la lista local (nuevo ingreso) */
  const agregarOrden = ()=>{
    if(!ordenDraft.empresa.trim()) return setAlert({type:'err',msg:'La empresa es obligatoria'});
    const dup = ordenes.some((o,i)=>i!==ordenEditingIdx&&o.empresa.toLowerCase()===ordenDraft.empresa.toLowerCase());
    if(dup) return setAlert({type:'err',msg:'Esta empresa ya está en el ingreso'});
    if(ordenEditingIdx!==null){
      setOrdenes(p=>{const n=[...p];n[ordenEditingIdx]={...ordenDraft};return n;});
      setOrdenEditingIdx(null);
    }else{
      setOrdenes(p=>[...p,{...ordenDraft}]);
    }
    setOrdenDraft({...emptyOrd});
    setCitaOrdenInfo(null);
  };

  /* citas_programadas.numero_orden_compra exige 10 dígitos que empiecen en 4
     (mismo CHECK/regex ^4\d{9}$ que ya usa proveedores_ordenes en el
     autorregistro QR del conductor). El guarda puede teclear el número tal
     cual aparece en el WMS ("PT - 4602898240 - 2"); se extrae el patrón de
     10 dígitos de adentro del texto (no se asume posición fija) antes de
     comparar contra la BD -- comparar el texto crudo nunca haría match. */
  const _extraerNumeroOrden = (v)=>{
    const s = String(v||'').trim();
    if(!s) return '';
    const grupos = s.match(/\d+/g) || [];
    const encontrado = grupos.find(g=>g.length===10 && g[0]==='4');
    return encontrado || '';
  };

  /* Autocompletado desde las citas del día cargadas por el guarda (WMS).
     Nunca bloquea: si no hay match, el guarda sigue llenando a mano. Solo
     pisa Empresa/Proveedor y Hora de cita si esos campos están vacíos, para
     no sobrescribir algo que el guarda ya haya escrito. */
  const buscarCitaOrden = async(valor)=>{
    const numero = _extraerNumeroOrden(valor);
    if(!numero){ setCitaOrdenInfo(null); return; }
    try{
      const res = await api.get(`/proveedores/citas/buscar?fecha=${encodeURIComponent(vehiculoForm.fecha)}&numero_orden_compra=${encodeURIComponent(numero)}`);
      if(res && res.encontrado){
        setCitaOrdenInfo({estado:'encontrado',proveedor:res.proveedor_nombre,hora:res.hora_cita_inicio});
        // cita_id viaja con la orden hasta el POST /proveedores para que el
        // backend marque proveedores_ordenes.cita_id (ver GET /citas/buscar).
        setOrdenDraft(p=>({...p,empresa:p.empresa.trim()?p.empresa:(res.proveedor_nombre||p.empresa),cita_id:res.cita_id||null}));
        if(res.hora_cita_inicio) setVehiculoForm(p=>({...p,hora_cita:p.hora_cita?p.hora_cita:res.hora_cita_inicio}));
      }else{
        setCitaOrdenInfo({estado:'no_encontrado'});
        setOrdenDraft(p=>({...p,cita_id:null}));
      }
    }catch(e){ setCitaOrdenInfo(null); } // silencioso: nunca bloquea el registro manual
  };

  /* guardar nuevo ingreso completo (vehículo + órdenes) */
  const guardarIngreso = async()=>{
    if(!vehiculoForm.placa_vehiculo.trim()) return setAlert({type:'err',msg:'La placa es obligatoria'});
    if(!vehiculoForm.cedula_conductor.trim()) return setAlert({type:'err',msg:'La cédula del conductor es obligatoria'});
    if(!vehiculoForm.nombre_conductor.trim()) return setAlert({type:'err',msg:'El nombre del conductor es obligatorio'});
    if(ordenes.length===0) return setAlert({type:'err',msg:'Agrega al menos un proveedor'});
    if(!Array.isArray(vehiculoForm.tipos_logistica_inversa)) return setAlert({type:'err',msg:'Indica si el vehículo trae logística inversa (selecciona una opción o marca "No aplica")'});
    setSaving(true);
    try{
      const ts=await _tsBog();
      await api.post('/proveedores',{
        vehiculo:{...vehiculoForm,placa_vehiculo:vehiculoForm.placa_vehiculo.toUpperCase(),fecha:ts.fecha,hora_ingreso:ts.hora},
        ordenes
      });
      // Actualizar ultima_visita si conductor frecuente conocido (activo o inactivo)
      if(frecuenteInfo?.data?.id){
        api.put(`/maestros/conductores-frecuentes/${frecuenteInfo.data.id}`,{ultima_visita:ts.fecha}).catch(()=>{});
      }
      const esNuevo = !frecuenteInfo || frecuenteInfo.estado==='nuevo';
      setAlert({type:'ok',msg:`Ingreso registrado (${ordenes.length} orden${ordenes.length>1?'es':''})`});
      setView('list');
      // Ofrecer guardar como frecuente si conductor nuevo
      if(esNuevo&&vehiculoForm.cedula_conductor.trim()){
        setFrDraft({cedula:vehiculoForm.cedula_conductor,nombre_conductor:vehiculoForm.nombre_conductor,empresa_principal:ordenes[0]?.empresa||'',tipo_vehiculo:vehiculoForm.tipo_vehiculo});
        setSaveFrModal(true);
      }
      setFrecuenteInfo(null);
      setCitaOrdenInfo(null);
      setVehiculoForm(emptyVeh());setOrdenes([]);setOrdenDraft({...emptyOrd});setOrdenEditingIdx(null);
      load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  if(view==='form' && esBodega) return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>{setView('list');setForm(emptyF);setSelected(null);setFormOrdenes([]);},style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,'Observación de descargue'),h('span',null,'Proveedores'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h(DetalleTiempos,{registro:form}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'package',s:12}),' Proveedor'),
        h('div',{className:'fg'},h('label',null,'Empresa(s)'),h('p',{style:{fontWeight:600,padding:'4px 0',color:'var(--text)'}},
          formOrdenes.map(o=>o.empresa).filter(Boolean).join(' · ')||form.empresa||'—'
        )),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Conductor'),h('p',{style:{padding:'4px 0',color:'var(--text2)'}},form.nombre_conductor||'—')),
          h('div',{className:'fg'},h('label',null,'Placa'),h('p',{style:{padding:'4px 0',color:'var(--text2)'}},form.placa_vehiculo||'—'))
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Hora de llegada'),h('p',{style:{padding:'4px 0',color:'var(--text2)'}},form.hora_ingreso||'—')),
          h('div',{className:'fg'},h('label',null,'Hora de ingreso'),h('p',{style:{padding:'4px 0',color:'var(--text2)'}},form.hora_ingreso_confirmado||'Sin confirmar'))
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'clipboard',s:12}),' Observación del descargue'),
        h('div',{className:'fg'},
          h('label',null,'Notas'),
          h('textarea',{value:form.observaciones,onChange:e=>setForm(p=>({...p,observaciones:e.target.value})),rows:4,placeholder:'Novedades, instrucciones, motivo de rechazo si aplica, etc.'})
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'camera',s:12}),' Fotografía (opcional)'),
        h(CameraField,{value:form.foto_url,onChange:v=>setForm(p=>({...p,foto_url:v}))})
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);setFormOrdenes([]);}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar observación'
      )
    )
  );

  /* ── VISTA: EDITAR REGISTRO INDIVIDUAL ── */
  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>{setView('list');setForm(emptyF);setSelected(null);setFormOrdenes([]);setAddingOrd(false);},style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,esCoordinador?'Ver Proveedor':'Editar Proveedor'),h('span',null,'Proveedores'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      esCoordinador&&h('p',{style:{fontSize:12,color:'var(--slate)',margin:'0 0 8px'}},'Solo lectura'),
      h('div',{style:{pointerEvents:esCoordinador?'none':undefined}},
      h(DetalleTiempos,{registro:form}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'truck',s:12}),' Vehículo y conductor'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha'),h('input',{type:'date',value:form.fecha,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Placa'),h('input',{type:'text',value:form.placa_vehiculo,onChange:e=>setForm(p=>({...p,placa_vehiculo:e.target.value.toUpperCase()})),placeholder:'ABC-123'}))
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Tipo documento'),
            h('select',{value:form.tipo_documento||'CC',onChange:e=>setForm(p=>({...p,tipo_documento:e.target.value}))},
              h('option',{value:'CC'},'CC'),h('option',{value:'NIT'},'NIT'),h('option',{value:'Otro'},'Otro')
            )
          ),
          h('div',{className:'fg'},h('label',null,'N° documento conductor'),h('input',{type:'text',value:form.cedula_conductor||'',onChange:e=>setForm(p=>({...p,cedula_conductor:e.target.value})),placeholder:'Número'}))
        ),
        h('div',{className:'fg'},h('label',null,'Nombre conductor'),h('input',{type:'text',value:form.nombre_conductor,onChange:e=>setForm(p=>({...p,nombre_conductor:e.target.value})),onBlur:()=>setForm(p=>({...p,nombre_conductor:capitalizarNombre(p.nombre_conductor)})),placeholder:'Nombre completo'})),
        h('div',{className:'fg'},h('label',null,'Teléfono conductor'),h('input',{type:'tel',value:form.telefono_conductor||'',onChange:e=>setForm(p=>({...p,telefono_conductor:e.target.value})),placeholder:'Número de contacto (opcional)'})),
        h('div',{className:'fg'},h('label',null,'Tipo vehículo'),
          h('select',{value:form.tipo_vehiculo,onChange:e=>setForm(p=>({...p,tipo_vehiculo:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),...tiposVehiculo.map(t=>h('option',{key:t,value:t},t))
          )
        ),
        h('div',{className:'fg'},h('label',null,'Muelle descargue'),h('input',{type:'text',value:form.muelle_descargue||'',onChange:e=>setForm(p=>({...p,muelle_descargue:e.target.value})),placeholder:'N° muelle'}))
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'checkCircle',s:12}),' Seguridad y carga'),
        h('div',{className:'fg'},h('label',null,'¿Cuenta con EPP?'),
          h('select',{value:form.epp_cumple===true?'si':form.epp_cumple===false?'no':'',onChange:e=>setForm(p=>({...p,epp_cumple:e.target.value===''?'':e.target.value==='si'}))},
            h('option',{value:''},'—'),h('option',{value:'si'},'Sí'),h('option',{value:'no'},'No')
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Tipo de carga'),
            h('select',{value:form.tipo_carga||'',onChange:e=>setForm(p=>({...p,tipo_carga:e.target.value}))},
              h('option',{value:''},'—'),...tiposCarga.map(t=>h('option',{key:t,value:t},t))
            )
          ),
          h('div',{className:'fg'},h('label',null,'Formato de carga'),
            h('select',{value:form.formato_carga||'',onChange:e=>{
              const v=e.target.value;
              setForm(p=>({...p,formato_carga:v,cantidad_pallets:(v==='Granel'||v==='Mixta')?'No aplica':(p.cantidad_pallets==='No aplica'?'':p.cantidad_pallets)}));
            }},
              h('option',{value:''},'—'),...formatosCarga.map(t=>h('option',{key:t,value:t},t))
            )
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Cantidad de pallets'),
            h('input',{type:'text',value:form.cantidad_pallets||'',readOnly:form.formato_carga==='Granel'||form.formato_carga==='Mixta',onChange:e=>setForm(p=>({...p,cantidad_pallets:e.target.value})),placeholder:'Ej: 10',style:(form.formato_carga==='Granel'||form.formato_carga==='Mixta')?{background:'#f8fafc',cursor:'default'}:null})
          ),
          h('div',{className:'fg'},h('label',null,'Maneja la carga'),
            h('select',{value:form.manejo_carga||'',onChange:e=>setForm(p=>({...p,manejo_carga:e.target.value}))},
              h('option',{value:''},'—'),...manejosCarga.map(t=>h('option',{key:t,value:t},t))
            )
          )
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'check',s:12}),' Horarios y ARL'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Hora de llegada'),h('input',{type:'time',value:form.hora_ingreso,onChange:e=>setForm(p=>({...p,hora_ingreso:e.target.value}))})),
          h('div',{className:'fg'},h('label',null,'Hora de ingreso'),h('input',{type:'time',value:form.hora_ingreso_confirmado||'',readOnly:true,placeholder:'Sin confirmar',style:{background:'#f8fafc',cursor:'default'}}))
        ),
        h('div',{className:'fg'},h('label',null,'Hora salida'),h('input',{type:'time',value:form.hora_salida||'',onChange:e=>setForm(p=>({...p,hora_salida:e.target.value})),placeholder:'También puedes usar el botón "Registrar salida"'})),
        !esBodega&&!esCoordinador&&selected&&selected.estado_confirmacion==='confirmado'&&!form.hora_salida&&h('button',{
          onClick:()=>{setSalida(selected);setHoraSalida(ahoraHora());setFechaSalidaP(today());setView('list');},
          style:{marginBottom:10,background:'#d97706',border:'none',color:'#fff',borderRadius:8,padding:'8px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:12,fontWeight:700,fontFamily:'inherit'}
        },h(Ico,{n:'checkCircle',s:14}),'Registrar salida'),
        h('div',{className:'fg'},h('label',null,'Fecha pago ARL'),h('input',{type:'date',min:'2000-01-01',max:'2100-12-31',value:form.fecha_pago_arl,onChange:e=>{if(fechaValida(e.target.value))setForm(p=>({...p,fecha_pago_arl:e.target.value}));}})),
        h('div',{className:'fg'},h('label',null,'Observaciones'),h('textarea',{value:form.observaciones,onChange:e=>setForm(p=>({...p,observaciones:e.target.value})),rows:2,placeholder:'—'}))
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'camera',s:12}),' Fotografía'),
        h(CameraField,{value:form.foto_url,onChange:v=>setForm(p=>({...p,foto_url:v}))})
      ),
      h('div',{className:'fcard'},
        h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}},
          h('p',{className:'sec-ttl',style:{margin:0}},h(Ico,{n:'package',s:12}),` Órdenes / Proveedores (${formOrdenes.length})`),
          h('button',{onClick:()=>setAddingOrd(v=>!v),style:{background:'var(--navy)',border:'none',color:'#fff',borderRadius:6,padding:'4px 10px',fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:'inherit'}},
            addingOrd?'Cancelar':'+ Agregar')
        ),
        formOrdenes.length===0&&!addingOrd&&h('p',{style:{fontSize:12,color:'var(--slate)',textAlign:'center',padding:'8px 0'}},'Sin órdenes registradas'),
        formOrdenes.map((o,i)=>h('div',{key:o.id||i,style:{display:'flex',alignItems:'center',gap:8,padding:'6px 0',borderBottom:i<formOrdenes.length-1?'1px solid var(--border)':'none'}},
          h('div',{style:{flex:1,minWidth:0}},
            h('div',{style:{fontWeight:700,fontSize:13,color:'var(--text)'}},(o.empresa||'Sin empresa')),
            h('div',{style:{fontSize:11,color:'var(--slate)',marginTop:1}},
              [o.numero_orden_compra&&('OC '+o.numero_orden_compra),o.actividad_a_desarrollar,o.carga_compartida&&'Carga compartida'].filter(Boolean).join(' · ')
            )
          ),
          h('button',{title:'Eliminar orden',onClick:()=>eliminarOrdenForm(o.id),style:{background:'#fee2e2',border:'none',cursor:'pointer',color:'#dc2626',padding:'4px 8px',borderRadius:6,fontSize:11}},h(Ico,{n:'trash',s:12}))
        )),
        addingOrd&&h('div',{style:{marginTop:10,paddingTop:10,borderTop:'1px dashed var(--border)'}},
          h('div',{className:'fg'},
            h('label',null,'Empresa',h('span',{className:'req'},'*')),
            h('input',{type:'text',list:'bd-prov-form-edit',value:formOrd.empresa,onChange:e=>setFormOrd(p=>({...p,empresa:e.target.value})),placeholder:'Selecciona o escribe'}),
            h('datalist',{id:'bd-prov-form-edit'},bdProv.filter(p=>p.activo!==false).map(p=>h('option',{key:p.id,value:p.nombre})))
          ),
          h('div',{className:'fg'},h('label',null,'Carga compartida'),
            h('select',{value:formOrd.carga_compartida?'si':'no',onChange:e=>setFormOrd(p=>({...p,carga_compartida:e.target.value==='si'}))},
              h('option',{value:'no'},'No'),h('option',{value:'si'},'Sí')
            )
          ),
          h('div',{className:'fg'},h('label',null,'Actividad'),h('textarea',{value:formOrd.actividad_a_desarrollar,onChange:e=>setFormOrd(p=>({...p,actividad_a_desarrollar:e.target.value})),rows:2,placeholder:'Opcional'})),
          h('button',{onClick:agregarOrdenForm,style:{width:'100%',marginTop:6,background:'var(--navy)',border:'none',color:'#fff',borderRadius:8,padding:'9px 14px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:6,fontSize:13,fontWeight:700,fontFamily:'inherit'}},
            h(Ico,{n:'plus',s:14}),'Agregar orden')
        )
      )
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);setFormOrdenes([]);setAddingOrd(false);}},h(Ico,{n:'x',s:15})),
      !esCoordinador&&h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar registro'
      )
    )
  );

  /* ── CARGA DIARIA DE CITAS (WMS) — helpers ──
     El parseo del Excel se hace en el navegador con SheetJS (mismo patrón
     que CargaMasivaPage) y se manda al backend ya como JSON. Columnas reales
     del export ("Fecha Ejec.", "O. Compra", "Proveedor", "F. Temporal", y
     desde Fase 5.2 también código de proveedor, flujo, descripción de
     carga, fecha del documento de compra y cantidad de pallets -- paridad
     con cargar_archivo() de citas-muelles-cedi-r10); matching de
     encabezados tolerante a mayúsculas/espacios porque el archivo .xls
     trae variaciones de codificación en otras columnas que no usamos.
     "Transportador" no se envía: citas_programadas (tabla real, compartida
     con una app externa) no tiene columna para guardarlo.
     "Fecha Ejec." viene por fila (YYYYMMDD) -- un mismo archivo puede traer
     más de un día, así que la fecha ya NO se elige a mano, se calcula por
     fila y el backend hace DELETE+INSERT por cada fecha distinta que
     encuentre entre las filas válidas.
     IMPORTANTE: NO se activa `cellDates:true` en XLSX.read (a diferencia
     de citas-muelles-cedi-r10) -- "Fecha Ejec." ya funciona en producción
     asumiendo que la celda llega como texto/numero YYYYMMDD, no como Date;
     activar cellDates globalmente arriesgaba romper ese parseo que ya
     funciona. Por eso "Fecha doc." (fecha_documento_compra) se normaliza
     con el mismo criterio YYYYMMDD/YYYY-MM-DD por texto en vez de asumir
     un objeto Date -- si no calza ningún formato reconocido se manda tal
     cual y el backend la descarta a NULL sin tumbar la fila (ver
     _fecha_documento_opcional en proveedores.py). */
  const _citasFindVal = (row, variantes) => {
    for(const k of Object.keys(row)){
      const kk = String(k).toLowerCase().trim();
      if(variantes.some(v=>kk===v||kk.startsWith(v))) return row[k];
    }
    return '';
  };
  const _citasNormalizarFecha = v => {
    const s = String(v||'').trim();
    if(/^\d{8}$/.test(s)) return `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`;
    if(/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0,10);
    return s;
  };

  const handleCitasFile = e => {
    const file = e.target.files[0];
    if(!file) return;
    if(!window.XLSX){ setCitasErr('Librería Excel no cargada, recarga la página'); return; }
    setCitasFileN(file.name); setCitasResult(null); setCitasErr('');
    const reader = new FileReader();
    reader.onload = ev => {
      try{
        const wb = window.XLSX.read(ev.target.result,{type:'array'});
        const ws = wb.Sheets[wb.SheetNames[0]];
        const raw = window.XLSX.utils.sheet_to_json(ws,{defval:''});
        const parsed = raw.map(row=>{
          const fechaEjec = String(_citasFindVal(row,['fecha ejec.','fecha ejec','fechaejec'])||'').trim();
          const fecha = /^\d{8}$/.test(fechaEjec) ? `${fechaEjec.slice(0,4)}-${fechaEjec.slice(4,6)}-${fechaEjec.slice(6,8)}` : '';
          return {
            fecha,
            numero_orden_compra: _extraerNumeroOrden(_citasFindVal(row,['o. compra','o.compra','orden compra','orden de compra'])),
            proveedor: String(_citasFindVal(row,['proveedor'])||'').trim(),
            franja_horaria_texto: String(_citasFindVal(row,['f. temporal','f.temporal','franja horaria','franja'])||'').trim(),
            // Campos ampliados en Fase 5.2 (paridad con cargar_archivo() de
            // citas-muelles-cedi-r10) -- todos opcionales: si no calzan con
            // ningún encabezado del archivo, el backend los guarda como NULL
            // sin descartar la fila (a diferencia de los 4 campos de arriba,
            // que sí son obligatorios para que la fila sea válida).
            proveedor_codigo: String(_citasFindVal(row,['proveedor_codigo','codigo proveedor','código proveedor','cod. proveedor','cod proveedor','numero de cuenta del proveedor','número de cuenta del proveedor'])||'').trim(),
            flujo: String(_citasFindVal(row,['flujo'])||'').trim(),
            descripcion_carga: String(_citasFindVal(row,['descripcion_carga','descripcion','descripción','descripcion carga','descripción carga','desc. carga'])||'').trim(),
            fecha_documento_compra: _citasNormalizarFecha(_citasFindVal(row,['fecha_documento_compra','fecha doc.','fecha doc','fecha documento compra','fecha docto','fecha documento'])),
            cantidad_pallets: String(_citasFindVal(row,['cantidad_pallets','ekko-yypal','ekko yypal','pallets','cantidad pallets','cantidad de pallets'])||'').trim(),
          };
        }).filter(r=>r.numero_orden_compra && r.proveedor);
        setCitasRows(parsed);
        if(parsed.length===0){
          setCitasErr('No se encontraron filas válidas. Revisa que el archivo tenga las columnas "O. Compra" (con un número de 10 dígitos que empiece en 4) y "Proveedor".');
        }
      }catch(ex){ setCitasErr('Error al leer archivo: '+ex.message); }
    };
    reader.readAsArrayBuffer(file);
    e.target.value='';
  };

  const handleCitasImport = async()=>{
    if(!citasRows.length) return setCitasErr('No hay datos para importar');
    setCitasLoading(true); setCitasErr(''); setCitasResult(null);
    try{
      const res = await api.post('/proveedores/citas/importar',{
        nombre_archivo:citasFileName,
        filas:citasRows,
      });
      setCitasResult(res);
      setCitasRows([]); setCitasFileN('');
      load(); // por si hay ordenes ya en pantalla que ahora pueden autocompletarse
      if(res.fechas?.includes(citasDiaFecha)) cargarCitasDia(); // refresca la lista si el import tocó la fecha que se está viendo
    }catch(ex){
      let m=ex.message||'Error'; try{m=JSON.parse(m).detail||m;}catch{}
      setCitasErr(m);
    }finally{ setCitasLoading(false); }
  };

  const empezarEditarCita = c => {
    setCitaEditId(c.id);
    setCitaEditForm({hora_cita_inicio:c.hora_cita_inicio||'',hora_cita_fin:c.hora_cita_fin||'',motivo:''});
    setCitaEditErr('');
  };
  const cancelarEditarCita = () => { setCitaEditId(null); setCitaEditErr(''); };
  const guardarEditarCita = async () => {
    setCitaEditSaving(true); setCitaEditErr('');
    try{
      await api.put(`/proveedores/citas/${citaEditId}`,citaEditForm);
      setCitaEditId(null);
      cargarCitasDia();
    }catch(ex){ setCitaEditErr(_textoErrorCita(ex)); }
    finally{ setCitaEditSaving(false); }
  };

  // Aviso no bloqueante: si el muelle digitado no coincide con el patrón
  // habitual observado para el tipo de carga (ver MUELLES_HABITUALES), se
  // avisa al guarda pero no se le impide continuar -- puede ser correcto
  // (ej. el muelle habitual está ocupado y lo reasignaron).
  const avisoMuelle = (() => {
    const rango = MUELLES_HABITUALES[vehiculoForm.tipo_carga];
    if(!rango) return null;
    const m = normalizarMuelle(vehiculoForm.muelle_descargue);
    if(m===null) return null;
    if(m>=rango[0] && m<=rango[1]) return null;
    return {muelle:m, tipo:vehiculoForm.tipo_carga, rango};
  })();

  /* ── VISTA: NUEVO INGRESO ── */
  if(view==='batch') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>{setView('list');setVehiculoForm(emptyVeh());setOrdenes([]);setOrdenDraft({...emptyOrd});setOrdenEditingIdx(null);setFrecuenteInfo(null);setCitaOrdenInfo(null);},style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,'Nuevo ingreso'),h('span',null,'Proveedores'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),

      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'truck',s:12}),' Datos del vehículo'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha',h('span',{className:'req'},'*')),h('input',{type:'date',value:vehiculoForm.fecha,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Hora ingreso',h('span',{className:'req'},'*')),h('input',{type:'time',value:vehiculoForm.hora_ingreso,readOnly:true,style:{background:'#f8fafc',cursor:'default'}}))
        ),
        // Documento/cédula primero (antes de Placa): dispara lookupConductor()
        // en el onBlur ANTES de que el guarda llene el resto de campos del
        // conductor, para que nombre/teléfono lleguen ya autocompletados si
        // es un conductor frecuente. Mismo criterio que el autorregistro QR
        // (pedido explícito de Karen para ambos formularios).
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},
            h('label',null,'Documento conductor',h('span',{className:'req'},'*')),
            h('div',{style:{display:'flex',gap:6}},
              h('select',{value:vehiculoForm.tipo_documento||'CC',onChange:e=>setVehiculoForm(p=>({...p,tipo_documento:e.target.value})),style:{flex:'0 0 80px'}},
                h('option',{value:'CC'},'CC'),h('option',{value:'NIT'},'NIT'),h('option',{value:'Otro'},'Otro')
              ),
              h('input',{type:'text',value:vehiculoForm.cedula_conductor,
                onChange:e=>{setVehiculoForm(p=>({...p,cedula_conductor:e.target.value}));setFrecuenteInfo(null);},
                onBlur:e=>lookupConductor(e.target.value,setVehiculoForm),
                placeholder:'Número',style:{flex:1}})
            ),
            frecuenteInfo&&h('div',{style:{marginTop:5,padding:'5px 9px',borderRadius:7,fontSize:11,fontWeight:700,display:'flex',alignItems:'center',gap:5,
              background:frecuenteInfo.estado==='encontrado'?'#d1fae5':frecuenteInfo.estado==='inactivo'?'#fef3c7':'#f1f5f9',
              color:frecuenteInfo.estado==='encontrado'?'#065f46':frecuenteInfo.estado==='inactivo'?'#92400e':'#475569',
              border:`1px solid ${frecuenteInfo.estado==='encontrado'?'#6ee7b7':frecuenteInfo.estado==='inactivo'?'#fcd34d':'#e2e8f0'}`}},
              h(Ico,{n:frecuenteInfo.estado==='encontrado'?'check':frecuenteInfo.estado==='inactivo'?'alert':'user',s:12}),
              frecuenteInfo.estado==='encontrado'?'Conductor frecuente — datos autocompletados':
              frecuenteInfo.estado==='inactivo'?'Conductor inactivo en el catálogo':'Conductor nuevo'
            )
          ),
          h('div',{className:'fg'},
            h('label',null,'Placa',h('span',{className:'req'},'*')),
            h('input',{type:'text',value:vehiculoForm.placa_vehiculo,onChange:e=>setVehiculoForm(p=>({...p,placa_vehiculo:e.target.value.toUpperCase()})),placeholder:'ABC-123',style:{textTransform:'uppercase'}})
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Nombre conductor',h('span',{className:'req'},'*')),h('input',{type:'text',value:vehiculoForm.nombre_conductor,onChange:e=>setVehiculoForm(p=>({...p,nombre_conductor:e.target.value})),onBlur:()=>setVehiculoForm(p=>({...p,nombre_conductor:capitalizarNombre(p.nombre_conductor)})),placeholder:'Se autocompleta o ingresa manual'})),
          h('div',{className:'fg'},h('label',null,'Teléfono conductor'),h('input',{type:'tel',value:vehiculoForm.telefono_conductor||'',onChange:e=>setVehiculoForm(p=>({...p,telefono_conductor:e.target.value})),placeholder:'Número de contacto (opcional)'}))
        ),
        h('div',{className:'fg'},h('label',null,'Tipo vehículo'),
          h('select',{value:vehiculoForm.tipo_vehiculo,onChange:e=>setVehiculoForm(p=>({...p,tipo_vehiculo:e.target.value}))},
            h('option',{value:''},'Seleccionar...'),...tiposVehiculo.map(t=>h('option',{key:t,value:t},t))
          )
        ),
        h('div',{className:'fg'},h('label',null,'Fecha pago ARL'),h('input',{type:'date',min:'2000-01-01',max:'2100-12-31',value:vehiculoForm.fecha_pago_arl,onChange:e=>{if(fechaValida(e.target.value))setVehiculoForm(p=>({...p,fecha_pago_arl:e.target.value}));}})),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Muelle descargue'),h('input',{type:'text',value:vehiculoForm.muelle_descargue,onChange:e=>setVehiculoForm(p=>({...p,muelle_descargue:e.target.value})),placeholder:'N° muelle (opcional)'})),
          h('div',{className:'fg'},h('label',null,'Hora de cita'),h('input',{type:'time',value:vehiculoForm.hora_cita||'',onChange:e=>setVehiculoForm(p=>({...p,hora_cita:e.target.value})),placeholder:'Opcional'}))
        ),
        avisoMuelle&&h('div',{style:{display:'flex',alignItems:'flex-start',gap:7,padding:'7px 9px',borderRadius:8,background:'#fef3c7',border:'1px solid #fcd34d',marginTop:4}},
          h(Ico,{n:'alert',s:13,style:{flexShrink:0,marginTop:1,color:'#b45309'}}),
          h('p',{style:{fontSize:11,fontWeight:500,color:'#92400e',lineHeight:1.45,margin:0}},
            h('span',{style:{fontWeight:700}},`Muelle ${avisoMuelle.muelle} fuera de lo habitual. `),
            `Carga ${avisoMuelle.tipo} suele ir en ${avisoMuelle.rango[0]}-${avisoMuelle.rango[1]}. Puedes continuar si el asignado es correcto.`
          )
        )
      ),

      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'checkCircle',s:12}),' Seguridad y carga'),
        h('div',{className:'fg'},h('label',null,'¿Cuenta con EPP?'),
          h('select',{value:vehiculoForm.epp_cumple===true?'si':vehiculoForm.epp_cumple===false?'no':'',onChange:e=>setVehiculoForm(p=>({...p,epp_cumple:e.target.value===''?'':e.target.value==='si'}))},
            h('option',{value:''},'—'),h('option',{value:'si'},'Sí'),h('option',{value:'no'},'No')
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Tipo de carga'),
            h('select',{value:vehiculoForm.tipo_carga||'',onChange:e=>setVehiculoForm(p=>({...p,tipo_carga:e.target.value}))},
              h('option',{value:''},'—'),...tiposCarga.map(t=>h('option',{key:t,value:t},t))
            )
          ),
          h('div',{className:'fg'},h('label',null,'Formato de carga'),
            h('select',{value:vehiculoForm.formato_carga||'',onChange:e=>{
              const v=e.target.value;
              setVehiculoForm(p=>({...p,formato_carga:v,cantidad_pallets:(v==='Granel'||v==='Mixta')?'No aplica':(p.cantidad_pallets==='No aplica'?'':p.cantidad_pallets)}));
            }},
              h('option',{value:''},'—'),...formatosCarga.map(t=>h('option',{key:t,value:t},t))
            )
          )
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Cantidad de pallets'),
            h('input',{type:'text',value:vehiculoForm.cantidad_pallets||'',readOnly:vehiculoForm.formato_carga==='Granel'||vehiculoForm.formato_carga==='Mixta',onChange:e=>setVehiculoForm(p=>({...p,cantidad_pallets:e.target.value})),placeholder:'Ej: 10',style:(vehiculoForm.formato_carga==='Granel'||vehiculoForm.formato_carga==='Mixta')?{background:'#f8fafc',cursor:'default'}:null})
          ),
          h('div',{className:'fg'},h('label',null,'Maneja la carga'),
            h('select',{value:vehiculoForm.manejo_carga||'',onChange:e=>setVehiculoForm(p=>({...p,manejo_carga:e.target.value}))},
              h('option',{value:''},'—'),...manejosCarga.map(t=>h('option',{key:t,value:t},t))
            )
          )
        ),
        h(LogisticaInversaField,{value:vehiculoForm.tipos_logistica_inversa,onChange:v=>setVehiculoForm(p=>({...p,tipos_logistica_inversa:v}))})
      ),

      h('div',{className:'fcard',style:{border:'1.5px solid var(--navy)'}},
        h('p',{className:'sec-ttl',style:{color:'var(--navy)'}},
          h(Ico,{n:'plus',s:12}),' ',ordenEditingIdx!==null?`Editar orden ${ordenEditingIdx+1}`:'Agregar proveedor'
        ),
        h('div',{className:'fg'},
          h('label',null,'Número de orden'),
          h('input',{type:'text',value:ordenDraft.numero_orden_compra||'',
            onChange:e=>{setOrdenDraft(p=>({...p,numero_orden_compra:e.target.value,cita_id:null}));setCitaOrdenInfo(null);},
            onBlur:e=>buscarCitaOrden(e.target.value),
            placeholder:'Como aparece en la reserva del WMS, ej. 4602898240 (opcional)'}),
          citaOrdenInfo?.estado==='encontrado'&&h('div',{style:{marginTop:5,padding:'5px 9px',borderRadius:7,fontSize:11,fontWeight:700,display:'flex',alignItems:'center',gap:5,background:'#d1fae5',color:'#065f46',border:'1px solid #6ee7b7'}},
            h(Ico,{n:'check',s:12}),'Cita encontrada — proveedor'+(citaOrdenInfo.hora?' y hora':'')+' autocompletados desde el archivo del día'
          ),
          citaOrdenInfo?.estado==='no_encontrado'&&h('div',{style:{marginTop:5,padding:'5px 9px',borderRadius:7,fontSize:11,color:'var(--slate)',display:'flex',alignItems:'center',gap:5}},
            h(Ico,{n:'alert',s:12}),'Sin cita registrada para este número — continúa llenando a mano'
          )
        ),
        h('div',{className:'fg'},
          h('label',null,'Empresa / Proveedor',h('span',{className:'req'},'*')),
          h('input',{type:'text',list:'bd-prov-batch',value:ordenDraft.empresa,onChange:e=>setOrdenDraft(p=>({...p,empresa:e.target.value})),placeholder:'Selecciona o escribe'}),
          h('datalist',{id:'bd-prov-batch'},bdProv.filter(p=>p.activo!==false).map(p=>h('option',{key:p.id,value:p.nombre})))
        ),
        h('div',{className:'fg'},h('label',null,'Carga compartida'),
          h('select',{value:ordenDraft.carga_compartida?'si':'no',onChange:e=>setOrdenDraft(p=>({...p,carga_compartida:e.target.value==='si'}))},
            h('option',{value:'no'},'No'),h('option',{value:'si'},'Sí')
          )
        ),
        h('div',{className:'fg'},h('label',null,'Actividad a desarrollar'),h('textarea',{value:ordenDraft.actividad_a_desarrollar,onChange:e=>setOrdenDraft(p=>({...p,actividad_a_desarrollar:e.target.value})),rows:2,placeholder:'Opcional'})),
        h('div',{className:'fg'},h('label',null,'Dependencia que autoriza'),h('input',{type:'text',value:ordenDraft.dependencia_autoriza,onChange:e=>setOrdenDraft(p=>({...p,dependencia_autoriza:e.target.value})),placeholder:'Opcional'})),
        h('button',{
          onClick:agregarOrden,
          style:{width:'100%',marginTop:8,background:'var(--navy)',border:'none',color:'#fff',borderRadius:8,padding:'10px 14px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:6,fontSize:13,fontWeight:700,fontFamily:'inherit'}
        },h(Ico,{n:ordenEditingIdx!==null?'save':'plus',s:15}),ordenEditingIdx!==null?'Actualizar proveedor':'+ Agregar a la lista')
      ),

      ordenes.length>0&&h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'package',s:12}),` Proveedores en este ingreso (${ordenes.length})`),
        ordenes.map((o,i)=>h('div',{key:i,style:{display:'flex',alignItems:'center',gap:8,padding:'8px 0',borderBottom:i<ordenes.length-1?'1px solid var(--border)':'none'}},
          h('div',{style:{flex:1,minWidth:0}},
            h('div',{style:{fontWeight:700,fontSize:13,color:'var(--text)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}},o.empresa||'Sin empresa'),
            h('div',{style:{fontSize:11,color:'var(--slate)',marginTop:1}},
              [o.actividad_a_desarrollar,o.carga_compartida&&'Carga compartida'].filter(Boolean).join(' · ')
            )
          ),
          h('div',{style:{display:'flex',gap:4,flexShrink:0}},
            h('button',{title:'Editar',onClick:()=>{setOrdenDraft({...o});setOrdenEditingIdx(i);},style:{background:'#dbeafe',border:'none',cursor:'pointer',color:'#1d4ed8',padding:'4px 8px',borderRadius:6,fontSize:11,fontWeight:700}},h(Ico,{n:'edit',s:12})),
            h('button',{title:'Quitar',onClick:()=>{setOrdenes(p=>p.filter((_,j)=>j!==i));if(ordenEditingIdx===i){setOrdenDraft({...emptyOrd});setOrdenEditingIdx(null);}},style:{background:'#fee2e2',border:'none',cursor:'pointer',color:'#dc2626',padding:'4px 8px',borderRadius:6,fontSize:11}},h(Ico,{n:'trash',s:12}))
          )
        ))
      ),

      ordenes.length===0&&h('div',{style:{textAlign:'center',padding:'16px 0',color:'var(--slate)',fontSize:12}},
        h(Ico,{n:'package',s:28,style:{opacity:.3,display:'block',margin:'0 auto 6px'}}),
        'Agrega al menos un proveedor arriba'
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setVehiculoForm(emptyVeh());setOrdenes([]);setOrdenDraft({...emptyOrd});setOrdenEditingIdx(null);setFrecuenteInfo(null);setCitaOrdenInfo(null);}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:guardarIngreso,disabled:saving||ordenes.length===0,style:{opacity:ordenes.length===0?.5:1}},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),
        saving?'Guardando...':ordenes.length>0?`Guardar ingreso (${ordenes.length} orden${ordenes.length>1?'es':''})`:'Guardar'
      )
    )
  );

  const nPorConfirmar = records.filter(r=>r.estado_confirmacion==='pendiente').length;
  const nDentro = records.filter(r=>r.estado_confirmacion==='confirmado'&&!r.hora_salida).length;
  const nIngresadosWps = records.filter(r=>r.estado_confirmacion==='ingresado_wps').length;
  const nCitasAtrasadas = citasAlertas.atrasadas.length;
  const nCitasTotal = citasAlertas.pendientes.length + citasAlertas.por_vencer.length + nCitasAtrasadas;
  const empresaDe = r => {
    const emps = (r.ordenes||[]).map(o=>o.empresa).filter(Boolean);
    return emps.length===0?(r.empresa||'Sin empresa'):emps.length<=2?emps.join(' · '):emps.slice(0,2).join(' · ')+` +${emps.length-2}`;
  };
  // Orden compuesto: fecha DESC (como ya viene del backend, agrupa por
  // día) y, dentro del mismo día, hora_cita ASC -- los que tienen cita más
  // temprano primero. Los registros sin hora_cita van al final de su día
  // sin romper el orden de los que sí la tienen. Se ordena ANTES de
  // filtrar para que todas las pestañas hereden el mismo orden.
  const cmpRecords = (a,b) => {
    if(a.fecha !== b.fecha) return a.fecha < b.fecha ? 1 : -1; // fecha DESC
    const ha = a.hora_cita || null, hb = b.hora_cita || null;
    if(ha && hb) return ha < hb ? -1 : ha > hb ? 1 : 0; // hora_cita ASC
    if(ha && !hb) return -1;
    if(!ha && hb) return 1;
    return 0;
  };
  const visibles = [...records]
    .sort(cmpRecords)
    .filter(r=>{
      if(filtro==='confirmar') return r.estado_confirmacion==='pendiente';
      if(filtro==='wps') return r.estado_confirmacion==='ingresado_wps';
      if(filtro==='dentro') return r.estado_confirmacion==='confirmado'&&!r.hora_salida;
      return true;
    })
    .filter(r=>{
      if(!busqueda.trim()) return true;
      const q=busqueda.trim().toLowerCase();
      const empStr=(r.ordenes||[]).map(o=>o.empresa||'').join(' ').toLowerCase();
      return empStr.includes(q)||
        (r.empresa&&r.empresa.toLowerCase().includes(q))||
        (r.nombre_conductor&&r.nombre_conductor.toLowerCase().includes(q))||
        (r.placa_vehiculo&&r.placa_vehiculo.toLowerCase().includes(q))||
        (r.cedula_conductor&&String(r.cedula_conductor).includes(q));
    });
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('div',{style:{display:'flex',gap:8,padding:'8px 14px 6px',flexWrap:'wrap'}},
        !esBodega&&!esCoordinador&&h('button',{onClick:()=>api.exportar('proveedores'),style:{background:'none',border:'1.5px solid var(--slate)',color:'var(--slate)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
          h(Ico,{n:'download',s:14}),' Excel'
        ),
        h('div',{style:{marginLeft:'auto',display:'flex',gap:6,alignItems:'center',minWidth:0,flexWrap:'wrap',justifyContent:'flex-end'}},
          h('button',{onClick:()=>setFiltro('confirmar'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='confirmar'?'#d97706':(nPorConfirmar>0?'#fef3c7':'transparent'),color:filtro==='confirmar'?'#fff':(nPorConfirmar>0?'#92400e':'var(--slate)'),borderColor:filtro==='confirmar'?'#d97706':(nPorConfirmar>0?'#fcd34d':'var(--border)')}},`🔔 Por confirmar (${nPorConfirmar})`),
          h('button',{onClick:()=>setFiltro('wps'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='wps'?'var(--navy)':'transparent',color:filtro==='wps'?'#fff':'var(--slate)',borderColor:filtro==='wps'?'var(--navy)':'var(--border)'}},`Ingresados WPS (${nIngresadosWps})`),
          h('button',{onClick:()=>setFiltro('dentro'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='dentro'?'var(--navy)':'transparent',color:filtro==='dentro'?'#fff':'var(--slate)',borderColor:filtro==='dentro'?'var(--navy)':'var(--border)'}},`En muelle (${nDentro})`),
          h('button',{onClick:()=>setFiltro('todos'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='todos'?'var(--navy)':'transparent',color:filtro==='todos'?'#fff':'var(--slate)',borderColor:filtro==='todos'?'var(--navy)':'var(--border)'}},`Todos (${records.length})`),
          /* Bodega no gestiona portería/llamadas a proveedores -- la pestaña
             no le sirve para nada, se oculta por completo. Coordinador sí la
             ve (acceso de solo lectura a todo el módulo) pero en modo
             puramente informativo: el botón de llamar se deshabilita más
             abajo, en el render de cada fila. */
          !esBodega&&h('button',{onClick:()=>setFiltro('citas'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:700,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:filtro==='citas'?'#dc2626':(nCitasAtrasadas>0?'#fee2e2':'transparent'),color:filtro==='citas'?'#fff':(nCitasAtrasadas>0?'#991b1b':'var(--slate)'),borderColor:filtro==='citas'?'#dc2626':(nCitasAtrasadas>0?'#fca5a5':'var(--border)')}},`📅 Con cita (${nCitasTotal})`)
        ),
        !esBodega&&!esCoordinador&&h('button',{onClick:()=>{setVehiculoForm(emptyVeh());setOrdenes([]);setOrdenDraft({...emptyOrd});setOrdenEditingIdx(null);setFrecuenteInfo(null);setCitaOrdenInfo(null);setView('batch');},style:{background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
          h(Ico,{n:'plus',s:15}),' Nuevo'
        ),
        !esBodega&&!esCoordinador&&h('button',{onClick:()=>setView('qr'),style:{background:'none',border:'1.5px solid var(--navy)',color:'var(--navy)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
          h(Ico,{n:'qrCode',s:14}),' QR Ingreso'
        ),
        !esBodega&&!esCoordinador&&h('button',{onClick:()=>{setCitasModal(true);setCitasTab('subir');setCitasRows([]);setCitasFileN('');setCitasResult(null);setCitasErr('');setCitaEditId(null);setCitaEditErr('');},title:'Subir el archivo de citas/reservas del día (WMS) para autocompletar el número de orden en el ingreso',style:{background:'none',border:'1.5px solid var(--navy)',color:'var(--navy)',borderRadius:8,padding:'7px 12px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:600,fontFamily:'inherit'}},
          h(Ico,{n:'calendar',s:14}),' Citas del día'
        ),
        esBodega&&h('p',{style:{fontSize:12,color:'var(--slate)',alignSelf:'center',margin:'0 0 0 4px'}},h(Ico,{n:'alert',s:12}),' Toca un registro para agregar evidencia de rechazo'),
        esCoordinador&&h('p',{style:{fontSize:12,color:'var(--slate)',alignSelf:'center',margin:'0 0 0 4px'}},'Solo lectura')
      ),
      h('div',{style:{padding:'0 14px 8px',position:'relative'}},
        h(Ico,{n:'search',s:14,style:{position:'absolute',left:24,top:'50%',transform:'translateY(-50%)',color:'var(--slate)',pointerEvents:'none'}}),
        h('input',{type:'text',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar empresa, conductor, cédula o placa...',style:{width:'100%',paddingLeft:30,fontSize:12,boxSizing:'border-box'}})
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      /* Pestaña "📅 Con cita": citas de hoy programadas (WMS) cuyo proveedor
         todavía no ha llegado (ver GET /proveedores/citas/alertas). Distinta
         a la pill "🔔 Llegó — Por confirmar" (esa es de un registro YA
         creado, esperando confirmación). Antes vivía en un banner fijo
         encima del listado; ahora es una pestaña más para no duplicar la
         misma información dos veces en pantalla. citasAlertas se carga por
         separado del fetch de `records`, así que no depende de `loading`.
         No es clickeable/navegable (no hay vehículo/placa/conductor todavía
         en una cita sin llegada): solo informa y, si el rol puede operar,
         ofrece el botón de llamar. */
      filtro==='citas'?(()=>{
        const atrasadas = [...citasAlertas.atrasadas].sort((a,b)=>b.minutos_atraso-a.minutos_atraso);
        const porVencer = [...citasAlertas.por_vencer].sort((a,b)=>a.minutos_restantes-b.minutos_restantes);
        // El backend ya entrega "pendientes" ordenado por hora_cita_inicio.
        const pendientes = citasAlertas.pendientes;
        const total = atrasadas.length+porVencer.length+pendientes.length;
        if(total===0) return h('div',{className:'empty'},h(Ico,{n:'calendar',s:44}),h('p',null,'Sin citas programadas pendientes de llegar hoy'));
        // esCoordinador tiene acceso de solo lectura a todo el módulo: ve la
        // pestaña pero sin botón de llamar activo (no le corresponde operar).
        const Fila = (c,tono)=>h('div',{key:tono+'-'+c.numero_orden_compra,style:{background:'var(--white)',borderRadius:10,padding:'10px 12px',marginBottom:8,display:'flex',alignItems:'center',flexWrap:'wrap',columnGap:10,rowGap:4,boxShadow:'0 1px 4px rgba(0,0,0,0.05)',border:'1px solid '+(tono==='at'?'#fecaca':tono==='pv'?'#fed7aa':'var(--border)')}},
          c.ya_registrado
            ?h('span',{style:{fontWeight:700,whiteSpace:'nowrap',padding:'2px 9px',borderRadius:20,fontSize:11,background:'#fef3c7',color:'#92400e',flexShrink:0}},'En portería · pendiente WPS')
            :h(Ico,{n:'phone',s:14,style:{color:tono==='at'?'#e11d48':tono==='pv'?'#c2650a':'var(--slate)',flexShrink:0}}),
          h('span',{style:{fontWeight:700,fontSize:13,color:'var(--text)'}},c.proveedor_nombre||'Sin nombre'),
          !c.ya_registrado&&c.telefono&&(esCoordinador
            ?h('span',{style:{color:'var(--slate)',fontSize:12}},c.telefono)
            :h('a',{href:'tel:'+c.telefono,style:{color:tono==='at'?'#e11d48':tono==='pv'?'#c2650a':'var(--navy)',fontWeight:600,fontSize:12,textDecoration:'underline'}},c.telefono)),
          h('span',{style:{color:'var(--slate)',fontSize:12}},`orden ${c.numero_orden_compra} · cita ${c.hora_cita_inicio}`),
          h('span',{style:{marginLeft:'auto',fontWeight:700,whiteSpace:'nowrap',padding:'2px 9px',borderRadius:20,fontSize:11,
              background:tono==='at'?'#fee2e2':tono==='pv'?'#ffedd5':'#f1f5f9',
              color:tono==='at'?'#991b1b':tono==='pv'?'#9a3412':'var(--slate)'}},
            tono==='at'?`Atrasado ${c.minutos_atraso} min`
              :tono==='pv'?(c.minutos_restantes>=0?`Cita en ${c.minutos_restantes} min`:`Cita vencida hace ${Math.abs(c.minutos_restantes)} min`)
              :`Hoy ${c.hora_cita_inicio}`
          )
        );
        return h(React.Fragment,null,
          atrasadas.map(c=>Fila(c,'at')),
          porVencer.map(c=>Fila(c,'pv')),
          pendientes.map(c=>Fila(c,'pd'))
        );
      })():
      loading?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:'package',s:44}),h('p',null,busqueda.trim()?'Sin resultados para "'+busqueda.trim()+'"':filtro==='confirmar'?'Nadie por confirmar en este momento':filtro==='dentro'?'Nadie dentro en este momento':'Sin proveedores')):
      (()=>{
        // Card compartida por todas las pestañas de lista (excepto "citas",
        // que tiene su propio render arriba). `citaOverride` trae el
        // borde/fondo de la tarjeta y el pill superior de "cita", que varían
        // según la pestaña:
        //  - pestañas normales (Todos/WPS/En muelle): countdown en vivo
        //    contra ahoraHora() -- comportamiento histórico, sin cambios.
        //  - pestaña "Por confirmar": agrupación por puntualidad real
        //    (hora_ingreso vs hora_cita), ver bloque más abajo.
        const cardFor = (r, citaOverride) => {
          const ords=r.ordenes||[];
          // Mismo criterio que backend/routers/muelles.py tablero() (SELECT
          // "empresas"): se agrupa por empresa y se listan sus OCs distintas
          // y no vacías entre paréntesis -- "Empresa (OC 111, OC 222)". Una
          // empresa sin ninguna OC capturada se muestra solo con el nombre,
          // sin paréntesis. Se arma aquí en el cliente (no hace falta tocar
          // el backend: r.ordenes ya trae numero_orden_compra por orden).
          const empGroups=[];
          const empIndex={};
          ords.forEach(o=>{
            const nombreEmp=o.empresa;
            if(!nombreEmp) return;
            if(!(nombreEmp in empIndex)){empIndex[nombreEmp]=empGroups.length;empGroups.push({empresa:nombreEmp,ocs:[]});}
            const oc=(o.numero_orden_compra||'').trim();
            if(oc && !empGroups[empIndex[nombreEmp]].ocs.includes(oc)) empGroups[empIndex[nombreEmp]].ocs.push(oc);
          });
          const emps=empGroups.map(g=>g.ocs.length?`${g.empresa} (${g.ocs.map(oc=>'OC '+oc).join(', ')})`:g.empresa);
          const empLabel=emps.length===0?(r.empresa||'Sin empresa'):emps.length<=2?emps.join(' · '):emps.slice(0,2).join(' · ')+` +${emps.length-2}`;
          const pendConf = r.estado_confirmacion==='pendiente';
          const enWps = r.estado_confirmacion==='ingresado_wps';
          const confMuelle = r.estado_confirmacion==='confirmado';
          const conSalida = !!r.hora_salida;
          const etapa = pendConf?{txt:'🔔 Llegó — Por confirmar',cls:'pill-amber'}
            :enWps?{txt:'Ingresado a WPS',cls:'pill-blue'}
            :conSalida?null
            :{txt:'Ingreso autorizado',cls:'pill-green'};
          return h('div',{key:r.id,className:'list-item',style:citaOverride.style},
            h('div',{className:'li-icon',style:{background:pendConf?'#fef3c7':'#fde68a'}},
              h(Ico,{n:pendConf?'bell':'package',s:18,style:{color:'#d97706'}})
            ),
            h('div',{className:'li-body',onClick:()=>{
              setForm({...emptyF,...r,cedula_conductor:r.cedula_conductor||'',hora_ingreso:r.hora_ingreso||'',hora_salida:r.hora_salida||''});
              setSelected(r);setFormOrdenes(r.ordenes||[]);setAddingOrd(false);setView('form');
            }},
              h('div',{style:{display:'flex',flexWrap:'wrap',alignItems:'center'}},
                citaOverride.pill,
                etapa&&h('span',{className:`pill ${etapa.cls}`,style:{marginBottom:3,display:'inline-block'}},etapa.txt),
                r.tipo_carga&&h(TipoCargaBadge,{tipo:r.tipo_carga,style:{marginLeft:6,marginBottom:3}})
              ),
              h('div',{className:'li-title'},r.nombre_conductor||r.placa_vehiculo||'Sin nombre'),
              h('div',{className:'li-sub'},
                [r.cedula_conductor&&('CC '+r.cedula_conductor),r.placa_vehiculo&&h('strong',{key:'placa',style:{fontWeight:700,color:'var(--text,#0f172a)'}},r.placa_vehiculo),r.tipo_vehiculo,r.muelle_descargue&&('Muelle '+r.muelle_descargue),r.telefono_conductor&&('📞 '+r.telefono_conductor)]
                  .filter(Boolean).reduce((acc,cur,i)=>i===0?[cur]:[...acc,' · ',cur],[])
              ),
              r.hora_cita&&h('div',{className:'li-sub'},'Cita: '+r.hora_cita.slice(0,5)),
              r.hora_ingreso&&h('div',{className:'li-sub'},'Hora de llegada '+r.hora_ingreso.slice(0,5)),
              h('div',{className:'li-sub'},empLabel),
              ords.length>1&&h('span',{style:{fontSize:10,background:'#dbeafe',color:'#1d4ed8',borderRadius:4,padding:'1px 6px',fontWeight:700,display:'inline-block',marginTop:2}},ords.length+' órdenes')
            ),
            h('div',{className:'li-right'},
              h('span',{className:'li-date'},fmtDate(r.fecha),
                r.fecha_salida&&r.fecha_salida!==r.fecha&&h('span',{style:{display:'block',fontSize:9,color:'#059669',fontWeight:600}},'Sale: '+fmtDate(r.fecha_salida))
              ),
              !esCoordinador&&h('div',{style:{display:'flex',gap:6,marginTop:3,alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}},
                !esBodega&&pendConf&&h('button',{
                  title:'Marcar ingreso a WPS',
                  onClick:(e)=>{e.stopPropagation();marcarWps(r.id);},
                  style:{background:'#1d4ed8',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700,display:'inline-flex',alignItems:'center',gap:3}
                },h(Ico,{n:'upload',s:11}),'Ingresado WPS'),
                !esBodega&&enWps&&h('button',{
                  title:'Confirmar ingreso',
                  onClick:(e)=>{e.stopPropagation();setMuelleSheet(r);},
                  style:{background:'#059669',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
                },'Confirmar'),
                // El botón se muestra siempre que el registro esté en WPS: el
                // guard real (estado + integridad de citas) lo aplica el backend
                // en /deshacer-wps, ya no hay ventana de tiempo.
                !esBodega&&enWps&&h('button',{
                  title:'Deshacer el ingreso a WPS marcado por error',
                  onClick:(e)=>{e.stopPropagation();setDeshacerWps(r);},
                  style:{background:'none',border:'1px solid #1d4ed8',cursor:'pointer',color:'#1d4ed8',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700,display:'inline-flex',alignItems:'center',gap:3}
                },h(Ico,{n:'undo',s:11}),'Deshacer'),
                !esBodega&&confMuelle&&r.hora_ingreso&&!r.hora_salida&&h('button',{
                  title:'Registrar salida',
                  onClick:(e)=>{e.stopPropagation();setSalida(r);setHoraSalida(ahoraHora());setFechaSalidaP(today());setFotoSalida(null);},
                  style:{background:'#d97706',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700}
                },'Salida'),
                // El botón se muestra siempre que el registro esté confirmado en
                // muelle: el guard real (estado + salida + logística inversa) lo
                // aplica el backend en /deshacer-confirmacion.
                !esBodega&&confMuelle&&r.hora_ingreso&&!r.hora_salida&&h('button',{
                  title:'Deshacer la confirmación de muelle hecha por error',
                  onClick:(e)=>{e.stopPropagation();setDeshacerConf(r);},
                  style:{background:'none',border:'1px solid #1d4ed8',cursor:'pointer',color:'#1d4ed8',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700,display:'inline-flex',alignItems:'center',gap:3}
                },h(Ico,{n:'undo',s:11}),'Deshacer'),
                puede(user,'muelles','liberar')&&confMuelle&&r.muelle_descargue&&!r.hora_salida&&h('button',{
                  title:'Liberar muelle',
                  onClick:(e)=>{e.stopPropagation();setLiberarMuelle(r);},
                  style:{background:'var(--purple)',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700,display:'inline-flex',alignItems:'center',gap:3}
                },h(Ico,{n:'truck',s:11}),' Liberar muelle'),
                puede(user,'muelles','liberar')&&confMuelle&&!r.hora_salida&&!r.muelle_logistica_inversa
                  &&Array.isArray(r.tipos_logistica_inversa)&&r.tipos_logistica_inversa.length>0&&h('button',{
                  title:'Enviar a logística inversa',
                  onClick:(e)=>{e.stopPropagation();setMuelleInversaSheet(r);},
                  style:{background:'var(--navy2)',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700,display:'inline-flex',alignItems:'center',gap:3}
                },h(Ico,{n:'package',s:11}),' Enviar a logística inversa'),
                puede(user,'muelles','liberar')&&!!r.muelle_logistica_inversa&&h('button',{
                  title:'Liberar muelle de logística inversa',
                  onClick:(e)=>{e.stopPropagation();setLiberarMuelleInversa(r);},
                  style:{background:'var(--navy3)',border:'none',cursor:'pointer',color:'#fff',padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:700,display:'inline-flex',alignItems:'center',gap:3}
                },h(Ico,{n:'truck',s:11}),' Liberar muelle inversa'),
                r.tipos_logistica_inversa&&h(LogisticaInversaBadge,{tipos:r.tipos_logistica_inversa}),
                (esBodega||esVehicular)&&(r.observaciones||r.foto_url)&&h('span',{style:{fontSize:10,background:'#fef3c7',color:'#92400e',borderRadius:4,padding:'2px 6px',fontWeight:600}},'Con observación'),
                !esBodega&&h('button',{title:'Eliminar',onClick:(e)=>{e.stopPropagation();setConfirm(r.id);},className:'li-act li-act-danger'},h(Ico,{n:'trash',s:14}))
              )
            )
          );
        };

        if(filtro==='confirmar'){
          // Agrupación por puntualidad (spec Laura, tolerancia 5 min).
          // atrasoMin se calcula con hora_ingreso REAL (llegada a portería
          // registrada), no con el countdown en vivo que usan las demás
          // pestañas -- así el orden no cambia solo porque pasa el tiempo
          // mientras el guarda mira la pantalla.
          const atrasados=[], aTiempo=[], sinCita=[], proximos=[];
          const [ahC,amC]=ahoraHora().split(':').map(Number);
          const ahoraMinC=ahC*60+amC;
          visibles.forEach(r=>{
            if(!r.hora_cita){ sinCita.push({r,atrasoMin:null}); return; }
            const [ch,cm]=r.hora_cita.split(':').map(Number);
            const citaMin=ch*60+cm;
            if(!r.hora_ingreso){
              // Aún no llega a portería. Si la cita ya venció, es el mismo caso que
              // dispara el aviso sonoro cada 7 min (avisadosAtraso, ~línea 3296,
              // diff<0) -- debe verse tan urgente como quien sí llegó tarde, no
              // perderse dentro de "SIN CITA REGISTRADA". Si la cita aún no vence,
              // sigue siendo sinCita (caso sin resolver todavía, no es error).
              // Si la cita aún no vence pero está a <=60 min (mismo umbral que
              // citaAlerta, ~línea 4358), es el aviso preventivo "regístrate a
              // WPS antes de tu cita" -- no debe perderse en sinCita.
              if(ahoraMinC-citaMin>0){ atrasados.push({r,atrasoMin:ahoraMinC-citaMin,sinLlegar:true}); }
              else if(citaMin-ahoraMinC<=60){ proximos.push({r,atrasoMin:null,diff:citaMin-ahoraMinC}); }
              else{ sinCita.push({r,atrasoMin:null}); }
              return;
            }
            const [ih,im]=r.hora_ingreso.split(':').map(Number);
            const atrasoMin=(ih*60+im)-citaMin;
            (atrasoMin>5?atrasados:aTiempo).push({r,atrasoMin});
          });
          const porHoraIngreso=(a,b)=>a.r.hora_ingreso<b.r.hora_ingreso?-1:a.r.hora_ingreso>b.r.hora_ingreso?1:0;
          // Dentro de atrasados: quien todavía no llega (sinLlegar) primero -- sigue
          // sonando la alerta cada 7 min, es lo más urgente que el guarda puede
          // resolver; entre ellos, mayor atraso primero. Quien ya llegó tarde
          // (evento resuelto, solo falta confirmar) va después, como antes.
          const porUrgenciaAtrasados=(a,b)=>{
            if(a.sinLlegar&&b.sinLlegar) return b.atrasoMin-a.atrasoMin;
            if(a.sinLlegar) return -1;
            if(b.sinLlegar) return 1;
            return porHoraIngreso(a,b);
          };
          atrasados.sort(porUrgenciaAtrasados);
          // Dentro de proximos: menor diff primero -- la cita más próxima a
          // vencer es la más urgente de confirmar/registrar.
          proximos.sort((a,b)=>a.diff-b.diff);
          aTiempo.sort(porHoraIngreso);
          sinCita.sort(porHoraIngreso);
          const grupoHeader = (tipo,count,esPrimero) => {
            const cfg = {
              atrasados:{bg:'#fee2e2',border:'#fca5a5',icon:'alert',iconColor:'#991b1b',label:'ATRASADOS POR INCUMPLIMIENTO DE CITA',textColor:'#991b1b',pillBg:'#fecaca'},
              proximos:{bg:'#fef2f2',border:'#fecaca',icon:'alert',iconColor:'#b91c1c',label:'PRÓXIMOS A VENCER',textColor:'#b91c1c',pillBg:'#fee2e2'},
              aTiempo:{bg:'#d1fae5',border:'#6ee7b7',icon:'checkCircle',iconColor:'#065f46',label:'A TIEMPO',textColor:'#065f46',pillBg:'#a7f3d0'},
              sinCita:{bg:'#f1f5f9',border:'var(--border)',icon:'clipboard',iconColor:'var(--slate)',label:'SIN CITA REGISTRADA',textColor:'var(--slate)',pillBg:'#e2e8f0'}
            }[tipo];
            return h('div',{key:'grupo-'+tipo,style:{padding:'6px 10px',borderRadius:8,display:'flex',alignItems:'center',gap:8,background:cfg.bg,border:'1px solid '+cfg.border,marginTop:esPrimero?0:16,marginBottom:8}},
              h('span',{style:{color:cfg.iconColor,display:'inline-flex'}},h(Ico,{n:cfg.icon,s:14})),
              h('span',{style:{fontSize:12,fontWeight:800,color:cfg.textColor,textTransform:'uppercase',letterSpacing:.3}},cfg.label),
              h('span',{style:{marginLeft:'auto',background:cfg.pillBg,color:cfg.textColor,borderRadius:20,padding:'1px 8px',fontSize:11,fontWeight:700}},String(count))
            );
          };
          const cardConfirmar = ({r,atrasoMin,sinLlegar,diff},tipo) => {
            const style = tipo==='atrasados'||tipo==='proximos'
              ?{border:'1.5px solid #f87171',background:'#fef2f2'}
              :{border:'1.5px solid #fcd34d',background:'#fffbeb'};
            const pill = tipo==='atrasados'
              ?(sinLlegar
                ?h('span',{className:'pill pill-red cita-blink',style:{marginBottom:3,marginRight:4,display:'inline-block',fontSize:11,fontWeight:700,padding:'3px 9px'}},`⏰ Cita atrasada — aún no llega (${atrasoMin} min)`)
                :h('span',{className:'pill pill-red',style:{marginBottom:3,marginRight:4,display:'inline-block',fontSize:11,fontWeight:700,padding:'3px 9px'}},`Llegó tarde a su cita — ${atrasoMin} min de atraso`))
              :tipo==='proximos'
                ?h('span',{className:'pill',style:{marginBottom:3,marginRight:4,display:'inline-block',fontSize:11,fontWeight:700,padding:'3px 9px',background:'#fee2e2',color:'#991b1b',border:'1px solid #fca5a5'}},`⏰ Cita en ${diff} min`)
                :tipo==='aTiempo'
                  ?h('span',{className:'pill pill-green',style:{marginBottom:3,marginRight:4,display:'inline-block',fontSize:11,fontWeight:700,padding:'3px 9px'}},'Llegó a tiempo a su cita')
                  :null;
            return cardFor(r,{style,pill});
          };
          let huboEncabezado=false;
          const bloques=[];
          if(atrasados.length){ bloques.push(grupoHeader('atrasados',atrasados.length,!huboEncabezado)); huboEncabezado=true; atrasados.forEach(item=>bloques.push(cardConfirmar(item,'atrasados'))); }
          if(proximos.length){ bloques.push(grupoHeader('proximos',proximos.length,!huboEncabezado)); huboEncabezado=true; proximos.forEach(item=>bloques.push(cardConfirmar(item,'proximos'))); }
          if(aTiempo.length){ bloques.push(grupoHeader('aTiempo',aTiempo.length,!huboEncabezado)); huboEncabezado=true; aTiempo.forEach(item=>bloques.push(cardConfirmar(item,'aTiempo'))); }
          if(sinCita.length){ bloques.push(grupoHeader('sinCita',sinCita.length,!huboEncabezado)); huboEncabezado=true; sinCita.forEach(item=>bloques.push(cardConfirmar(item,'sinCita'))); }
          return h(React.Fragment,null,bloques);
        }

        return visibles.map(r=>{
          const pendConf = r.estado_confirmacion==='pendiente';
          // Alerta cuando falta 1h o menos para la hora de cita que dio el
          // conductor y el vehiculo todavia no ha pasado a WPS (estado_confirmacion
          // sigue en 'pendiente'). Se mantiene activa aunque la hora ya haya
          // pasado (diff negativo): sigue sin confirmarse, sigue alertando.
          const citaAlerta = (pendConf && r.hora_cita) ? (()=>{
            const [ch,cm] = r.hora_cita.split(':').map(Number);
            const [ah,am] = ahoraHora().split(':').map(Number);
            const diff = (ch*60+cm) - (ah*60+am);
            return diff<=60 ? {diff} : null;
          })() : null;
          const citaProxima = !!citaAlerta;
          return cardFor(r,{
            style: citaProxima?{border:'1.5px solid #f87171',background:'#fef2f2'}:pendConf?{border:'1.5px solid #fcd34d',background:'#fffbeb'}:null,
            pill: citaAlerta&&h('span',{className:'pill'+(citaAlerta.diff<0?' cita-blink':''),style:{marginBottom:3,marginRight:4,display:'inline-block',background:'#fee2e2',color:'#991b1b',border:'1px solid #fca5a5'}},citaAlerta.diff>=0?`⏰ Cita en ${citaAlerta.diff} min`:`⏰ Cita atrasada ${Math.abs(citaAlerta.diff)} min`)
          });
        });
      })()
    ),
    salida&&h('div',{className:'overlay',onClick:()=>setSalida(null)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'Registrar salida'),
          h('button',{className:'btn-icon',onClick:()=>setSalida(null)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:13,color:'var(--slate)',marginBottom:4}},
          (salida.nombre_conductor||salida.placa_vehiculo)+(
            (salida.ordenes||[]).map(o=>o.empresa).filter(Boolean).length>0
              ?' · '+(salida.ordenes||[]).map(o=>o.empresa).filter(Boolean).join(', ')
              :(salida.empresa?' · '+salida.empresa:'')
          )
        ),
        (salida.ordenes||[]).length>1&&h('p',{style:{fontSize:11,color:'#059669',marginBottom:8,fontWeight:600}},
          '✓ Se registra salida de '+(salida.ordenes||[]).length+' orden(es) simultáneamente'
        ),
        (salida.observaciones||salida.foto_url)&&h('div',{style:{background:'#fef3c7',border:'1px solid #fcd34d',borderRadius:8,padding:'8px 10px',marginBottom:10}},
          h('p',{style:{fontSize:11,fontWeight:700,color:'#92400e',marginBottom:4}},h(Ico,{n:'alert',s:11}),' Observación de bodega'),
          salida.observaciones&&h('p',{style:{fontSize:12,color:'#78350f',whiteSpace:'pre-wrap'}},salida.observaciones),
          salida.foto_url&&h('img',{src:salida.foto_url,style:{maxWidth:'100%',borderRadius:6,marginTop:6}})
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Fecha de salida'),h('input',{type:'date',value:fechaSalidaP,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Hora de salida'),h('input',{type:'time',value:horaSalida,readOnly:true,style:{background:'#f8fafc',cursor:'default'}}))
        ),
        h('div',{className:'fg'},
          h('label',null,'Foto (opcional)'),
          h(CameraField,{value:fotoSalida,onChange:setFotoSalida})
        ),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          h('button',{className:'btn-cancel',onClick:()=>{setSalida(null);setFotoSalida(null);},disabled:saving},'Cancelar'),
          h('button',{className:'btn-primary',style:{background:'#d97706'},disabled:saving,onClick:async()=>{
            setSaving(true);
            try{
              const ts=await _tsBog();const upd={hora_salida:ts.hora,fecha_salida:ts.fecha};
              if(fotoSalida) upd.foto_url=fotoSalida;
              await api.put(`/proveedores/${salida.id}`,upd);
              setSalida(null);setFotoSalida(null);load();setAlert({type:'ok',msg:'Salida registrada'});
            }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
            finally{setSaving(false);}
          }},saving?h('div',{className:'spinner'}):h(Ico,{n:'check',s:16}),saving?'Guardando...':'Confirmar salida')
        )
      )
    ),
    confirm&&h(ConfirmSheet,{msg:'Se eliminará el ingreso de proveedor y todas sus órdenes.',onOk:async()=>{await api.del(`/proveedores/${confirm}`);setConfirm(null);load();setAlert({type:'ok',msg:'Eliminado'});},onCancel:()=>setConfirm(null)}),
    liberarMuelle&&h(ConfirmSheet,{
      icon:'truck',
      titulo:`¿Liberar el muelle ${liberarMuelle.muelle_descargue}?`,
      textoOk:'Liberar muelle',
      colorOk:'var(--purple)',
      msg:`El vehículo ${liberarMuelle.placa_vehiculo||''} dejará de ocupar el muelle ${liberarMuelle.muelle_descargue}. Esto libera el espacio para el panel de disponibilidad, pero NO registra la salida del vehículo del CEDI.`,
      onOk:async()=>{
        try{
          await api.put(`/proveedores/${liberarMuelle.id}/liberar-muelle`,{});
          setLiberarMuelle(null); load(); setAlert({type:'ok',msg:'Muelle liberado'});
        }catch(e){
          setLiberarMuelle(null); load();
          setAlert({type:'err',msg:'Error: '+e.message});
        }
      },
      onCancel:()=>setLiberarMuelle(null)
    }),
    deshacerWps&&h(ConfirmSheet,{
      icon:'undo',
      titulo:'¿Deshacer el ingreso a WPS?',
      textoOk:'Deshacer',
      colorOk:'#1d4ed8',
      msg:`El registro de ${deshacerWps.nombre_conductor||deshacerWps.placa_vehiculo||'este vehículo'} volverá a "Por confirmar", como si todavía no se hubiera marcado el ingreso a WPS. Úsalo solo si el registro anterior fue un error.`,
      onOk:async()=>{
        try{
          await api.put(`/proveedores/${deshacerWps.id}/deshacer-wps`,{});
          setDeshacerWps(null); load(); setAlert({type:'ok',msg:'Ingreso a WPS deshecho'});
        }catch(e){
          setDeshacerWps(null); load();
          setAlert({type:'err',msg:_textoErrorCita(e)});
        }
      },
      onCancel:()=>setDeshacerWps(null)
    }),
    deshacerConf&&h(ConfirmSheet,{
      icon:'undo',
      titulo:'¿Deshacer la confirmación de muelle?',
      textoOk:'Deshacer',
      colorOk:'#1d4ed8',
      msg:`El registro de ${deshacerConf.nombre_conductor||deshacerConf.placa_vehiculo||'este vehículo'} volverá a "Ingresado WPS" y quedará libre el muelle ${deshacerConf.muelle_descargue||''}. Úsalo solo si el muelle o la confirmación fueron un error.`,
      onOk:async()=>{
        try{
          await api.put(`/proveedores/${deshacerConf.id}/deshacer-confirmacion`,{});
          setDeshacerConf(null); load(); setAlert({type:'ok',msg:'Confirmación de muelle deshecha'});
        }catch(e){
          setDeshacerConf(null); load();
          setAlert({type:'err',msg:_textoErrorCita(e)});
        }
      },
      onCancel:()=>setDeshacerConf(null)
    }),
    muelleSheet&&h(ConfirmarMuelleSheet,{
      registro:muelleSheet,
      onClose:()=>setMuelleSheet(null),
      onElegirMuelle:async(numero)=>{ await confirmarIngreso(muelleSheet.id,numero); setMuelleSheet(null); },
      onSinMuelle:async()=>{ await confirmarIngreso(muelleSheet.id); setMuelleSheet(null); }
    }),
    muelleInversaSheet&&h(ConfirmarMuelleSheet,{
      registro:muelleInversaSheet,
      endpoint:'/muelles/logistica-inversa',
      titulo:'Elegir muelle de logística inversa',
      ocultarSinMuelle:true,
      onClose:()=>setMuelleInversaSheet(null),
      onElegirMuelle:async(numero)=>{
        try{
          await api.put(`/proveedores/${muelleInversaSheet.id}/asignar-muelle-inversa`,{muelle:numero});
          setMuelleInversaSheet(null); load(); setAlert({type:'ok',msg:`Enviado a logística inversa — muelle ${numero}`});
        }catch(e){
          setMuelleInversaSheet(null); load();
          setAlert({type:'err',msg:'Error: '+e.message});
        }
      },
      onSinMuelle:()=>{} // no aplica en este modo, ocultarSinMuelle:true ya quita el botón que lo dispararía
    }),
    liberarMuelleInversa&&h(ConfirmSheet,{
      icon:'truck',
      titulo:`¿Liberar el muelle de logística inversa ${liberarMuelleInversa.muelle_logistica_inversa}?`,
      textoOk:'Liberar muelle',
      colorOk:'var(--navy3)',
      msg:`El vehículo ${liberarMuelleInversa.placa_vehiculo||''} dejará de ocupar el muelle ${liberarMuelleInversa.muelle_logistica_inversa} de logística inversa.`,
      onOk:async()=>{
        try{
          await api.put(`/proveedores/${liberarMuelleInversa.id}/liberar-muelle-inversa`,{});
          setLiberarMuelleInversa(null); load(); setAlert({type:'ok',msg:'Muelle de logística inversa liberado'});
        }catch(e){
          setLiberarMuelleInversa(null); load();
          setAlert({type:'err',msg:'Error: '+e.message});
        }
      },
      onCancel:()=>setLiberarMuelleInversa(null)
    }),
    saveFrModal&&h('div',{className:'overlay',onClick:()=>setSaveFrModal(false)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'¿Guardar como conductor frecuente?'),
          h('button',{className:'btn-icon',onClick:()=>setSaveFrModal(false)},h(Ico,{n:'x',s:16}))
        ),
        h('p',{style:{fontSize:12,color:'var(--slate)',marginBottom:12}},'Guarda los datos para agilizar futuros ingresos de este conductor.'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Cédula'),h('input',{type:'text',value:frDraft.cedula,readOnly:true,style:{background:'#f8fafc',cursor:'default'}})),
          h('div',{className:'fg'},h('label',null,'Nombre'),h('input',{type:'text',value:frDraft.nombre_conductor,onChange:e=>setFrDraft(p=>({...p,nombre_conductor:e.target.value})),onBlur:()=>setFrDraft(p=>({...p,nombre_conductor:capitalizarNombre(p.nombre_conductor)})),placeholder:'Nombre conductor'}))
        ),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Empresa principal'),h('input',{type:'text',value:frDraft.empresa_principal,onChange:e=>setFrDraft(p=>({...p,empresa_principal:e.target.value})),placeholder:'Empresa habitual'})),
          h('div',{className:'fg'},h('label',null,'Tipo vehículo'),
            h('select',{value:frDraft.tipo_vehiculo,onChange:e=>setFrDraft(p=>({...p,tipo_vehiculo:e.target.value}))},
              h('option',{value:''},'Seleccionar...'),...tiposVehiculo.map(t=>h('option',{key:t,value:t},t))
            )
          )
        ),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          h('button',{className:'btn-cancel',onClick:()=>setSaveFrModal(false)},'Omitir'),
          h('button',{className:'btn-primary',onClick:async()=>{
            try{
              const ts=await _tsBog();
              await api.post('/maestros/conductores-frecuentes',{...frDraft,ultima_visita:ts.fecha});
              setSaveFrModal(false);setAlert({type:'ok',msg:'Conductor guardado en catálogo de frecuentes'});
            }catch(e){setSaveFrModal(false);setAlert({type:'err',msg:'No se pudo guardar como frecuente'});}
          }},h(Ico,{n:'save',s:16}),' Guardar en catálogo')
        )
      )
    ),
    citasModal&&h('div',{className:'overlay',onClick:()=>setCitasModal(false)},
      h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
        h('div',{className:'sheet-header'},
          h('span',{style:{fontWeight:700,fontSize:15}},'Citas del día (WMS)'),
          h('button',{className:'btn-icon',onClick:()=>setCitasModal(false)},h(Ico,{n:'x',s:16}))
        ),

        /* Dos tareas con intención y frecuencia distintas dentro del mismo
           modal: subir el archivo es un lote (una vez en la mañana, o cuando
           llega un nuevo export), editar una hora es puntual y puede pasar
           en cualquier momento del turno. Separarlas en pestañas evita que
           el guarda tenga que hacer scroll pasando la zona de carga cada vez
           que solo necesita corregir una cita. */
        h('div',{style:{display:'flex',gap:6,marginBottom:14}},
          h('button',{onClick:()=>setCitasTab('subir'),style:{flex:1,display:'flex',alignItems:'center',justifyContent:'center',gap:5,padding:'8px 10px',borderRadius:8,fontSize:12,fontWeight:700,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:citasTab==='subir'?'var(--navy)':'transparent',color:citasTab==='subir'?'#fff':'var(--slate)',borderColor:citasTab==='subir'?'var(--navy)':'var(--border)'}},
            h(Ico,{n:'upload',s:13}),'Subir archivo'
          ),
          h('button',{onClick:()=>setCitasTab('ver'),style:{flex:1,display:'flex',alignItems:'center',justifyContent:'center',gap:5,padding:'8px 10px',borderRadius:8,fontSize:12,fontWeight:700,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:citasTab==='ver'?'var(--navy)':'transparent',color:citasTab==='ver'?'#fff':'var(--slate)',borderColor:citasTab==='ver'?'var(--navy)':'var(--border)'}},
            h(Ico,{n:'calendar',s:13}),'Ver / editar horas'
          )
        ),

        citasTab==='subir'&&h(React.Fragment,null,
          h('p',{style:{fontSize:12,color:'var(--slate)',marginBottom:12}},
            'Sube el export de reservas del WMS ("Plano_Reservas_de_Recepción") para autocompletar el proveedor y la hora de cita al escribir el número de orden en un nuevo ingreso. La fecha de cada cita se toma de la columna "Fecha Ejec." del archivo (puede traer varios días); se reemplazan las citas cargadas previamente para cada fecha que aparezca.'
          ),
          h('label',{className:'upload-zone',style:{marginBottom:10}},
            h('input',{type:'file',accept:'.xlsx,.xls,.csv',style:{display:'none'},onChange:handleCitasFile}),
            h(Ico,{n:'upload',s:24,c:'upload-ico'}),
            h('p',null, citasFileName||'Toca para seleccionar el archivo'),
            h('span',null,'.xlsx · .xls · .csv')
          ),
          citasErr&&h('div',{className:'alert-err',style:{marginBottom:10}},h(Ico,{n:'alert',s:14}),citasErr),
          citasRows.length>0&&h('div',{style:{marginBottom:10}},
            h('p',{style:{fontSize:12,fontWeight:700,color:'var(--text)',marginBottom:6}},`${citasRows.length} citas listas para importar`),
            h('div',{style:{overflowX:'auto',maxHeight:180,overflowY:'auto',border:'1px solid var(--border)',borderRadius:8}},
              h('table',{className:'preview-table'},
                h('thead',null,h('tr',null,h('th',null,'Fecha'),h('th',null,'O. Compra'),h('th',null,'Proveedor'),h('th',null,'F. Temporal'))),
                h('tbody',null,
                  citasRows.slice(0,8).map((r,i)=>h('tr',{key:i},h('td',null,r.fecha||'—'),h('td',null,r.numero_orden_compra),h('td',null,r.proveedor),h('td',null,r.franja_horaria_texto||'—')))
                )
              )
            ),
            citasRows.length>8&&h('p',{style:{fontSize:10,color:'var(--slate)',marginTop:4}},`...y ${citasRows.length-8} más`)
          ),
          citasResult&&h('div',{style:{background:'#f0fdf4',border:'1px solid #bbf7d0',borderRadius:8,padding:'8px 10px',marginBottom:10}},
            h('p',{style:{fontSize:12,color:'#166534',fontWeight:700}},`${citasResult.insertados} citas cargadas`+(citasResult.fechas?.length?` para ${citasResult.fechas.join(', ')}`:'')),
            citasResult.errores?.length>0&&h('div',{style:{marginTop:6}},
              citasResult.errores.slice(0,5).map((e,i)=>h('p',{key:i,style:{fontSize:11,color:'var(--red)'}},`Fila ${e.fila}: ${e.error}`)),
              citasResult.errores.length>5&&h('p',{style:{fontSize:10,color:'var(--slate)'}},`...y ${citasResult.errores.length-5} errores más`)
            )
          ),
          h('div',{style:{display:'flex',gap:8,marginTop:4}},
            h('button',{className:'btn-cancel',onClick:()=>setCitasModal(false),disabled:citasLoading},'Cerrar'),
            h('button',{className:'btn-primary',style:{flex:1},onClick:handleCitasImport,disabled:citasLoading||citasRows.length===0},
              citasLoading?h('div',{className:'spinner'}):h(Ico,{n:'upload',s:15}),
              citasLoading?'Importando...':`Importar ${citasRows.length||''} citas`
            )
          )
        ),

        citasTab==='ver'&&h(React.Fragment,null,
          h('p',{style:{fontSize:12,color:'var(--slate)',marginBottom:12}},
            'Consulta las citas ya cargadas de un día y corrige puntualmente la hora de una si se autorizó un cambio por fuera del WMS (llamada o correo con el proveedor). El motivo queda guardado junto con tu usuario, como respaldo de quién autorizó el cambio.'
          ),
          h('div',{style:{display:'flex',gap:8,alignItems:'flex-end',marginBottom:10}},
            h('div',{className:'fg',style:{flex:1,marginBottom:0}},
              h('label',null,'Fecha'),
              h('input',{type:'date',value:citasDiaFecha,onChange:e=>{setCitasDiaFecha(e.target.value);setCitaEditId(null);}})
            ),
            h('button',{className:'btn-cancel',onClick:cargarCitasDia,disabled:citasDiaLoading,style:{padding:'0 14px',fontSize:11,height:38}},citasDiaLoading?'Cargando...':'Actualizar')
          ),
          citasDiaErr&&h('div',{className:'alert-err',style:{marginBottom:10}},h(Ico,{n:'alert',s:14}),citasDiaErr),

          citasDiaLoading&&h(LoadingDots),

          !citasDiaLoading&&citasDiaItems.length===0&&!citasDiaErr&&h('div',{style:{textAlign:'center',padding:'20px 10px',color:'var(--slate)'}},
            h(Ico,{n:'calendar',s:28,style:{opacity:.35,display:'block',margin:'0 auto 6px'}}),
            h('p',{style:{fontSize:12}},'Sin citas guardadas para esta fecha.')
          ),

          !citasDiaLoading&&citasDiaItems.length>0&&h('div',{style:{maxHeight:340,overflowY:'auto',display:'flex',flexDirection:'column',gap:8}},
            citasDiaItems.map(c=>{
              const editing = citaEditId===c.id;
              const bloqueada = !!c.tiene_llegada;
              const motivoOk = citaEditForm.motivo.trim().length>=5;
              const horasOk = !!citaEditForm.hora_cita_inicio && !!citaEditForm.hora_cita_fin && citaEditForm.hora_cita_inicio<citaEditForm.hora_cita_fin;
              return h('div',{key:c.id,style:{border:'1.5px solid '+(editing?'var(--amber)':'var(--border)'),borderRadius:10,padding:'10px 12px',background:editing?'#fffbeb':'#fff'}},
                h('div',{style:{display:'flex',justifyContent:'space-between',gap:8,alignItems:'flex-start'}},
                  h('div',{style:{minWidth:0}},
                    h('div',{style:{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap',marginBottom:3}},
                      h('span',{style:{fontWeight:700,fontSize:13,color:'var(--text)'}}, `${c.hora_cita_inicio||'—'} – ${c.hora_cita_fin||'—'}`),
                      c.hora_editada_manualmente&&h('span',{className:'pill pill-amber',title:'Esta hora fue corregida manualmente y no viene tal cual del archivo del WMS',style:{display:'inline-flex',alignItems:'center',gap:3}},h(Ico,{n:'edit',s:9}),'Editada'),
                      c.tiene_llegada&&h('span',{className:'pill pill-green',title:'El proveedor ya se presentó para esta orden',style:{display:'inline-flex',alignItems:'center',gap:3}},h(Ico,{n:'check',s:9}),'Llegó')
                    ),
                    h('div',{style:{fontSize:12,fontWeight:600,color:'var(--text2)'}}, c.proveedor_nombre||'Sin nombre'),
                    h('div',{style:{fontSize:11,color:'var(--slate)'}}, 'O.C. '+c.numero_orden_compra)
                  ),
                  !editing&&(bloqueada
                    ? h('div',{title:'No editable: el proveedor ya registró su llegada para esta orden',style:{display:'flex',alignItems:'center',gap:4,color:'var(--slate)',fontSize:10,fontWeight:600,flexShrink:0,whiteSpace:'nowrap',paddingTop:3}},
                        h(Ico,{n:'lock',s:12}),'No editable'
                      )
                    : h('button',{className:'btn-icon',title:'Editar hora de esta cita',onClick:()=>empezarEditarCita(c),style:{flexShrink:0}},h(Ico,{n:'edit',s:13}))
                  )
                ),

                editing&&h('div',{style:{marginTop:10,paddingTop:10,borderTop:'1px dashed var(--amber2)'}},
                  h('div',{style:{display:'flex',gap:8,marginBottom:8}},
                    h('div',{className:'fg',style:{flex:1,marginBottom:0}},h('label',null,'Nueva hora inicio'),h('input',{type:'time',value:citaEditForm.hora_cita_inicio,onChange:e=>setCitaEditForm(p=>({...p,hora_cita_inicio:e.target.value}))})),
                    h('div',{className:'fg',style:{flex:1,marginBottom:0}},h('label',null,'Nueva hora fin'),h('input',{type:'time',value:citaEditForm.hora_cita_fin,onChange:e=>setCitaEditForm(p=>({...p,hora_cita_fin:e.target.value}))}))
                  ),
                  !horasOk&&citaEditForm.hora_cita_inicio&&citaEditForm.hora_cita_fin&&h('p',{style:{fontSize:11,color:'var(--red)',marginTop:-4,marginBottom:8}},'La hora de inicio debe ser anterior a la hora de fin.'),
                  h('div',{className:'fg',style:{marginBottom:6}},
                    h('label',null,'Motivo del cambio ',h('span',{className:'req'},'*')),
                    h('input',{type:'text',placeholder:'Ej: proveedor llamó y pidió adelantar la cita',value:citaEditForm.motivo,onChange:e=>setCitaEditForm(p=>({...p,motivo:e.target.value}))})
                  ),
                  h('p',{style:{fontSize:10.5,color:'var(--slate)',display:'flex',alignItems:'flex-start',gap:4,marginBottom:10,lineHeight:1.4}},
                    h(Ico,{n:'lock',s:11,style:{flexShrink:0,marginTop:1}}),
                    'Este cambio queda registrado con tu usuario, la hora y el motivo -- es el respaldo de quién autorizó mover la cita.'
                  ),
                  citaEditErr&&h('div',{className:'alert-err',style:{marginBottom:8}},h(Ico,{n:'alert',s:14}),citaEditErr),
                  h('div',{style:{display:'flex',gap:6}},
                    h('button',{className:'btn-cancel',onClick:cancelarEditarCita,disabled:citaEditSaving,style:{flex:1}},'Cancelar'),
                    h('button',{className:'btn-primary',onClick:guardarEditarCita,disabled:citaEditSaving||!motivoOk||!horasOk,style:{flex:1}},
                      citaEditSaving?h('div',{className:'spinner'}):h(Ico,{n:'check',s:14}),
                      citaEditSaving?'Guardando...':'Guardar cambio'
                    )
                  )
                )
              );
            })
          ),

          h('div',{style:{marginTop:14}},
            h('button',{className:'btn-cancel',style:{width:'100%'},onClick:()=>setCitasModal(false)},'Cerrar')
          )
        )
      )
    )
  );
}
