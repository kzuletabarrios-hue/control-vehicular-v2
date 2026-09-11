// ── API CLIENT ──
// Extraído de frontend/index.html (líneas ~561-613, sección
// "/* ── API CLIENT ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que las fases 3-6 la importen cuando quede
// conectada vía <script type="module">.

import { API_BASE } from './config.js';
import { getToken, getRefresh, clearAuth } from './auth-store.js';

// Fallback de fecha para el nombre de archivo exportado cuando el backend
// no manda Content-Disposition con filename (ver `exportar` más abajo). En
// el monolito original esto reutiliza la función compartida `today()` de
// la sección UTILS. Acá se duplica intencionalmente esa única línea (en
// vez de importar utils.js) para no crear una dependencia circular:
// utils.js necesita importar `api` de este archivo (para `_tsBog`), así
// que este archivo no debe depender de utils.js a su vez.
const _fallbackFechaArchivo = () => {
  const b = new Date(Date.now() - 18000000);
  const p = n => String(n).padStart(2, '0');
  return `${b.getUTCFullYear()}-${p(b.getUTCMonth()+1)}-${p(b.getUTCDate())}`;
};

export const api = {
  _fetch: async (path,opts={}) => {
    const token = getToken();
    const headers = {'Content-Type':'application/json', ...(token?{Authorization:`Bearer ${token}`}:{})};
    const rawUrl = `${API_BASE}${path}`;
    const safeUrl = rawUrl.startsWith('http:') ? rawUrl.replace('http:','https:') : rawUrl;
    const r = await fetch(safeUrl,{...opts,headers:{...headers,...(opts.headers||{})}});
    if(r.status===401){
      const rt = getRefresh();
      if(rt){
        try{
          const rr = await fetch(`${API_BASE}/auth/refresh`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:rt})});
          if(rr.ok){
            const {access_token} = await rr.json();
            localStorage.setItem('cv_token',access_token);
            const r2 = await fetch(`${API_BASE}${path}`,{...opts,headers:{...headers,Authorization:`Bearer ${access_token}`}});
            if(!r2.ok) throw new Error(await r2.text());
            return r2.json();
          }
        }catch(e){}
      }
      clearAuth();
      window.location.reload();
      return;
    }
    if(!r.ok) throw new Error(await r.text());
    return r.json();
  },
  get:  (p)     => api._fetch(p),
  post: (p,b)   => api._fetch(p,{method:'POST', body:JSON.stringify(b)}),
  put:  (p,b)   => api._fetch(p,{method:'PUT',  body:JSON.stringify(b)}),
  del:  (p)     => api._fetch(p,{method:'DELETE'}),
  patch:(p,b)   => api._fetch(p,{method:'PATCH', body:JSON.stringify(b)}),
  exportar: async (tabla,fi,ff) => {
    const token = getToken();
    let url = `${API_BASE}/export/${tabla}`;
    const ps=[]; if(fi)ps.push('fecha_desde='+fi); if(ff)ps.push('fecha_hasta='+ff);
    if(ps.length) url+='?'+ps.join('&');
    try{
      const resp = await fetch(url,{headers:{Authorization:'Bearer '+token}});
      if(!resp.ok) throw new Error('Error '+resp.status);
      const blob = await resp.blob();
      const cd   = resp.headers.get('Content-Disposition')||'';
      const m    = cd.match(/filename="([^"]+)"/);
      const a    = document.createElement('a');
      a.href     = URL.createObjectURL(blob);
      a.download = m ? m[1] : `${tabla}_${_fallbackFechaArchivo()}.xlsx`;
      a.click();
      URL.revokeObjectURL(a.href);
    }catch(e){ alert('Error al exportar: '+e.message); }
  }
};
