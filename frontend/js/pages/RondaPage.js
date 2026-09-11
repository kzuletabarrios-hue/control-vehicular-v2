// ── RONDA PAGE (rondas de vigilancia — recorredor externo / admin) ──
// Extraído de frontend/index.html (líneas 5016-5383, función RondaPage del
// <script> monolítico, entre el cierre de BtnNovedad y el comentario
// "/* ── PANEL RONDERO (supervisión) ── */" -- que corresponde a
// RondaPanelPage, NO extraída en este lote). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado -- este
// módulo es una copia autocontenida, lista para que la Fase 6 lo importe
// cuando quede conectado vía <script type="module">.
//
// Hallazgo: a diferencia de MuellesPage/ProveedoresPage/CitasPage/etc.,
// esta página NO usa useVisibilityPolling en el monolito original (solo
// carga con useEffect al montar / al cambiar turnoSel) -- se preserva tal
// cual, sin agregar polling que no estaba.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// obtenerUbicacion (core/utils.js) y los componentes compartidos Alert,
// LoadingDots, CameraField, ConfirmSheet, QRScanner (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.
// También usa `localStorage` del navegador (recordar el turno elegido) tal
// cual el original.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { obtenerUbicacion } from '../core/utils.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { CameraField } from '../shared/CameraField.js';
import { ConfirmSheet } from '../shared/ConfirmSheet.js';
import { QRScanner } from '../shared/QRScanner.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function RondaPage({user}){
  const [tab,setTab]                 = useState('cronograma'); // cronograma | activa
  const [cronograma,setCronograma]   = useState(null);
  const [ciclo,setCiclo]             = useState(null);
  const [apoyos,setApoyos]           = useState([]);
  const [loading,setLoading]         = useState(true);
  const [view,setView]               = useState('list'); // list | scanning | confirmar | scanningApoyo
  const [selPunto,setSelPunto]       = useState(null);
  const [codEscaneado,setCodEscaneado] = useState('');
  const emptyConf = {estado:'ok',observacion:'',fotografia:null};
  const [conf,setConf]     = useState(emptyConf);
  const [saving,setSaving] = useState(false);
  const [alert,setAlert]   = useState(null);
  const [showPausa,setShowPausa] = useState(false);
  const [confirmCancelar,setConfirmCancelar] = useState(false);
  const [pausaMotivo,setPausaMotivo] = useState('Baño');
  const [pausaOtro,setPausaOtro] = useState('');
  const [turnoSel,setTurnoSel] = useState(()=>localStorage.getItem('cv_turno_ronda')||'');

  const esAdmin      = ['admin','supervisor'].includes(user?.rol);
  const esRecorredor = user?.rol==='recorredor_externo';

  const load = useCallback(()=>{
    setLoading(true);
    const qs = turnoSel ? `?turno=${turnoSel}` : '';
    Promise.all([
      api.get(`/rondas/turno/cronograma${qs}`).then(r=>setCronograma(r)).catch(()=>{}),
      esRecorredor ? api.get('/rondas/ciclo/activo').then(r=>setCiclo(r)).catch(()=>{}) : Promise.resolve(),
      esRecorredor ? api.get('/rondas/apoyo/hoy').then(r=>setApoyos(Array.isArray(r)?r:[])).catch(()=>{}) : Promise.resolve(),
    ]).finally(()=>setLoading(false));
  },[esRecorredor,turnoSel]);
  useEffect(()=>{ load(); },[load]);

  const elegirTurno = (t)=>{
    setTurnoSel(t);
    if(t) localStorage.setItem('cv_turno_ronda',t); else localStorage.removeItem('cv_turno_ronda');
  };

  const apoyoEnCurso = apoyos.find(a=>!a.hora_salida);

  const ST = {
    ok:      {bg:'#d1fae5',color:'#065f46',label:'OK',icon:'checkCircle'},
    novedad: {bg:'#fef3c7',color:'#92400e',label:'Novedad',icon:'alert'},
    omitido: {bg:'#f1f5f9',color:'#64748b',label:'Omitido',icon:'x'},
  };
  const ITEM_ST = {
    pendiente:  {bg:'#f1f5f9',color:'#64748b',label:'Pendiente'},
    en_curso:   {bg:'#dbeafe',color:'#1d4ed8',label:'En curso'},
    pausada:    {bg:'#fef3c7',color:'#92400e',label:'En pausa'},
    completa:   {bg:'#d1fae5',color:'#065f46',label:'Completa'},
    completo:   {bg:'#d1fae5',color:'#065f46',label:'Completo'},
    incompleta: {bg:'#fee2e2',color:'#991b1b',label:'Incompleta'},
  };

  const handleScan = (codigo)=>{ setCodEscaneado(codigo); setView('confirmar'); };

  const handleIniciarRonda = async()=>{
    setAlert(null);
    try{
      await api.post('/rondas/ciclo/iniciar',{turno:cronograma?.turno});
      setAlert({type:'ok',msg:'Ronda iniciada desde Tanques'});
      setTab('activa'); load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }
  };

  const handleMarcar = async()=>{
    if(!selPunto||!ciclo?.ciclo) return;
    setSaving(true); setAlert(null);
    try{
      const ubicacion = await obtenerUbicacion();
      const r = await api.put('/rondas/marcar',{
        ciclo_id:ciclo.ciclo.id, punto_id:selPunto.id, codigo_escaneado:codEscaneado,
        estado:conf.estado,observacion:conf.observacion||null,fotografia:conf.fotografia||null,
        lat:ubicacion?.lat??null, lng:ubicacion?.lng??null,
      });
      setAlert({type:'ok',msg:r.message||'Punto marcado correctamente'});
      setView('list'); setSelPunto(null); setCodEscaneado(''); setConf(emptyConf);
      load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }finally{ setSaving(false); }
  };

  const handlePausar = async()=>{
    setAlert(null);
    const motivo = pausaMotivo==='Otro'?(pausaOtro.trim()||'Otro'):pausaMotivo;
    try{
      await api.post('/rondas/ciclo/pausar',{motivo});
      setShowPausa(false); setPausaOtro('');
      setAlert({type:'ok',msg:'Ronda en pausa'});
      load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }
  };

  const handleCancelar = async()=>{
    setAlert(null);
    try{
      await api.post('/rondas/ciclo/cancelar',{});
      setConfirmCancelar(false);
      setAlert({type:'ok',msg:'Ronda cancelada'});
      load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }
  };

  const handleReanudar = async()=>{
    setAlert(null);
    try{
      await api.post('/rondas/ciclo/reanudar',{});
      setAlert({type:'ok',msg:'Ronda reanudada'});
      load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }
  };

  const handleScanApoyo = async(codigo)=>{
    setView('list'); setAlert(null);
    try{
      const r = await api.post('/rondas/apoyo/marcar',{codigo_escaneado:codigo});
      setAlert({type:'ok',msg:r.accion==='llegada'?`Llegada a apoyo registrada (${r.motivo})`:'Salida de apoyo registrada'});
      load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }
  };

  if(view==='scanning') return h(QRScanner,{onScan:handleScan,onClose:()=>setView('list')});
  if(view==='scanningApoyo') return h(QRScanner,{onScan:handleScanApoyo,onClose:()=>setView('list')});

  if(view==='confirmar'&&selPunto) return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('button',{onClick:()=>setView('list'),style:{background:'none',border:'none',color:'#fff',cursor:'pointer',display:'flex',alignItems:'center',gap:6,fontSize:13,fontWeight:600}},
          h(Ico,{n:'arrowLeft',s:18}),' Volver'
        ),
        h('div',{className:'header-brand'},h('h1',null,'Confirmar marcación'),h('span',null,'Ronda'))
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard',style:{border:'1.5px solid #86efac'}},
        h('p',{className:'sec-ttl'},h(Ico,{n:'checkCircle',s:12}),' QR verificado — ', selPunto.nombre),
        h('div',{className:'fg'},
          h('label',null,'Código escaneado'),
          h('p',{style:{fontFamily:'monospace',fontSize:11,padding:'4px 0',color:'var(--slate)',wordBreak:'break-all'}},codEscaneado)
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'clipboard',s:12}),' Estado del punto'),
        h('div',{className:'fg'},
          h('label',null,'Estado'),
          h('select',{value:conf.estado,onChange:e=>setConf(p=>({...p,estado:e.target.value}))},
            h('option',{value:'ok'},'✓ Todo bien'),
            h('option',{value:'novedad'},'⚠ Novedad encontrada'),
            h('option',{value:'omitido'},'— Punto inaccesible / omitido')
          )
        ),
        (conf.estado==='novedad'||conf.estado==='omitido')&&h('div',{className:'fg'},
          h('label',null,conf.estado==='omitido'?'Motivo de omisión':'Descripción de la novedad',
            conf.estado==='omitido'&&h('span',{className:'req'},'*')
          ),
          h('textarea',{value:conf.observacion,onChange:e=>setConf(p=>({...p,observacion:e.target.value})),rows:3,
            placeholder:conf.estado==='omitido'?'¿Por qué no se pudo acceder al punto?':'Describe lo encontrado...'})
        ),
        conf.estado==='novedad'&&h('div',{className:'fg'},
          h('label',null,'Foto de evidencia (opcional)'),
          h(CameraField,{value:conf.fotografia,onChange:v=>setConf(p=>({...p,fotografia:v}))})
        )
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>setView('list')},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleMarcar,disabled:saving},
        saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),
        saving?'Guardando...':'Confirmar marcación'
      )
    )
  );

  const completadas = cronograma?.rondas_completadas||0;
  const objetivo     = cronograma?.rondas_objetivo||8;
  const progreso     = objetivo>0?Math.round((completadas/objetivo)*100):0;

  const TIPO_LABEL = {ronda:'Ronda',apoyo:'Apoyo operativo',permanencia:'Permanencia en Tanques'};

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('div',{className:'header-brand'},
          h('h1',null,'Ronda de Marcación'),
          h('span',null,'CEDI R10 · Turno '+(cronograma?.turno==='noche'?'noche':'día'))
        ),
        esAdmin&&h('button',{
          onClick:()=>{
            const tok=localStorage.getItem('cv_token');
            fetch('/api/rondas/puntos/qr-print',{headers:{'Authorization':'Bearer '+tok}})
              .then(r=>{
                if(!r.ok) return r.text().then(t=>{throw new Error('HTTP '+r.status+': '+t)});
                return r.text();
              })
              .then(html=>{
                if(!html||html.trim().length<50){throw new Error('Respuesta vacía del servidor')}
                const blob=new Blob([html],{type:'text/html'});
                const url=URL.createObjectURL(blob);
                const w=window.open(url,'_blank');
                if(!w) alert('El navegador bloqueó la ventana emergente. Permite popups para este sitio y vuelve a intentarlo.');
              })
              .catch(e=>alert('Error QR: '+(e.message||e)));
          },
          style:{background:'rgba(255,255,255,0.15)',border:'none',color:'#fff',borderRadius:8,
            padding:'6px 10px',cursor:'pointer',fontSize:11,fontWeight:700,display:'flex',alignItems:'center',gap:4}
        },h(Ico,{n:'download',s:13}),' Imprimir QR')
      )
    ),
    esRecorredor&&h('div',{style:{display:'flex',gap:6,padding:'10px 14px 0'}},
      h('button',{onClick:()=>setTab('cronograma'),
        style:{flex:1,padding:'8px 0',borderRadius:8,border:'none',cursor:'pointer',fontSize:12,fontWeight:700,
          background:tab==='cronograma'?'var(--navy2)':'#e2e8f0',color:tab==='cronograma'?'#fff':'var(--text2)'}},
        'Cronograma'),
      h('button',{onClick:()=>setTab('activa'),
        style:{flex:1,padding:'8px 0',borderRadius:8,border:'none',cursor:'pointer',fontSize:12,fontWeight:700,
          background:tab==='activa'?'var(--navy2)':'#e2e8f0',color:tab==='activa'?'#fff':'var(--text2)'}},
        'Ronda activa')
    ),
    esRecorredor&&h('div',{style:{display:'flex',gap:6,alignItems:'center',padding:'8px 14px 0',flexWrap:'wrap'}},
      h('span',{style:{fontSize:11,color:'var(--slate)',fontWeight:600}},'Mi turno:'),
      h('button',{onClick:()=>elegirTurno('dia'),
        style:{padding:'4px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',
          background:turnoSel==='dia'?'var(--navy)':'transparent',color:turnoSel==='dia'?'#fff':'var(--slate)',borderColor:turnoSel==='dia'?'var(--navy)':'var(--border)'}},
        'Día (06-18h)'),
      h('button',{onClick:()=>elegirTurno('noche'),
        style:{padding:'4px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',
          background:turnoSel==='noche'?'var(--navy)':'transparent',color:turnoSel==='noche'?'#fff':'var(--slate)',borderColor:turnoSel==='noche'?'var(--navy)':'var(--border)'}},
        'Noche (18-06h)'),
      turnoSel&&h('button',{onClick:()=>elegirTurno(''),title:'Volver a detección automática',
        style:{padding:'4px 8px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'none',background:'none',color:'var(--slate)',textDecoration:'underline'}},
        'Auto')
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),

      h('div',{className:'fcard',style:{marginBottom:10}},
        h('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}},
          h('span',{style:{fontSize:13,fontWeight:700}},`${completadas} / ${objetivo} rondas completadas`),
          h('span',{style:{fontSize:14,fontWeight:800,color:progreso===100?'#059669':'var(--navy2)'}},`${progreso}%`)
        ),
        h('div',{style:{height:6,background:'#e2e8f0',borderRadius:3,overflow:'hidden'}},
          h('div',{style:{height:'100%',background:progreso===100?'#059669':'var(--amber)',borderRadius:3,
            width:`${progreso}%`,transition:'width .4s'}})
        )
      ),

      loading?h(LoadingDots):

      (!esRecorredor||tab==='cronograma')?(
        !cronograma||!cronograma.items?.length
          ? h('div',{className:'empty'},h(Ico,{n:'clock',s:44}),h('p',null,'No hay cronograma disponible'))
          : cronograma.items.map((it,i)=>{
              const st = ITEM_ST[it.estado]||ITEM_ST.pendiente;
              return h('div',{key:i,className:'list-item'},
                h('div',{className:'li-icon',style:{background:st.bg}},
                  h(Ico,{n:it.tipo==='ronda'?'mapPin':it.tipo==='apoyo'?'userCheck':'clock',s:18,style:{color:st.color}})
                ),
                h('div',{className:'li-body'},
                  h('div',{className:'li-title'},
                    it.tipo==='ronda'?`Ronda ${it.numero}`:it.tipo==='apoyo'?it.motivo:'Permanencia en Tanques'),
                  h('div',{className:'li-sub'},`${it.hora_inicio} – ${it.hora_fin}`)
                ),
                h('div',{className:'li-right'},
                  h('span',{className:'pill',style:{background:st.bg,color:st.color}},st.label)
                )
              );
            })
      ):(
        !ciclo?.activo
          ? h('div',{className:'empty'},
              h(Ico,{n:'mapPin',s:44}),
              h('p',null,completadas>=objetivo?'Ya completaste las rondas obligatorias del turno':'No tienes una ronda en curso'),
              completadas<objetivo&&!apoyoEnCurso&&h('button',{className:'btn-primary',style:{marginTop:10},onClick:handleIniciarRonda},
                h(Ico,{n:'mapPin',s:16}),' Iniciar ronda desde Tanques')
            )
          : ciclo.ciclo.estado==='pausada' ? h(React.Fragment,null,
              h('div',{className:'fcard',style:{marginBottom:10,border:'1.5px solid #fcd34d',background:'#fffbeb'}},
                h('p',{className:'sec-ttl'},h(Ico,{n:'alert',s:12}),' Ronda en pausa'),
                h('p',{style:{fontSize:12,fontWeight:700,color:'#92400e',margin:'2px 0'}},ciclo.ciclo.pausa_motivo||'Pausa breve'),
                h('p',{style:{fontSize:11,color:'var(--slate)'}},'Reanuda la ronda para seguir marcando puntos.')
              ),
              h('button',{className:'btn-primary',onClick:handleReanudar},h(Ico,{n:'checkCircle',s:16}),' Reanudar ronda'),
              h('button',{className:'btn-cancel',style:{marginTop:8,width:'100%',color:'#dc2626'},onClick:()=>setConfirmCancelar(true)},h(Ico,{n:'x',s:14}),' Cancelar ronda')
            ) : h(React.Fragment,null,
              h('div',{className:'fcard',style:{marginBottom:10,border:'1.5px solid #93c5fd'}},
                h('p',{className:'sec-ttl'},h(Ico,{n:'mapPin',s:12}),` Ronda ${ciclo.ciclo.numero_ronda} en curso`),
                h('p',{style:{fontSize:11,color:'var(--slate)'}},'Recorre los puntos pendientes y regresa a Tanques para cerrar la ronda.')
              ),
              !showPausa && h('button',{className:'btn-cancel',style:{marginBottom:10,width:'100%'},onClick:()=>setShowPausa(true)},
                h(Ico,{n:'clock',s:14}),' Pausar ronda (baño, llaves, etc.)'),
              !showPausa && h('button',{className:'btn-cancel',style:{marginBottom:10,width:'100%',color:'#dc2626'},onClick:()=>setConfirmCancelar(true)},
                h(Ico,{n:'x',s:14}),' Cancelar ronda'),
              showPausa && h('div',{className:'fcard',style:{marginBottom:10}},
                h('p',{className:'sec-ttl'},h(Ico,{n:'clock',s:12}),' Motivo de la pausa'),
                h('div',{className:'fg'},
                  h('select',{value:pausaMotivo,onChange:e=>setPausaMotivo(e.target.value)},
                    h('option',{value:'Baño'},'Baño'),
                    h('option',{value:'Entrega de llaves'},'Entrega de llaves'),
                    h('option',{value:'Otro'},'Otro')
                  )
                ),
                pausaMotivo==='Otro' && h('div',{className:'fg'},
                  h('textarea',{value:pausaOtro,onChange:e=>setPausaOtro(e.target.value),rows:2,placeholder:'Describe el motivo...'})
                ),
                h('div',{style:{display:'flex',gap:8}},
                  h('button',{className:'btn-cancel',onClick:()=>setShowPausa(false)},'Cancelar'),
                  h('button',{className:'btn-primary',style:{flex:1},onClick:handlePausar},h(Ico,{n:'clock',s:14}),' Confirmar pausa')
                )
              ),
              ciclo.pendientes.map(p=>h('div',{key:p.id,className:'list-item',onClick:()=>{
                  setSelPunto(p); setConf(emptyConf); setCodEscaneado(''); setView('scanning');
                },style:{cursor:'pointer'}},
                h('div',{className:'li-icon',style:{background:'#dbeafe'}},h(Ico,{n:p.es_base?'mapPin':'mapPin',s:18,style:{color:'#1d4ed8'}})),
                h('div',{className:'li-body'},
                  h('div',{className:'li-title'},`${p.orden}. ${p.nombre}`+(p.es_base?' (regreso final)':'')),
                  h('div',{className:'li-sub',style:{color:'#1d4ed8'}},h(Ico,{n:'qrCode',s:11}),' Toca para escanear QR')
                ),
                h('div',{className:'li-right'},h('span',{className:'pill pill-blue'},'Pendiente'))
              )),
              ciclo.marcados.map(m=>{
                const st=ST[m.estado]||ST.ok;
                return h('div',{key:m.id,className:'list-item'},
                  h('div',{className:'li-icon',style:{background:st.bg}},
                    h(Ico,{n:m.estado==='ok'?'checkCircle':m.estado==='novedad'?'alert':'x',s:18,style:{color:st.color}})
                  ),
                  h('div',{className:'li-body'},
                    h('div',{className:'li-title'},`${m.orden}. ${m.punto_nombre}`),
                    h('div',{className:'li-sub'},(m.hora_marcacion||'').slice(0,5))
                  ),
                  h('div',{className:'li-right'},h('span',{className:'pill',style:{background:st.bg,color:st.color}},st.label))
                );
              })
            )
      )
    ),
    esRecorredor&&h('button',{
      onClick:()=>setView('scanningApoyo'),
      title:'Apoyo Operativo',
      style:{position:'fixed',bottom:'68px',right:'70px',width:46,height:46,
        background:apoyoEnCurso?'#dc2626':'#0f766e',color:'#fff',border:'none',borderRadius:'50%',
        cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',
        boxShadow:'0 4px 16px rgba(15,118,110,0.5)',zIndex:90}
    }, h(Ico,{n:'userCheck',s:19})),
    confirmCancelar&&h(ConfirmSheet,{
      msg:'Se cancelará la ronda en curso. Los puntos ya marcados quedan registrados, pero esta ronda no contará como completada.',
      onOk:handleCancelar,
      onCancel:()=>setConfirmCancelar(false)
    })
  );
}
