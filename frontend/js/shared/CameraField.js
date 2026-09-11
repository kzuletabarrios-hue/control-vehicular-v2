// ── CAMERA COMPONENT ──
// Extraído de frontend/index.html (líneas 332-404, sección
// "/* ── CAMERA COMPONENT ── */" del <script> monolítico). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado (ver notas de la Fase 2/3 del plan de migración) -- este módulo
// es una copia autocontenida, lista para que las fases posteriores lo
// importen cuando quede conectado vía <script type="module">.
//
// Depende de React (useState/useRef/useEffect globales), del icono
// compartido Ico (core/icons.js), del cliente `api` (core/api-client.js)
// para subir la foto comprimida, y de LoadingDots (./LoadingDots.js),
// ya extraído por el agente anterior.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { LoadingDots } from './LoadingDots.js';

const { useState, useRef, useEffect } = React;
const h = React.createElement;

export function CameraField({value,onChange}){
  const fileRef = useRef();
  const ready   = useRef(false);
  const [uploading,setUploading] = useState(false);
  const [errUp,setErrUp]         = useState(null);
  useEffect(()=>{ const t=setTimeout(()=>{ready.current=true;},350); return ()=>clearTimeout(t); },[]);
  const compress = (file,cb,cbErr) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      try {
        const MAX = 800;
        let w=img.width,h=img.height;
        if(w>MAX){h=h*(MAX/w);w=MAX;}
        const c=document.createElement('canvas'); c.width=w; c.height=h;
        c.getContext('2d').drawImage(img,0,0,w,h);
        const dataUrl = c.toDataURL('image/jpeg',0.75);
        URL.revokeObjectURL(url);
        cb(dataUrl);
      } catch(err) {
        URL.revokeObjectURL(url);
        cbErr(err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      cbErr(new Error('No se pudo decodificar la imagen'));
    };
    img.src=url;
  };
  const handleFile = e => {
    const f=e.target.files[0]; if(!f) return;
    e.target.value = '';
    setErrUp(null); setUploading(true);
    compress(f, async b64 => {
      try {
        const {url} = await api.post('/upload-foto',{data:b64});
        onChange(url);
      } catch(err) {
        setErrUp('Error al subir foto. Intenta de nuevo.');
      } finally { setUploading(false); }
    }, err => {
      setErrUp('No se pudo procesar la foto. Intenta de nuevo o elige otra imagen.');
      setUploading(false);
    });
  };
  if(uploading) return h('div',{className:'camera-field'},
    h(LoadingDots),
    h('p',{style:{fontSize:12,marginTop:6,color:'var(--text2)'}},'Subiendo foto...')
  );
  if(value) return h('div',null,
    h('div',{className:'camera-preview'},h('img',{src:value,alt:'foto'})),
    errUp && h('p',{style:{color:'#e11d48',fontSize:11,marginTop:4}},errUp),
    h('div',{className:'camera-preview-actions'},
      h('button',{className:'btn-sm-outline',style:{borderColor:'#e11d48',color:'#e11d48'},onClick:()=>onChange(null)},
        h(Ico,{n:'trash',s:13}),' Eliminar'
      ),
      h('button',{className:'btn-sm-outline',style:{borderColor:'var(--navy2)',color:'var(--navy2)'},onClick:()=>fileRef.current.click()},
        h(Ico,{n:'camera',s:13}),' Cambiar'
      )
    ),
    h('input',{ref:fileRef,type:'file',accept:'image/*',capture:'environment',onChange:handleFile,style:{display:'none'}})
  );
  return h('div',null,
    h('div',{className:'camera-field',onClick:()=>{ if(ready.current) fileRef.current.click(); }},
      h(Ico,{n:'camera',s:28}),
      h('p',null,'Toca para tomar foto o seleccionar')
    ),
    errUp && h('p',{style:{color:'#e11d48',fontSize:11,marginTop:4}},errUp),
    h('input',{ref:fileRef,type:'file',accept:'image/*',capture:'environment',onChange:handleFile,style:{display:'none'}})
  );
}
