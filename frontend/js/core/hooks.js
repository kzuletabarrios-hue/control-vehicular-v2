// ── HOOKS COMPARTIDOS ──
// Extraído de frontend/index.html (líneas ~719-760, sección
// "/* ── POLLING CON PAUSA EN SEGUNDO PLANO ── */" del <script>
// monolítico). Contenido idéntico al original: el código viejo en
// index.html NO fue tocado ni borrado (ver notas de la Fase 2 del plan de
// migración) -- este módulo es una copia autocontenida, lista para que las
// fases 3-6 lo importen cuando quede conectado vía <script type="module">.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

const { useEffect, useRef } = React;

/* ── POLLING CON PAUSA EN SEGUNDO PLANO ──
   Sustituye a setInterval "a secas" en pantallas que refrescan datos
   periódicamente. Evita el egress de Supabase que se sigue generando
   cuando la pestaña queda oculta (minimizada o con la pantalla del
   guarda bloqueada): mientras document.visibilityState !== 'visible' el
   polling queda en pausa por completo (sin fetch alguno) y se reanuda
   -- con una ejecución inmediata, para no dejar datos obsoletos -- en
   cuanto la pestaña vuelve a estar visible.
   `fn` puede cambiar en cada render (se guarda en un ref, sin necesidad
   de useCallback en quien llama), y `deps` controla cuándo se reinicia
   el ciclo completo (listener + interval), igual que el arreglo de
   dependencias de un useEffect normal. `enabled=false` desactiva el
   polling por completo (ni fetch inicial ni listener) -- lo usan
   pantallas donde el refresco solo aplica a una sub-vista puntual
   (p.ej. el QR de portería solo mientras esa vista está abierta). */
export function useVisibilityPolling(fn, intervalMs, deps=[], enabled=true){
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(()=>{
    if(!enabled) return;
    let timerId = null;
    const start = ()=>{
      if(timerId) return; // ya corriendo, evita duplicar el interval
      fnRef.current();
      timerId = setInterval(()=>fnRef.current(), intervalMs);
    };
    const stop = ()=>{
      if(timerId){ clearInterval(timerId); timerId=null; }
    };
    const onVisibilityChange = ()=>{
      if(document.visibilityState==='visible') start();
      else stop();
    };
    if(document.visibilityState==='visible') start();
    document.addEventListener('visibilitychange', onVisibilityChange);
    return ()=>{
      stop();
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled]);
}
