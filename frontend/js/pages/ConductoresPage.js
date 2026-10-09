// ── CONDUCTORES PAGE ──
// Alta y mantenimiento del maestro de conductores para el puesto peatonal
// (guarda_peatonal) y admin. Bodega/vehicular solo eligen de la lista; si el
// conductor no aparece, se lo piden al peatonal.
//
// Contrato backend (routers/conductores.py):
//   GET  /conductores?activo=true        lista
//   GET  /conductores?cedula=<texto>     [] o [conductor] (aviso de duplicado)
//   POST /conductores {conductor,n_cedula,celular?}
//   PUT  /conductores/{id}               parcial (corregir datos / activo:false)
// El backend normaliza nombre a MAYÚSCULAS y cédula a solo dígitos.
// Los errores llegan como Error cuyo message es el texto JSON {"detail":...}.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { Alert } from '../shared/Alert.js';
import { LoadingDots } from '../shared/LoadingDots.js';
import { ConfirmSheet } from '../shared/ConfirmSheet.js';

const { useState, useEffect, useCallback, useRef } = React;
const h = React.createElement;

const soloDigitos = v => String(v||'').replace(/\D/g,'');
const cedulaValida = v => { const d = soloDigitos(v); return d.length>=6 && d.length<=10; };
const MIN_TOUCH = 44;

// Traduce el error del servidor a un mensaje claro en español.
function textoError(e){
  let d = '';
  try{
    const j = JSON.parse(e.message).detail;
    d = Array.isArray(j) ? j.map(x=>x.msg||'').join('; ') : String(j||'');
  }catch(_){ d = String(e&&e.message||''); }
  const dl = d.toLowerCase();
  if(dl.includes('entre 6 y 10')) return 'La cédula debe tener entre 6 y 10 dígitos (solo números).';
  if(dl.includes('ya existe')){
    const m = d.match(/:\s*(.+)$/);
    return 'Esta cédula ya está registrada'+(m?' a nombre de '+m[1]:'')+'.';
  }
  if(dl.includes('permiso')||dl.includes('forbidden')||dl.includes('not authorized')||dl.includes('no autorizado')) return 'No tienes permiso para esta acción.';
  if(dl.includes('nombre')) return 'El nombre es obligatorio.';
  if(!d || d[0]==='<' || dl.includes('failed to fetch') || dl.includes('networkerror')) return 'No se pudo conectar con el servidor. Revisa la señal e intenta de nuevo.';
  return d;
}

const inputBase = {width:'100%',boxSizing:'border-box',minHeight:MIN_TOUCH,fontSize:16};

export function ConductoresPage({user}){
  const [lista,setLista]       = useState([]);
  const [loading,setLoading]   = useState(true);
  const [alert,setAlert]       = useState(null);
  const [busqueda,setBusqueda] = useState('');

  // formulario de alta
  const [cedula,setCedula]   = useState('');
  const [nombre,setNombre]   = useState('');
  const [celular,setCelular] = useState('');
  const [saving,setSaving]   = useState(false);
  const [errForm,setErrForm] = useState('');
  const [dup,setDup]         = useState(null);      // nombre del conductor existente
  const [checking,setChecking] = useState(false);
  const reqId = useRef(0);

  // edición / desactivación
  const [edit,setEdit]         = useState(null);    // {id,conductor,n_cedula,celular}
  const [editErr,setEditErr]   = useState('');
  const [editSaving,setEditSaving] = useState(false);
  const [editDup,setEditDup]   = useState(null);
  const [confirmDes,setConfirmDes] = useState(null);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/conductores?activo=true')
      .then(r=>setLista(Array.isArray(r)?r:(r&&r.items)||[]))
      .catch(e=>setAlert({type:'err',msg:textoError(e)}))
      .finally(()=>setLoading(false));
  },[]);
  useEffect(()=>{load();},[load]);

  // Aviso de duplicado mientras escribe la cédula (debounce 400 ms).
  useEffect(()=>{
    const d = soloDigitos(cedula);
    setDup(null);
    if(d.length<6){ setChecking(false); return; }
    setChecking(true);
    const mine = ++reqId.current;
    const t = setTimeout(()=>{
      api.get('/conductores?cedula='+encodeURIComponent(d))
        .then(r=>{ if(mine!==reqId.current) return; const a = Array.isArray(r)?r:[]; setDup(a.length?(a[0].conductor||'(sin nombre)'):null); })
        .catch(()=>{})
        .finally(()=>{ if(mine===reqId.current) setChecking(false); });
    },400);
    return ()=>clearTimeout(t);
  },[cedula]);

  // Mismo aviso dentro del editor (excluye al propio conductor).
  useEffect(()=>{
    setEditDup(null);
    if(!edit) return;
    const d = soloDigitos(edit.n_cedula);
    if(d.length<6 || d===soloDigitos(edit.original)) return;
    const t = setTimeout(()=>{
      api.get('/conductores?cedula='+encodeURIComponent(d))
        .then(r=>{ const a = (Array.isArray(r)?r:[]).filter(c=>c.id!==edit.id); setEditDup(a.length?(a[0].conductor||'(sin nombre)'):null); })
        .catch(()=>{});
    },400);
    return ()=>clearTimeout(t);
  },[edit&&edit.n_cedula, edit&&edit.id]);

  const cedulaOk = cedulaValida(cedula);
  const nombreOk = nombre.trim().length>=3;
  const puedeCrear = cedulaOk && nombreOk && !dup && !checking && !saving;

  const crear = async(e)=>{
    e&&e.preventDefault();
    if(!puedeCrear) return;
    setSaving(true); setErrForm(''); setAlert(null);
    try{
      const body = {conductor:nombre.trim().toUpperCase(),n_cedula:soloDigitos(cedula)};
      if(celular.trim()) body.celular = soloDigitos(celular);
      await api.post('/conductores',body);
      setAlert({type:'ok',msg:'Conductor registrado: '+body.conductor+' · CC '+body.n_cedula+'. Ya aparece en la lista para bodega y vehicular.'});
      setCedula(''); setNombre(''); setCelular('');
      load();
    }catch(err){ setErrForm(textoError(err)); }
    finally{ setSaving(false); }
  };

  const abrirEditar = c=>{
    setEditErr(''); setEditDup(null);
    setEdit({id:c.id,conductor:c.conductor||'',n_cedula:c.n_cedula||'',celular:c.celular||'',original:c.n_cedula||''});
  };

  const guardarEdicion = async()=>{
    if(!edit) return;
    if(!cedulaValida(edit.n_cedula)) return setEditErr('La cédula debe tener entre 6 y 10 dígitos (solo números).');
    if(edit.conductor.trim().length<3) return setEditErr('El nombre es obligatorio.');
    if(editDup) return setEditErr('Esta cédula ya está registrada a nombre de '+editDup+'.');
    setEditSaving(true); setEditErr('');
    try{
      await api.put('/conductores/'+edit.id,{
        conductor:edit.conductor.trim().toUpperCase(),
        n_cedula:soloDigitos(edit.n_cedula),
        celular:soloDigitos(edit.celular)||null
      });
      setEdit(null);
      setAlert({type:'ok',msg:'Datos del conductor actualizados.'});
      load();
    }catch(err){ setEditErr(textoError(err)); }
    finally{ setEditSaving(false); }
  };

  const desactivar = async()=>{
    const c = confirmDes; setConfirmDes(null);
    if(!c) return;
    try{
      await api.put('/conductores/'+c.id,{activo:false});
      setAlert({type:'ok',msg:c.conductor+' fue desactivado y ya no aparece en las listas.'});
      load();
    }catch(err){ setAlert({type:'err',msg:textoError(err)}); }
  };

  const q = busqueda.trim().toLowerCase();
  const qDig = soloDigitos(busqueda);
  const visibles = lista
    .filter(c=>{
      if(!q) return true;
      return (c.conductor||'').toLowerCase().includes(q) || (qDig && soloDigitos(c.n_cedula).includes(qDig));
    })
    .sort((a,b)=>{
      const ia = cedulaValida(a.n_cedula)?1:0, ib = cedulaValida(b.n_cedula)?1:0;
      if(ia!==ib) return ia-ib;                       // inválidas primero
      return (a.conductor||'').localeCompare(b.conductor||'','es');
    });
  const nInvalidas = lista.filter(c=>!cedulaValida(c.n_cedula)).length;

  const btnAccion = (extra)=>({minHeight:MIN_TOUCH,minWidth:MIN_TOUCH,padding:'0 14px',borderRadius:10,fontSize:14,fontWeight:700,cursor:'pointer',fontFamily:'inherit',display:'inline-flex',alignItems:'center',justifyContent:'center',gap:6,...extra});
  const msgErr = (txt,id)=>h('p',{id,role:'alert',style:{margin:'6px 0 0',fontSize:13,fontWeight:600,color:'#b91c1c'}},txt);

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),

      // ── Formulario de alta ──
      h('form',{className:'fcard',onSubmit:crear,noValidate:true,'aria-labelledby':'cond-form-ttl'},
        h('p',{id:'cond-form-ttl',className:'sec-ttl'},h(Ico,{n:'userCheck',s:12}),' Registrar conductor nuevo'),
        h('div',{className:'fg'},
          h('label',{htmlFor:'cond-cedula'},'Cédula',h('span',{className:'req','aria-hidden':'true'},'*')),
          h('input',{id:'cond-cedula',type:'text',inputMode:'numeric',pattern:'[0-9]*',autoComplete:'off',maxLength:14,
            value:cedula,placeholder:'Solo números, 6 a 10 dígitos',
            'aria-invalid':(dup||(cedula&&!cedulaOk&&soloDigitos(cedula).length>10))?'true':'false',
            'aria-describedby':'cond-cedula-msg',
            onChange:e=>{setCedula(soloDigitos(e.target.value).slice(0,10));setErrForm('');},
            style:{...inputBase,borderColor:dup?'#dc2626':undefined}}),
          h('div',{id:'cond-cedula-msg',style:{minHeight:20}},
            dup?h('p',{role:'alert',style:{margin:'6px 0 0',fontSize:14,fontWeight:700,color:'#b91c1c'}},'Ya registrado: '+dup)
            :checking?h('p',{style:{margin:'6px 0 0',fontSize:12,color:'var(--slate)'}},'Verificando cédula...')
            :(cedula&&!cedulaOk)?h('p',{style:{margin:'6px 0 0',fontSize:12,color:'var(--slate)'}},'Faltan dígitos: la cédula tiene entre 6 y 10.')
            :(cedulaOk&&!dup)?h('p',{style:{margin:'6px 0 0',fontSize:12,fontWeight:600,color:'#047857'}},'Cédula disponible'):null
          )
        ),
        h('div',{className:'fg'},
          h('label',{htmlFor:'cond-nombre'},'Nombre completo',h('span',{className:'req','aria-hidden':'true'},'*')),
          h('input',{id:'cond-nombre',type:'text',autoComplete:'off',autoCapitalize:'characters',value:nombre,placeholder:'NOMBRES Y APELLIDOS',
            onChange:e=>{setNombre(e.target.value.toUpperCase());setErrForm('');},
            style:{...inputBase,textTransform:'uppercase'}})
        ),
        h('div',{className:'fg'},
          h('label',{htmlFor:'cond-celular'},'Celular (opcional)'),
          h('input',{id:'cond-celular',type:'tel',inputMode:'tel',autoComplete:'off',maxLength:10,value:celular,placeholder:'3001234567',
            onChange:e=>setCelular(soloDigitos(e.target.value).slice(0,10)),style:inputBase})
        ),
        errForm&&msgErr(errForm,'cond-form-err'),
        h('button',{type:'submit',className:'btn-primary',disabled:!puedeCrear,
          style:{width:'100%',minHeight:52,fontSize:16,marginTop:12,opacity:puedeCrear?1:0.5,cursor:puedeCrear?'pointer':'not-allowed'}},
          saving?h('div',{className:'spinner'}):h(Ico,{n:'plus',s:18}),saving?'Registrando...':'Registrar conductor'
        )
      ),

      // ── Lista ──
      h('div',{style:{display:'flex',alignItems:'baseline',justifyContent:'space-between',margin:'14px 2px 6px'}},
        h('p',{className:'sec-ttl',style:{margin:0}},h(Ico,{n:'users',s:12}),' Conductores registrados ('+lista.length+')'),
        h('button',{type:'button',onClick:load,'aria-label':'Actualizar lista',style:btnAccion({background:'none',border:'none',color:'var(--navy2)',padding:'0 8px'})},h(Ico,{n:'refresh',s:16}))
      ),
      nInvalidas>0&&h('div',{role:'status',style:{background:'#fffbeb',border:'1px solid #fcd34d',color:'#92400e',borderRadius:8,padding:'8px 10px',fontSize:13,fontWeight:600,marginBottom:8}},
        nInvalidas+(nInvalidas===1?' conductor tiene':' conductores tienen')+' la cédula incorrecta. Aparecen primero: toca "Editar" para corregirla.'),
      h('div',{className:'fg',style:{marginBottom:10}},
        h('label',{htmlFor:'cond-buscar',style:{position:'absolute',width:1,height:1,overflow:'hidden',clip:'rect(0 0 0 0)'}},'Buscar por nombre o cédula'),
        h('input',{id:'cond-buscar',type:'search',value:busqueda,onChange:e=>setBusqueda(e.target.value),placeholder:'Buscar por nombre o cédula',autoComplete:'off',style:inputBase})
      ),
      loading?h(LoadingDots):
      visibles.length===0?h('div',{className:'empty'},h(Ico,{n:'users',s:44}),h('p',null,q?'Sin resultados para "'+busqueda.trim()+'". Si no existe, regístralo arriba.':'Aún no hay conductores registrados')):
      visibles.map(c=>{
        const malo = !cedulaValida(c.n_cedula);
        return h('div',{key:c.id,className:'list-item',style:{cursor:'default',borderLeft:malo?'4px solid #d97706':undefined,background:malo?'#fffbeb':undefined}},
          h('div',{className:'li-body',style:{minWidth:0,flex:'1 1 160px'}},
            h('div',{className:'li-title'},c.conductor||'(sin nombre)'),
            h('div',{className:'li-sub',style:{fontSize:14}},'CC ',c.n_cedula||'—',c.celular?' · Cel. '+c.celular:''),
            malo&&h('div',{style:{display:'inline-flex',alignItems:'center',gap:4,marginTop:4,fontSize:13,fontWeight:700,color:'#92400e'}},h(Ico,{n:'alert',s:14}),'Corregir cédula')
          ),
          h('div',{style:{display:'flex',gap:8,flexShrink:0,alignItems:'center'}},
            h('button',{type:'button',onClick:()=>abrirEditar(c),'aria-label':'Editar '+(c.conductor||'conductor'),
              style:btnAccion({background:malo?'#d97706':'var(--navy2)',color:'#fff',border:'none'})},h(Ico,{n:'edit',s:16}),'Editar'),
            h('button',{type:'button',onClick:()=>setConfirmDes(c),'aria-label':'Desactivar '+(c.conductor||'conductor'),
              style:btnAccion({background:'#fef2f2',color:'#b91c1c',border:'1.5px solid #fecaca'})},h(Ico,{n:'ban',s:16}),'Desactivar')
          )
        );
      })
    ),

    // ── Editor ──
    edit&&h('div',{className:'overlay',onClick:()=>!editSaving&&setEdit(null)},
      h('div',{className:'sheet',role:'dialog','aria-modal':'true','aria-labelledby':'cond-edit-ttl',onClick:e=>e.stopPropagation(),style:{maxHeight:'90vh',overflowY:'auto'}},
        h('div',{className:'sheet-header'},
          h('span',{id:'cond-edit-ttl',style:{fontWeight:700,fontSize:15}},'Editar conductor'),
          h('button',{type:'button',className:'btn-icon','aria-label':'Cerrar',onClick:()=>setEdit(null),style:{minWidth:MIN_TOUCH,minHeight:MIN_TOUCH}},h(Ico,{n:'x',s:16}))
        ),
        h('div',{className:'fg'},
          h('label',{htmlFor:'ed-cedula'},'Cédula'),
          h('input',{id:'ed-cedula',type:'text',inputMode:'numeric',pattern:'[0-9]*',autoComplete:'off',value:edit.n_cedula,
            onChange:e=>{const v=soloDigitos(e.target.value).slice(0,10);setEdit(p=>({...p,n_cedula:v}));setEditErr('');},
            style:{...inputBase,borderColor:editDup?'#dc2626':undefined}}),
          editDup&&h('p',{role:'alert',style:{margin:'6px 0 0',fontSize:14,fontWeight:700,color:'#b91c1c'}},'Ya registrado: '+editDup)
        ),
        h('div',{className:'fg'},
          h('label',{htmlFor:'ed-nombre'},'Nombre completo'),
          h('input',{id:'ed-nombre',type:'text',autoComplete:'off',autoCapitalize:'characters',value:edit.conductor,
            onChange:e=>{const v=e.target.value.toUpperCase();setEdit(p=>({...p,conductor:v}));setEditErr('');},
            style:{...inputBase,textTransform:'uppercase'}})
        ),
        h('div',{className:'fg'},
          h('label',{htmlFor:'ed-celular'},'Celular (opcional)'),
          h('input',{id:'ed-celular',type:'tel',inputMode:'tel',autoComplete:'off',value:edit.celular,
            onChange:e=>{const v=soloDigitos(e.target.value).slice(0,10);setEdit(p=>({...p,celular:v}));},style:inputBase})
        ),
        editErr&&msgErr(editErr,'cond-edit-err'),
        h('div',{style:{display:'flex',gap:8,marginTop:14}},
          h('button',{type:'button',className:'btn-cancel',onClick:()=>setEdit(null),disabled:editSaving,style:{minHeight:MIN_TOUCH}},'Cancelar'),
          h('button',{type:'button',className:'btn-primary',onClick:guardarEdicion,disabled:editSaving||!!editDup,style:{minHeight:MIN_TOUCH,opacity:(editSaving||editDup)?0.5:1}},
            editSaving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),editSaving?'Guardando...':'Guardar cambios')
        )
      )
    ),

    confirmDes&&h(ConfirmSheet,{
      icon:'ban',titulo:'¿Desactivar conductor?',textoOk:'Desactivar',
      msg:(confirmDes.conductor||'Este conductor')+' (CC '+(confirmDes.n_cedula||'—')+') dejará de aparecer en las listas de bodega y vehicular.',
      onOk:desactivar,onCancel:()=>setConfirmDes(null)
    })
  );
}
