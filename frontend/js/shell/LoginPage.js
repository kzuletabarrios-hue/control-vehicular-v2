// ── LOGIN PAGE ──
// Extraído de frontend/index.html (líneas 526-575, sección
// "/* ── LOGIN PAGE ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que la Fase 6 lo importe cuando quede conectado
// vía <script type="module">.
//
// Hace el POST de /auth/login directamente con fetch (no vía api.post, que
// exige token) -- réplica exacta del monolito. Solo usa API_BASE de
// core/config.js y setAuth/setRefresh de core/auth-store.js para persistir
// la sesión; onLogin(usuario) es un callback que App() root usa para poner
// el usuario en su propio estado (no se toca esa integración aquí).

import { API_BASE } from '../core/config.js';
import { setAuth, setRefresh } from '../core/auth-store.js';
import { Ico } from '../core/icons.js';

const { useState } = React;
const h = React.createElement;

export function LoginPage({onLogin}){
  const [email,setEmail]   = useState('');
  const [pass,setPass]     = useState('');
  const [loading,setLoading]= useState(false);
  const [error,setError]   = useState('');

  const handleLogin = async () => {
    if(!email||!pass) return setError('Ingresa email y contraseña');
    setLoading(true); setError('');
    try{
      const r = await fetch(`${API_BASE}/auth/login`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({email,password:pass})
      });
      if(!r.ok){ const e=await r.json(); throw new Error(e.detail||'Error al ingresar'); }
      const data = await r.json();
      setAuth(data.access_token, data.usuario);
      setRefresh(data.refresh_token);
      onLogin(data.usuario);
    }catch(e){ setError(e.message);
    }finally{ setLoading(false); }
  };

  return h('div',{className:'login-wrap'},
    h('div',{className:'login-logo'},
      h('div',{className:'login-icon'},h(Ico,{n:'truck',s:36})),
      h('h1',null,'CONTROL DE ACCESO Y OPERACIONES'),
      h('span',null,'CEDI R10')
    ),
    h('div',{className:'login-card'},
      h('h2',{className:'login-title'},'Iniciar sesión'),
      h('p',{className:'login-sub'},'Ingresa tus credenciales de acceso'),
      error&&h('div',{className:'login-error'},h(Ico,{n:'alert',s:14}),h('span',null,error)),
      h('div',{className:'l-group'},
        h('label',null,'Correo electrónico'),
        h('input',{type:'email',value:email,onChange:e=>setEmail(e.target.value),placeholder:'usuario@empresa.com',autoComplete:'email'})
      ),
      h('div',{className:'l-group'},
        h('label',null,'Contraseña'),
        h('input',{type:'password',value:pass,onChange:e=>setPass(e.target.value),placeholder:'••••••••',autoComplete:'current-password',
          onKeyDown:e=>e.key==='Enter'&&handleLogin()})
      ),
      h('button',{className:'btn-login',onClick:handleLogin,disabled:loading},
        loading?h('div',{className:'spinner'}):h(Ico,{n:'lock',s:16}),
        loading?'Ingresando...':'Ingresar'
      )
    )
  );
}
