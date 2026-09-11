// ── BASE DATOS PAGE (contenedor de tabs) ──
// Extraído de frontend/index.html (líneas 4829-4856, función BaseDatosPage
// del <script> monolítico, cierre de la sección "BASE DATOS PAGE" que
// comenzaba en la línea 4262). El código original en index.html NO fue
// tocado ni borrado.
//
// BaseDatosPage monta cada tab por estado local (useState 'tab'), sin
// pasarle props adicionales a los tabs (cada uno resuelve su propia carga
// de datos internamente vía api.get) -- se replica exactamente esa misma
// API aquí, importando cada tab desde su archivo hermano en esta carpeta.
//
// Depende de React como global UMD, igual que el monolito original.

import { PersonasTab } from './PersonasTab.js';
import { ProveedoresTab } from './ProveedoresTab.js';
import { TiendasTab } from './TiendasTab.js';
import { ConductoresTab } from './ConductoresTab.js';
import { UsuariosTab } from './UsuariosTab.js';
import { ConductoresFrecuentesTab } from './ConductoresFrecuentesTab.js';

const { useState } = React;
const h = React.createElement;

export function BaseDatosPage({user}){
  const [tab,setTab] = useState('personas');
  const isAdmin = user?.rol === 'admin';
  const tabs = [
    {id:'personas',    label:'Personas'},
    {id:'proveedores', label:'Proveedores'},
    {id:'tiendas',     label:'Tiendas'},
    {id:'conductores', label:'Conductores'},
    {id:'cond-frec',   label:'Frecuentes'},
    ...(isAdmin?[{id:'usuarios',label:'Usuarios'}]:[]),
  ];
  return h('div',{style:{display:'flex',flexDirection:'column',flex:1,overflow:'hidden'}},
    h('div',{style:{display:'flex',gap:6,padding:'10px 14px',background:'var(--white)',borderBottom:'1px solid var(--border)',flexShrink:0,overflowX:'auto',WebkitOverflowScrolling:'touch'}},
      tabs.map(t=>h('button',{key:t.id,onClick:()=>setTab(t.id),
        style:{flexShrink:0,padding:'8px 12px',borderRadius:8,fontSize:12,fontWeight:700,border:'1.5px solid',cursor:'pointer',fontFamily:'inherit',whiteSpace:'nowrap',
          background:tab===t.id?'var(--navy2)':'none',
          color:tab===t.id?'#fff':'var(--slate)',
          borderColor:tab===t.id?'var(--navy2)':'var(--border)'}
      },t.label))
    ),
    tab==='personas'    && h(PersonasTab),
    tab==='proveedores' && h(ProveedoresTab),
    tab==='tiendas'     && h(TiendasTab),
    tab==='conductores' && h(ConductoresTab),
    tab==='cond-frec'   && h(ConductoresFrecuentesTab),
    tab==='usuarios'    && h(UsuariosTab)
  );
}
