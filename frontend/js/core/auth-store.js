// ── AUTH STORE + OFFLINE QUEUE ──
// Extraído de frontend/index.html (líneas ~547-559, secciones
// "/* ── AUTH STORE ── */" y "/* ── OFFLINE QUEUE ── */" del <script>
// monolítico). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado (ver notas de la Fase 2 del plan de
// migración) -- este módulo es una copia autocontenida, lista para que las
// fases 3-6 la importen cuando quede conectada vía <script type="module">.

export const getToken  = () => localStorage.getItem('cv_token');
export const getUser   = () => { try{return JSON.parse(localStorage.getItem('cv_user')||'null')}catch{return null} };
export const setAuth   = (token,user) => { localStorage.setItem('cv_token',token); localStorage.setItem('cv_user',JSON.stringify(user)); };
export const clearAuth = () => { localStorage.removeItem('cv_token'); localStorage.removeItem('cv_user'); localStorage.removeItem('cv_refresh'); };
export const getRefresh = () => localStorage.getItem('cv_refresh');
export const setRefresh = (t) => localStorage.setItem('cv_refresh',t);

// ── OFFLINE QUEUE ──
export const QUEUE_KEY = 'cv_offline_queue';
export const getQueue = () => { try{return JSON.parse(localStorage.getItem(QUEUE_KEY)||'[]')}catch{return []} };
export const addToQueue = (item) => { const q = getQueue(); q.push({...item,id:Date.now(),ts:new Date().toISOString()}); localStorage.setItem(QUEUE_KEY,JSON.stringify(q)); };
export const clearQueue = () => localStorage.removeItem(QUEUE_KEY);
