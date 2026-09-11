// ── CAMBIAR PASSWORD SHEET ──
// Extraído de frontend/index.html (líneas 578-635, sección
// "/* ── CAMBIAR PASSWORD SHEET ── */" del <script> monolítico). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado (ver notas de la Fase 2 del plan de migración) -- este módulo es
// una copia autocontenida, lista para que la Fase 6 lo importe cuando quede
// conectado vía <script type="module">.
//
// Nota: en el monolito este sheet no tiene ningún consumidor activo (el
// flujo real de cambiar contraseña vive en PerfilSheet, que duplica el
// mismo formulario inline). Se extrae igual, tal cual está, sin inventar
// ni eliminar nada -- ver también la nota equivalente en PerfilSheet.js.

import { api } from '../core/api-client.js';
import { Ico } from '../core/icons.js';

const { useState } = React;
const h = React.createElement;

export function CambiarPasswordSheet({onClose,onSuccess}){
  const [actual,setActual]       = useState('');
  const [nueva,setNueva]         = useState('');
  const [confirmar,setConfirmar] = useState('');
  const [saving,setSaving]       = useState(false);
  const [err,setErr]             = useState('');
  const [done,setDone]           = useState(false);

  const handleSave = async()=>{
    setErr('');
    if(!actual||!nueva||!confirmar) return setErr('Todos los campos son requeridos');
    if(nueva.length<8) return setErr('La nueva contraseña debe tener mínimo 8 caracteres');
    if(nueva!==confirmar) return setErr('Las contraseñas nuevas no coinciden');
    setSaving(true);
    try{
      await api.put('/auth/usuarios/cambiar-password',{password_actual:actual,password_nueva:nueva});
      setDone(true);
      setTimeout(onSuccess,2000);
    }catch(e){ let m=e.message||'Error'; try{m=JSON.parse(m).detail||m;}catch{}; setErr(m); }
    finally{ setSaving(false); }
  };

  return h('div',{className:'overlay',onClick:onClose},
    h('div',{className:'sheet',onClick:e=>e.stopPropagation()},
      h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:16}},
        h('h3',{style:{fontSize:15,fontWeight:700,color:'var(--navy)',display:'flex',alignItems:'center',gap:6}},h(Ico,{n:'key',s:15}),'Cambiar contraseña'),
        h('button',{onClick:onClose,style:{background:'none',border:'none',cursor:'pointer',padding:4,color:'var(--slate)'}},h(Ico,{n:'x',s:18}))
      ),
      done
        ? h('div',{style:{textAlign:'center',padding:'16px 0'}},
            h('div',{style:{fontSize:32,marginBottom:8}},'✓'),
            h('p',{style:{color:'var(--navy2)',fontWeight:600}},'Contraseña actualizada'),
            h('p',{style:{fontSize:12,color:'var(--slate)',marginTop:4}},'Cerrando sesión...')
          )
        : h('div',null,
            err&&h('div',{className:'alert-err',style:{marginBottom:12,padding:'8px 12px',borderRadius:8,fontSize:12}},err),
            h('div',{className:'fg'},
              h('label',null,'Contraseña actual'),
              h('input',{type:'password',value:actual,onChange:e=>setActual(e.target.value),placeholder:'••••••••',autoComplete:'current-password'})
            ),
            h('div',{className:'fg'},
              h('label',null,'Nueva contraseña'),
              h('input',{type:'password',value:nueva,onChange:e=>setNueva(e.target.value),placeholder:'Mínimo 8 caracteres',autoComplete:'new-password'})
            ),
            h('div',{className:'fg',style:{marginBottom:16}},
              h('label',null,'Confirmar nueva contraseña'),
              h('input',{type:'password',value:confirmar,onChange:e=>setConfirmar(e.target.value),placeholder:'Repetir contraseña',autoComplete:'new-password',
                onKeyDown:e=>e.key==='Enter'&&handleSave()})
            ),
            h('div',{style:{display:'flex',gap:8}},
              h('button',{className:'btn-primary',style:{background:'none',border:'1.5px solid var(--navy2)',color:'var(--navy2)',flex:1},onClick:onClose},'Cancelar'),
              h('button',{className:'btn-primary',onClick:handleSave,disabled:saving},
                saving?h('div',{className:'spinner'}):h(Ico,{n:'save',s:15}),saving?'Guardando...':'Guardar')
            )
          )
    )
  );
}
