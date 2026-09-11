// ── REGISTROS / EXPORT PAGE ──
// Extraído de frontend/index.html (líneas 1765-1802, función RegistrosPage
// del <script> monolítico, entre el comentario "REGISTROS / EXPORT PAGE" y
// el comentario "SUSTANCIAS / HERRAMIENTAS SUB-PAGE"). Contenido idéntico
// al original: el código viejo en index.html NO fue tocado ni borrado --
// este módulo es una copia autocontenida, lista para que la Fase 6 lo
// importe cuando quede conectado vía <script type="module">.
//
// Importa Ico (core/icons.js), api (core/api-client.js) y today
// (core/utils.js). No depende de TiendaPicker ni de badges.js -- se
// revisó el código real y esta página solo usa selección de módulo,
// rango de fechas y el botón de exportar Excel.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';
import { today } from '../core/utils.js';

const { useState } = React;
const h = React.createElement;

export function RegistrosPage(){
  const [modulo,setModulo] = useState('flota');
  const [fi,setFi] = useState('');
  const [ff,setFf] = useState(today());
  const mods = [{id:'flota',l:'Flota'},{id:'proveedores',l:'Proveedores'},{id:'control-acceso',l:'Acceso'},{id:'visitantes',l:'Visitas'},{id:'visita-vehicular',l:'Visita Vh.'},{id:'sustancias',l:'Sustancias'},{id:'herramientas',l:'Herramientas'},{id:'rondas',l:'Rondas'},{id:'apoyos',l:'Apoyos Op.'},{id:'novedades',l:'Novedades'},{id:'conductores',l:'Conductores'},{id:'bd-proveedores',l:'BD Prov.'},{id:'bd-empleados',l:'BD Empleados'},{id:'bd-vehiculos',l:'BD Vehículos'},{id:'bd-tiendas',l:'BD Tiendas'}];

  return h('div',{className:'scroll-body'},
    h('div',{className:'pad'},
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},'Módulo'),
        h('div',{style:{display:'flex',flexWrap:'wrap',gap:7}},
          mods.map(m=>h('button',{key:m.id,
            style:{padding:'7px 14px',borderRadius:20,fontSize:12,fontWeight:600,border:'1.5px solid',cursor:'pointer',fontFamily:'inherit',
              background:modulo===m.id?'var(--navy2)':'none',
              color:modulo===m.id?'#fff':'var(--slate)',
              borderColor:modulo===m.id?'var(--navy2)':'var(--border)'},
            onClick:()=>setModulo(m.id)},m.l))
        )
      ),
      h('div',{className:'fcard'},
        h('p',{className:'sec-ttl'},'Rango de fechas (opcional)'),
        h('div',{className:'fgrid2'},
          h('div',{className:'fg'},h('label',null,'Desde'),h('input',{type:'date',value:fi,onChange:e=>setFi(e.target.value)})),
          h('div',{className:'fg'},h('label',null,'Hasta'),h('input',{type:'date',value:ff,onChange:e=>setFf(e.target.value)}))
        )
      ),
      h('button',{
        style:{width:'100%',background:'var(--green)',color:'#fff',border:'none',borderRadius:12,padding:16,fontSize:15,fontWeight:700,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:8,fontFamily:'inherit'},
        onClick:()=>api.exportar(modulo,fi||null,ff||null)
      },h(Ico,{n:'download',s:20}),'Exportar Excel · '+mods.find(m=>m.id===modulo)?.l),
      h('div',{style:{background:'#f0fdf4',border:'1px solid #bbf7d0',borderRadius:12,padding:13,marginTop:12}},
        h('p',{style:{fontSize:12,color:'#166534',lineHeight:1.6}},
          'El Excel incluye todos los campos del módulo seleccionado con formato y colores. El archivo se descarga directamente en tu dispositivo.'
        )
      )
    )
  );
}
