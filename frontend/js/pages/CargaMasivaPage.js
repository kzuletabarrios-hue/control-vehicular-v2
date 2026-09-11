// ── CARGA MASIVA PAGE ──
// Extraído de frontend/index.html (líneas 1596-1762, función
// CargaMasivaPage del <script> monolítico, entre el comentario
// "CARGA MASIVA" y el comentario "REGISTROS / EXPORT PAGE"). Contenido
// idéntico al original: el código viejo en index.html NO fue tocado ni
// borrado -- este módulo es una copia autocontenida, lista para que la
// Fase 6 lo importe cuando quede conectado vía <script type="module">.
//
// Importa Ico (core/icons.js) y api (core/api-client.js). No depende de
// ningún componente de shared/ -- las 4 pestañas (conductores, vehículos,
// empleados, tiendas) y su lógica de plantilla/importación son exclusivas
// de esta página, por eso permanecen aquí y no en shared/.
//
// Depende de window.XLSX (librería SheetJS cargada por <script> de CDN en
// el <head> de index.html) y de React como global UMD, igual que en el
// monolito original -- no se importa como módulo ES porque React 18 se
// sirve como build UMD, no ESM.

import { Ico } from '../core/icons.js';
import { api } from '../core/api-client.js';

const { useState, useEffect } = React;
const h = React.createElement;

export function CargaMasivaPage(){
  const TABS = [
    {
      id:'conductores', label:'Conductores',
      cols:['codigo','conductor','n_cedula','celular','tipo'],
      headers:['Código','Nombre','Cédula','Celular','Tipo (Propio/Tercero)'],
      endpoint:'/carga/conductores',
      required:['conductor'],
    },
    {
      id:'vehiculos', label:'Vehículos',
      cols:['placa','marca','modelo','color','anio','tipo','capacidad'],
      headers:['Placa','Marca','Modelo','Color','Año','Tipo','Capacidad'],
      endpoint:'/carga/vehiculos',
      required:['placa'],
    },
    {
      id:'empleados', label:'Empleados',
      cols:['cedula','nombre','contratista','estado'],
      headers:['Cédula','Nombre','Contratista','Estado (ACTIVO/INACTIVO)'],
      endpoint:'/carga/empleados',
      required:['cedula','nombre'],
    },
    {
      id:'tiendas', label:'Tiendas',
      cols:['codigo','nombre','direccion'],
      headers:['COD','Name','Dirección'],
      endpoint:'/carga/tiendas',
      required:['nombre'],
    },
  ];

  const [tab, setTab]       = useState('conductores');
  const [rows, setRows]     = useState([]);
  const [fileName, setFile] = useState('');
  const [loading, setLoad]  = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr]       = useState('');

  const tabDef = TABS.find(t=>t.id===tab);

  useEffect(()=>{ setRows([]); setFile(''); setResult(null); setErr(''); }, [tab]);

  const downloadTemplate = () => {
    if(!window.XLSX){ setErr('Librería Excel no cargada aún, intenta de nuevo'); return; }
    const wb = window.XLSX.utils.book_new();
    const ws = window.XLSX.utils.aoa_to_sheet([tabDef.headers]);
    ws['!cols'] = tabDef.headers.map(()=>({wch:20}));
    window.XLSX.utils.book_append_sheet(wb, ws, tabDef.label);
    window.XLSX.writeFile(wb, `plantilla_${tabDef.id}.xlsx`);
  };

  const handleFile = e => {
    const file = e.target.files[0];
    if(!file) return;
    if(!window.XLSX){ setErr('Librería Excel no cargada, recarga la página'); return; }
    setFile(file.name); setResult(null); setErr('');
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const wb = window.XLSX.read(ev.target.result, {type:'array'});
        const ws = wb.Sheets[wb.SheetNames[0]];
        const raw = window.XLSX.utils.sheet_to_json(ws, {defval:''});
        const normalized = raw.map(row=>{
          const r = {};
          tabDef.cols.forEach((col,i)=>{
            const variants = [col, tabDef.headers[i]];
            let val = '';
            for(const k of Object.keys(row)){
              if(variants.some(v=>v.toLowerCase()===k.toLowerCase().trim())){
                val = row[k]; break;
              }
            }
            r[col] = val;
          });
          return r;
        }).filter(r=>tabDef.required.some(c=>String(r[c]||'').trim()!==''));
        setRows(normalized);
        if(normalized.length===0) setErr('No se encontraron filas válidas. Revisa que las columnas coincidan con la plantilla.');
      } catch(ex){ setErr('Error al leer archivo: '+ex.message); }
    };
    reader.readAsArrayBuffer(file);
    e.target.value='';
  };

  const handleImport = async()=>{
    if(!rows.length) return setErr('No hay datos para importar');
    setLoad(true); setErr(''); setResult(null);
    try {
      const res = await api.post(tabDef.endpoint, {filas:rows});
      setResult(res);
      setRows([]); setFile('');
    } catch(ex){
      let m=ex.message||'Error'; try{m=JSON.parse(m).detail||m;}catch{}
      setErr(m);
    } finally { setLoad(false); }
  };

  return h('div',{className:'scroll-body'},
    h('div',{className:'pad'},
      h('div',{style:{display:'flex',gap:6,marginBottom:16,overflowX:'auto',WebkitOverflowScrolling:'touch'}},
        TABS.map(t=>h('button',{key:t.id,onClick:()=>setTab(t.id),
          style:{flexShrink:0,padding:'8px 12px',borderRadius:8,fontSize:12,fontWeight:700,border:'1.5px solid',cursor:'pointer',fontFamily:'inherit',whiteSpace:'nowrap',
            background:tab===t.id?'var(--navy2)':'none',
            color:tab===t.id?'#fff':'var(--slate)',
            borderColor:tab===t.id?'var(--navy2)':'var(--border)'}
        },t.label))
      ),

      h('div',{className:'fcard',style:{marginBottom:12}},
        h('p',{className:'sec-ttl',style:{marginBottom:8}},'1 · Descarga la plantilla'),
        h('button',{className:'btn-outline',onClick:downloadTemplate},
          h(Ico,{n:'download',s:14}),`Plantilla ${tabDef.label}`
        ),
        h('p',{style:{fontSize:10,color:'var(--slate)',marginTop:6}},
          `Columnas: ${tabDef.headers.join(' · ')}`
        )
      ),

      h('div',{className:'fcard',style:{marginBottom:12}},
        h('p',{className:'sec-ttl',style:{marginBottom:8}},'2 · Sube el archivo'),
        h('label',{className:'upload-zone'},
          h('input',{type:'file',accept:'.xlsx,.xls,.csv',style:{display:'none'},onChange:handleFile}),
          h(Ico,{n:'upload',s:28,c:'upload-ico'}),
          h('p',null, fileName||'Toca para seleccionar archivo'),
          h('span',null,'.xlsx · .xls · .csv')
        )
      ),

      err&&h('div',{className:'alert-err',style:{marginBottom:12}},h(Ico,{n:'alert',s:14}),err),

      rows.length>0&&h('div',{className:'fcard',style:{marginBottom:12}},
        h('p',{className:'sec-ttl',style:{marginBottom:8}},`3 · Vista previa — ${rows.length} registros`),
        h('div',{style:{overflowX:'auto',marginBottom:10}},
          h('table',{className:'preview-table'},
            h('thead',null,h('tr',null,tabDef.cols.map(c=>h('th',{key:c},c)))),
            h('tbody',null,
              rows.slice(0,8).map((r,i)=>h('tr',{key:i},tabDef.cols.map(c=>h('td',{key:c},String(r[c]??'')))))
            )
          )
        ),
        rows.length>8&&h('p',{style:{fontSize:10,color:'var(--slate)',marginBottom:8}},`...y ${rows.length-8} registros más`),
        h('button',{
          className:'btn-primary',style:{width:'100%'},
          onClick:handleImport,disabled:loading
        }, loading?'Importando...':h('span',{style:{display:'flex',alignItems:'center',gap:6,justifyContent:'center'}},
          h(Ico,{n:'upload',s:15}),`Importar ${rows.length} registros`
        ))
      ),

      result&&h('div',{className:'fcard'},
        h('p',{className:'sec-ttl',style:{marginBottom:12}},'Resultado'),
        h('div',{className:'stat-chips',style:{marginBottom:result.errores?.length?12:0}},
          h('div',{className:'stat-chip green'},h('span',null,result.insertados),h('small',null,'Nuevos')),
          h('div',{className:'stat-chip blue'},h('span',null,result.actualizados),h('small',null,'Actualizados')),
          result.errores?.length>0&&h('div',{className:'stat-chip red'},h('span',null,result.errores.length),h('small',null,'Errores')),
        ),
        result.errores?.length>0&&h('div',null,
          result.errores.slice(0,5).map((e,i)=>
            h('p',{key:i,style:{fontSize:11,color:'var(--red)',marginBottom:2}},`Fila ${e.fila}: ${e.error}`)
          ),
          result.errores.length>5&&h('p',{style:{fontSize:10,color:'var(--slate)'}},`...y ${result.errores.length-5} errores más`)
        )
      )
    )
  );
}
