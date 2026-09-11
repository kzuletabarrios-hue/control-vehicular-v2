// ── QR SCANNER ──
// Extraído de frontend/index.html (líneas 4858-4934, sección
// "/* ── QR SCANNER ── */" del <script> monolítico). Contenido idéntico al
// original: el código viejo en index.html NO fue tocado ni borrado (ver
// notas de la Fase 2/3 del plan de migración) -- este módulo es una copia
// autocontenida, lista para que las fases posteriores lo importen cuando
// quede conectado vía <script type="module">.
//
// Depende de React (useState/useRef/useEffect globales) y del icono
// compartido Ico (core/icons.js). También depende de `window.Html5Qrcode`,
// cargado como global UMD por el <script src="https://unpkg.com/html5-qrcode...">
// del <head> de index.html -- igual que React, no se importa como módulo ES.

import { Ico } from '../core/icons.js';

const { useState, useRef, useEffect } = React;
const h = React.createElement;

export function QRScanner({onScan,onClose}){
  const scannerRef = useRef(null);
  const activeRef  = useRef(true);
  const runningRef = useRef(false);
  const [error,setError] = useState(null);

  const safeStop = ()=>{
    if(!runningRef.current || !scannerRef.current) return Promise.resolve();
    runningRef.current = false;
    try{ return scannerRef.current.stop().catch(()=>{}); }
    catch(err){ return Promise.resolve(); }
  };

  const reportError = (err)=>{
    if(!activeRef.current) return;
    const msg = (err && (err.message||err.name)) || String(err);
    setError(
      /NotAllowedError|Permission/i.test(msg)
        ? 'Permiso de cámara denegado. Habilítalo en los ajustes del navegador y vuelve a intentar.'
        : /NotFoundError/i.test(msg)
          ? 'No se encontró ninguna cámara en este dispositivo.'
          : /NotSupportedError|secure context/i.test(msg)
            ? 'Este navegador no soporta acceso a la cámara en esta conexión. Asegúrate de usar https.'
            : 'No se pudo abrir la cámara: '+msg
    );
  };

  useEffect(()=>{
    activeRef.current = true;
    try{
      const Lib = window.Html5Qrcode;
      if(!Lib){ setError('No se pudo cargar el escáner. Verifica tu conexión a internet y vuelve a intentar.'); return; }
      if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
        setError('Este navegador no permite acceso a la cámara. Prueba con Chrome o Safari actualizado.');
        return;
      }
      const scanner = new Lib('qr-scan-region');
      scannerRef.current = scanner;
      scanner.start(
        {facingMode:'environment'},
        {fps:10,qrbox:{width:240,height:240}},
        (text)=>{
          if(!activeRef.current) return;
          safeStop().finally(()=>{ if(activeRef.current) onScan(text); });
        },
        ()=>{}
      ).then(()=>{ runningRef.current = true; }).catch(reportError);
    }catch(err){
      reportError(err);
    }
    return ()=>{
      activeRef.current = false;
      safeStop();
    };
  },[]);

  return h('div',{style:{position:'fixed',inset:0,background:'#000',zIndex:300,display:'flex',flexDirection:'column'}},
    h('div',{style:{padding:'14px 16px',display:'flex',justifyContent:'space-between',alignItems:'center',background:'rgba(0,0,0,0.85)',flexShrink:0}},
      h('span',{style:{color:'#fff',fontWeight:700,fontSize:14}},h(Ico,{n:'qrCode',s:16}),' Apunta al QR del punto'),
      h('button',{onClick:()=>{ safeStop(); onClose(); },
        style:{background:'none',border:'none',color:'#fff',cursor:'pointer',padding:4}},
        h(Ico,{n:'x',s:24})
      )
    ),
    error
      ? h('div',{style:{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'24px',gap:14}},
          h(Ico,{n:'alert',s:36,style:{color:'#f59e0b'}}),
          h('p',{style:{color:'#fff',fontSize:13,textAlign:'center',maxWidth:280}},error),
          h('button',{className:'btn-primary',onClick:onClose,style:{padding:'8px 20px'}},'Volver')
        )
      : h('div',{id:'qr-scan-region',style:{flex:1}}),
    !error&&h('div',{style:{padding:'12px 16px',background:'rgba(0,0,0,0.85)',textAlign:'center',flexShrink:0}},
      h('p',{style:{color:'rgba(255,255,255,0.65)',fontSize:12}},'Centra el código QR en el recuadro')
    )
  );
}
