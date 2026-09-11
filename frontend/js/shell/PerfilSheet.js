// ── PERFIL SHEET ──
// Extraído de frontend/index.html (líneas 637-706, sección
// "/* ── PERFIL SHEET ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que la Fase 6 lo importe cuando quede conectado
// vía <script type="module">.
//
// Nota: este componente duplica el mismo formulario de "cambiar contraseña"
// de CambiarPasswordSheet.js (ese sheet no tiene consumidores en el
// monolito) -- se replica tal cual está en el original, sin fusionarlos,
// porque no es parte del alcance de esta fase decidir esa refactorización.
//
// ROL_LABELS vive en core/utils.js (ver comentario ahí): en el monolito
// está declarado más abajo, en la sección de Base de Datos (línea ~4603),
// pero como constante de módulo se evalúa antes del primer render, así que
// funciona igual. Acá se importa explícitamente en vez de duplicarlo.

import { api } from '../core/api-client.js';
import { Ico } from '../core/icons.js';
import { initials, ROL_LABELS } from '../core/utils.js';

const { useState } = React;
const h = React.createElement;

export function PerfilSheet({user,onClose,onLogout}){
  const [actual,setActual]       = useState('');
  const [nueva,setNueva]         = useState('');
  const [confirmar,setConfirmar] = useState('');
  const [saving,setSaving]       = useState(false);
  const [err,setErr]             = useState('');
  const [done,setDone]           = useState(false);

  const handleSave = async()=>{
    setErr('');
    if(!actual||!nueva||!confirmar) return setErr('Todos los campos son requeridos');
    if(nueva.length<8) return setErr('Mínimo 8 caracteres');
    if(nueva!==confirmar) return setErr('Las contraseñas no coinciden');
    setSaving(true);
    try{
      await api.put('/auth/usuarios/cambiar-password',{password_actual:actual,password_nueva:nueva});
      setDone(true);
      setTimeout(onLogout,2000);
    }catch(e){ let m=e.message||'Error'; try{m=JSON.parse(m).detail||m;}catch{}; setErr(m); }
    finally{ setSaving(false); }
  };

  return h('div',{className:'overlay',onClick:onClose},
    h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
      h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:14}},
        h('h3',{style:{fontSize:15,fontWeight:700,color:'var(--navy)'}},'Mi perfil'),
        h('button',{onClick:onClose,style:{background:'none',border:'none',cursor:'pointer',padding:4,color:'var(--slate)'}},h(Ico,{n:'x',s:18}))
      ),
      h('div',{style:{display:'flex',alignItems:'center',gap:12,padding:'12px 14px',background:'#f8fafc',borderRadius:10,marginBottom:16}},
        h('div',{className:'user-avatar',style:{width:44,height:44,fontSize:17,flexShrink:0}},initials(user?.nombre||'')),
        h('div',{style:{minWidth:0}},
          h('div',{style:{fontWeight:700,fontSize:15,color:'var(--navy)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}},user?.nombre),
          h('div',{style:{fontSize:12,color:'var(--slate)',marginTop:2,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}},user?.email),
          h('span',{className:'pill pill-blue',style:{marginTop:5,display:'inline-block'}},ROL_LABELS[user?.rol]||user?.rol)
        )
      ),
      done
        ? h('div',{style:{textAlign:'center',padding:'20px 0'}},
            h('div',{style:{fontSize:36,marginBottom:8}},'✓'),
            h('p',{style:{color:'var(--navy2)',fontWeight:600}},'Contraseña actualizada'),
            h('p',{style:{fontSize:12,color:'var(--slate)',marginTop:4}},'Cerrando sesión...')
          )
        : h('div',null,
            h('p',{style:{fontSize:12,fontWeight:700,color:'var(--slate)',textTransform:'uppercase',letterSpacing:'0.05em',marginBottom:10}},
              h(Ico,{n:'key',s:12}),' Cambiar contraseña'),
            err&&h('div',{className:'alert-err',style:{marginBottom:10,padding:'8px 12px',borderRadius:8,fontSize:12}},err),
            h('div',{className:'fg'},
              h('label',null,'Contraseña actual'),
              h('input',{type:'password',value:actual,onChange:e=>setActual(e.target.value),placeholder:'••••••••',autoComplete:'current-password'})
            ),
            h('div',{className:'fg'},
              h('label',null,'Nueva contraseña'),
              h('input',{type:'password',value:nueva,onChange:e=>setNueva(e.target.value),placeholder:'Mínimo 8 caracteres',autoComplete:'new-password'})
            ),
            h('div',{className:'fg',style:{marginBottom:14}},
              h('label',null,'Confirmar nueva contraseña'),
              h('input',{type:'password',value:confirmar,onChange:e=>setConfirmar(e.target.value),placeholder:'Repetir contraseña',autoComplete:'new-password',
                onKeyDown:e=>e.key==='Enter'&&handleSave()})
            ),
            h('button',{className:'btn-primary',onClick:handleSave,disabled:saving,style:{width:'100%',marginBottom:12}},
              saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:15}),saving?'Guardando...':'Guardar contraseña'
            ),
            h('button',{onClick:onLogout,style:{width:'100%',display:'flex',alignItems:'center',justifyContent:'center',gap:8,background:'#fee2e2',border:'none',borderRadius:8,padding:'10px 14px',cursor:'pointer',fontSize:13,fontWeight:600,color:'#dc2626',fontFamily:'inherit'}},
              h(Ico,{n:'logOut',s:14}),'Cerrar sesión'
            )
          )
    )
  );
}
