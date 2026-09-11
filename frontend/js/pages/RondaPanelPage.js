// ── PANEL RONDERO (supervisión) ──
// Extraído de frontend/index.html (líneas 5385-5529, función RondaPanelPage
// del <script> monolítico, marcada con el comentario
// "/* ── PANEL RONDERO (supervisión) ── */", justo después del cierre de
// RondaPage y antes de "/* ── NOVEDADES PAGE ── */"). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado -- este
// módulo es una copia autocontenida, lista para que la Fase 6 lo importe
// cuando quede conectado vía <script type="module">.
//
// Hallazgo: a diferencia de RondaPage.js (fase 5 lote 3), esta página SÍ usa
// useVisibilityPolling (cada 60s, pausado en background) para la vista "hoy" --
// se confirmó leyendo el código real, no se asumió del lote anterior. La
// vista "semana" (reporte semanal) usa un useEffect normal, sin polling,
// disparado solo al cambiar `vista`.
//
// Importa Ico (core/icons.js), api (core/api-client.js), fmtDate y
// useVisibilityPolling (core/utils.js y core/hooks.js) y los componentes
// compartidos Alert, LoadingDots, ConfirmSheet (shared/).
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { fmtDate } from '../core/utils.js';
import { useVisibilityPolling } from '../core/hooks.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { ConfirmSheet } from '../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function RondaPanelPage({user}){
  const [vista,setVista]     = useState('hoy');
  const [data,setData]       = useState([]);
  const [semana,setSemana]   = useState(null);
  const [loading,setLoading] = useState(true);
  const [alert,setAlert]     = useState(null);
  const [confirmCancelar,setConfirmCancelar] = useState(null); // {id, nombre}

  const load = useCallback(()=>{
    api.get('/rondas/panel').then(r=>setData(Array.isArray(r)?r:[])).catch(()=>{}).finally(()=>setLoading(false));
  },[]);
  // Panel de rondas es de las pantallas más operativas: 1 min y se pausa en
  // background.
  useVisibilityPolling(load, 60000, [load]);

  const handleCancelarAdmin = async()=>{
    if(!confirmCancelar) return;
    try{
      await api.post(`/rondas/ciclo/${confirmCancelar.id}/cancelar-admin`,{});
      setAlert({type:'ok',msg:'Ronda cancelada'});
      setConfirmCancelar(null);
      load();
    }catch(e){
      let msg=e.message; try{msg=JSON.parse(msg).detail||msg;}catch{}
      setAlert({type:'err',msg});
    }
  };

  useEffect(()=>{
    if(vista!=='semana') return;
    setLoading(true);
    api.get('/rondas/reporte-semanal').then(r=>setSemana(r)).catch(()=>{}).finally(()=>setLoading(false));
  },[vista]);

  const pillCumplimiento = (pct)=>{
    if(pct==null) return h('span',{className:'pill pill-slate'},'Sin datos');
    if(pct>=90) return h('span',{className:'pill pill-green'},pct+'%');
    if(pct>=70) return h('span',{className:'pill pill-amber'},pct+'%');
    return h('span',{className:'pill pill-red'},pct+'%');
  };

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'header'},
      h('div',{className:'header-inner'},
        h('div',{className:'header-brand'},h('h1',null,'Panel Rondero'),h('span',null,vista==='hoy'?'Seguimiento en vivo':'Cumplimiento semanal'))
      )
    ),
    h('div',{style:{display:'flex',gap:6,alignItems:'center',padding:'8px 14px 0',background:'var(--white)',borderBottom:'1px solid var(--border)'}},
      h('button',{onClick:()=>setVista('hoy'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:vista==='hoy'?'var(--navy)':'transparent',color:vista==='hoy'?'#fff':'var(--slate)',borderColor:vista==='hoy'?'var(--navy)':'var(--border)',marginBottom:8}},'Hoy'),
      h('button',{onClick:()=>setVista('semana'),style:{padding:'5px 10px',borderRadius:20,fontSize:11,fontWeight:600,cursor:'pointer',fontFamily:'inherit',border:'1.5px solid',background:vista==='semana'?'var(--navy)':'transparent',color:vista==='semana'?'#fff':'var(--slate)',borderColor:vista==='semana'?'var(--navy)':'var(--border)',marginBottom:8}},'Semana')
    ),
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      vista==='hoy'?(
        data.length===0?h('div',{className:'empty'},h(Ico,{n:'clock',s:44}),h('p',null,'No hay recorredores externos activos')):
        data.map(d=>h('div',{key:d.recorredor_id,className:'fcard',style:{marginBottom:10,
            border:d.alerta_atraso?'1.5px solid #fca5a5':'1.5px solid var(--border)'}},
          h('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}},
            h('p',{style:{fontWeight:700,fontSize:14}},d.recorredor_nombre),
            d.alerta_atraso&&h('span',{className:'pill',style:{background:'#fee2e2',color:'#991b1b'}},h(Ico,{n:'alert',s:11}),' Atraso')
          ),
          h('div',{style:{display:'flex',justifyContent:'space-between',marginBottom:6}},
            h('span',{style:{fontSize:12,color:'var(--slate)'}},'Rondas hoy'),
            h('span',{style:{fontSize:13,fontWeight:700}},`${d.rondas_completadas} / ${d.rondas_completadas + d.rondas_pendientes}`)
          ),
          d.ronda_en_curso&&h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',gap:6,marginBottom:4}},
            h('span',{style:{fontSize:11,color:'#1d4ed8'}},`Ronda ${d.ronda_en_curso.numero_ronda} en curso desde ${fmtDate(d.ronda_en_curso.fecha)}`),
            h('button',{
              onClick:()=>setConfirmCancelar({id:d.ronda_en_curso.id,nombre:d.recorredor_nombre}),
              style:{background:'none',border:'1px solid #fca5a5',color:'#dc2626',borderRadius:6,padding:'2px 8px',fontSize:10,fontWeight:700,cursor:'pointer',fontFamily:'inherit',flexShrink:0}
            },'Cancelar')
          ),
          d.ronda_en_pausa&&h('div',{style:{fontSize:11,color:'#92400e',marginBottom:4,fontWeight:700}},
            `En pausa: ${d.ronda_en_pausa.motivo} (${d.ronda_en_pausa.minutos} min)`),
          d.apoyo_en_curso&&h('div',{style:{fontSize:11,color:'#0f766e',marginBottom:4}},`En apoyo: ${d.apoyo_en_curso.motivo}`),
          h('div',{style:{display:'flex',justifyContent:'space-between',marginBottom:4}},
            h('span',{style:{fontSize:12,color:'var(--slate)'}},'Último QR'),
            h('span',{style:{fontSize:12}},d.ultimo_evento?d.ultimo_evento.detalle:'—')
          ),
          h('div',{style:{display:'flex',justifyContent:'space-between'}},
            h('span',{style:{fontSize:12,color:'var(--slate)'}},'Sin movimiento'),
            h('span',{style:{fontSize:12,fontWeight:700,color:d.alerta_atraso?'#dc2626':'var(--text2)'}},
              d.minutos_sin_movimiento!=null?`${d.minutos_sin_movimiento} min`:'—')
          ),
          d.historial_apoyos.length>0&&h('details',{style:{marginTop:8}},
            h('summary',{style:{fontSize:11,color:'var(--slate)',cursor:'pointer'}},`Historial de apoyos (${d.historial_apoyos.length})`),
            d.historial_apoyos.map(a=>h('div',{key:a.id,style:{fontSize:11,padding:'4px 0',borderTop:'1px solid var(--border)'}},
              `${a.motivo} · ${(a.hora_llegada||'').slice(11,16)} – ${a.hora_salida?a.hora_salida.slice(11,16):'en curso'}`
            ))
          ),
          (d.rondas_hoy||[]).length>0&&h('details',{style:{marginTop:8}},
            h('summary',{style:{fontSize:11,color:'var(--slate)',cursor:'pointer'}},`Rondas de hoy (${d.rondas_hoy.length})`),
            d.rondas_hoy.map(rh=>h('div',{key:rh.ciclo_id,style:{padding:'4px 0',borderTop:'1px solid var(--border)'}},
              h('div',{style:{fontSize:11,display:'flex',justifyContent:'space-between',gap:6}},
                h('span',null,`Ronda ${rh.numero_ronda} (${rh.turno}) · ${(rh.hora_inicio||'').slice(11,16)}${rh.hora_fin?' – '+rh.hora_fin.slice(11,16):' – en curso'}`),
                h('span',{style:{fontWeight:700,color:rh.distancia_m!=null?'var(--navy)':'var(--slate)',flexShrink:0}},
                  rh.distancia_m!=null?(rh.distancia_m>=1000?(rh.distancia_m/1000).toFixed(2)+' km':rh.distancia_m+' m'):'Sin GPS'
                )
              ),
              rh.sospechosa&&h('div',{title:rh.motivo_sospecha||'',style:{marginTop:3,fontSize:10,fontWeight:700,color:'#991b1b',background:'#fee2e2',borderRadius:6,padding:'2px 6px',display:'inline-block'}},
                `⚠ Sospechosa · ${rh.motivo_sospecha||''}`
              )
            ))
          )
        ))
      ):(
        !semana||semana.recorredores.length===0?h('div',{className:'empty'},h(Ico,{n:'clipboard',s:44}),h('p',null,'No hay recorredores externos activos')):[
          h('p',{key:'rango',style:{fontSize:11,color:'var(--slate)',marginBottom:10}},`Del ${fmtDate(semana.desde)} al ${fmtDate(semana.hasta)}`),
          ...semana.recorredores.map(d=>h('div',{key:d.recorredor_id,className:'fcard',style:{marginBottom:10}},
            h('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}},
              h('p',{style:{fontWeight:700,fontSize:14}},d.recorredor_nombre),
              pillCumplimiento(d.porcentaje)
            ),
            h('div',{style:{display:'flex',justifyContent:'space-between',marginBottom:6}},
              h('span',{style:{fontSize:12,color:'var(--slate)'}},'Rondas completadas'),
              h('span',{style:{fontSize:13,fontWeight:700}},`${d.total_completadas} / ${d.total_esperadas}`)
            ),
            h('div',{style:{display:'flex',justifyContent:'space-between'}},
              h('span',{style:{fontSize:12,color:'var(--slate)'}},'Novedades reportadas'),
              h('span',{style:{fontSize:12,fontWeight:700,color:d.novedades>0?'#dc2626':'var(--text2)'}},d.novedades)
            ),
            h('div',{style:{display:'flex',justifyContent:'space-between',marginTop:6}},
              h('span',{style:{fontSize:12,color:'var(--slate)'}},'Rondas sospechosas'),
              h('span',{style:{fontSize:12,fontWeight:700,color:d.rondas_sospechosas>0?'#991b1b':'var(--text2)'}},d.rondas_sospechosas)
            ),
            d.dias.length>0&&h('details',{style:{marginTop:8}},
              h('summary',{style:{fontSize:11,color:'var(--slate)',cursor:'pointer'}},`Detalle por turno (${d.dias.length})`),
              d.dias.map((t,i)=>h('div',{key:i,style:{display:'flex',justifyContent:'space-between',fontSize:11,padding:'4px 0',borderTop:'1px solid var(--border)'}},
                h('span',null,`${fmtDate(t.fecha)} · ${t.turno}`),
                h('span',{style:{fontWeight:600}},`${t.completadas} / ${t.esperadas}`)
              ))
            )
          ))
        ]
      )
    ),
    confirmCancelar&&h(ConfirmSheet,{
      msg:`Se cancelará la ronda atascada de ${confirmCancelar.nombre}. No contará como completada, pero ya podrá iniciar una ronda nueva.`,
      onOk:handleCancelarAdmin,
      onCancel:()=>setConfirmCancelar(null)
    })
  );
}
