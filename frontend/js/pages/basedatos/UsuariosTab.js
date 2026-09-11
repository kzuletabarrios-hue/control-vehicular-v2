// ── BASE DATOS · USUARIOS TAB ──
// Extraído de frontend/index.html (líneas 4609-4708, función BdUsuariosTab
// del <script> monolítico, tab de "BASE DATOS PAGE"). El código original
// en index.html NO fue tocado ni borrado.
//
// NOTA: el objeto ROL_LABELS (index.html líneas 4603-4607, justo antes de
// BdUsuariosTab en el monolito) NO se redeclara aquí. En la fase 4 (shell/)
// María ya lo adelantó a core/utils.js porque PerfilSheet lo necesitaba
// antes de tiempo. Este archivo lo importa desde ahí para no duplicar la
// fuente de verdad.
//
// Importa Ico (core/icons.js), api (core/api-client.js),
// capitalizarNombre y ROL_LABELS (core/utils.js) y los componentes
// compartidos Alert, LoadingDots (shared/).
//
// Depende de React como global UMD, igual que el monolito original.

import { Ico } from '../../core/icons.js';
import { api } from '../../core/api-client.js';
import { capitalizarNombre, ROL_LABELS } from '../../core/utils.js';
import { Alert } from '../../shared/Alert.js';
import { LoadingDots } from '../../shared/LoadingDots.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function UsuariosTab(){
  const [view,setView]        = useState('list');
  const [records,setRecords]  = useState([]);
  const [loading,setLoading]  = useState(true);
  const [saving,setSaving]    = useState(false);
  const [alert,setAlert]      = useState(null);
  const [selected,setSelected]= useState(null);
  const emptyF = {nombre:'',email:'',password:'',rol:'operador'};
  const [form,setForm] = useState(emptyF);

  const load = useCallback(()=>{
    setLoading(true);
    api.get('/auth/usuarios').then(setRecords).catch(()=>setAlert({type:'err',msg:'Sin permiso para ver usuarios'})).finally(()=>setLoading(false));
  },[]);
  useEffect(()=>load(),[load]);

  const handleSave = async()=>{
    setSaving(true);
    try{
      if(selected){
        if(!form.nombre||!form.email) return setAlert({type:'err',msg:'Nombre y email son requeridos'});
        const body={nombre:form.nombre,email:form.email,rol:form.rol};
        if(form.password) body.password=form.password;
        await api.put(`/auth/usuarios/${selected.id}`,body);
        setAlert({type:'ok',msg:'Usuario actualizado'});
      } else {
        if(!form.nombre||!form.email||!form.password) return setAlert({type:'err',msg:'Nombre, email y contraseña son requeridos'});
        await api.post('/auth/usuarios',form);
        setAlert({type:'ok',msg:'Usuario creado'});
      }
      setView('list');setForm(emptyF);setSelected(null);load();
    }catch(e){setAlert({type:'err',msg:'Error: '+e.message});}
    finally{setSaving(false);}
  };

  const handleToggle = async(uid,e)=>{
    e.stopPropagation();
    try{ await api.put(`/auth/usuarios/${uid}/toggle`,{}); load(); }
    catch(err){ setAlert({type:'err',msg:'Error: '+err.message}); }
  };

  if(view==='form') return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{className:'scroll-body',style:{padding:'12px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},h(Ico,{n:'user',s:12}),selected?' Editar usuario':' Nuevo usuario'),
        h('div',{className:'fg'},h('label',null,'Nombre',h('span',{className:'req'},'*')),
          h('input',{type:'text',value:form.nombre,onChange:e=>setForm(p=>({...p,nombre:e.target.value})),onBlur:()=>setForm(p=>({...p,nombre:capitalizarNombre(p.nombre)})),placeholder:'Nombre completo'})
        ),
        h('div',{className:'fg'},h('label',null,'Email',h('span',{className:'req'},'*')),
          h('input',{type:'email',value:form.email,onChange:e=>setForm(p=>({...p,email:e.target.value})),placeholder:'correo@empresa.com'})
        ),
        h('div',{className:'fg'},h('label',null,selected?'Nueva contraseña (dejar vacío para no cambiar)':'Contraseña',!selected&&h('span',{className:'req'},'*')),
          h('input',{type:'password',value:form.password,onChange:e=>setForm(p=>({...p,password:e.target.value})),placeholder:selected?'Nueva contraseña (opcional)':'Mínimo 8 caracteres'})
        ),
        h('div',{className:'fg'},h('label',null,'Rol'),
          h('select',{value:form.rol,onChange:e=>setForm(p=>({...p,rol:e.target.value}))},
            Object.entries(ROL_LABELS).map(([v,l])=>h('option',{key:v,value:v},l))
          )
        )
      )
    ),
    h('div',{className:'sticky-cta'},
      h('button',{className:'btn-cancel',onClick:()=>{setView('list');setForm(emptyF);setSelected(null);}},h(Ico,{n:'x',s:15})),
      h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:16}),saving?'Guardando...':'Guardar')
    )
  );

  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{display:'flex',padding:'8px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0}},
      h('button',{onClick:()=>setView('form'),style:{marginLeft:'auto',background:'var(--amber)',border:'none',color:'var(--navy)',borderRadius:8,padding:'7px 14px',cursor:'pointer',display:'flex',alignItems:'center',gap:4,fontSize:12,fontWeight:700,fontFamily:'inherit'}},
        h(Ico,{n:'plus',s:15}),' Nuevo'
      )
    ),
    h('div',{className:'scroll-body',style:{padding:'10px 14px'}},
      alert&&h(Alert,{...alert,onClose:()=>setAlert(null)}),
      loading?h(LoadingDots):
      records.length===0?h('div',{className:'empty'},h(Ico,{n:'user',s:44}),h('p',null,'Sin usuarios')):
      records.map(r=>h('div',{key:r.id,className:'list-item'},
        h('div',{className:'li-icon',style:{background:r.rol==='admin'?'#fef3c7':'#e0e7ff'}},
          h(Ico,{n:'user',s:18,style:{color:r.rol==='admin'?'#d97706':'#4338ca'}})
        ),
        h('div',{className:'li-body',onClick:()=>{setForm({nombre:r.nombre,email:r.email,password:'',rol:r.rol});setSelected(r);setView('form');}},
          h('div',{className:'li-title'},r.nombre),
          h('div',{className:'li-sub'},r.email)
        ),
        h('div',{className:'li-right'},
          h('span',{className:`pill ${r.rol==='admin'?'pill-amber':'pill-blue'}`},ROL_LABELS[r.rol]||r.rol),
          h('div',{style:{display:'flex',alignItems:'center',gap:4,marginTop:4}},
            h('span',{className:`pill ${r.activo?'pill-green':'pill-slate'}`,style:{fontSize:9}},r.activo?'Activo':'Inactivo'),
            h('button',{title:r.activo?'Desactivar':'Activar',onClick:e=>handleToggle(r.id,e),
              className:r.activo?'li-act li-act-danger':'li-act li-act-positive'},
              h(Ico,{n:r.activo?'trash':'checkCircle',s:13})
            )
          )
        )
      ))
    )
  );
}
