// ── APP (root) ──
// Extraído de frontend/index.html (líneas 6413-6551, función App() del
// <script> monolítico -- el nav por rol, el switch de página vía
// pageContent[page], el manejo de sesión/online/offline-queue y el atajo
// ?ingreso_proveedor= para ProveedorAutorregistroPage). Contenido idéntico
// al original: ningún hook se reordenó, ningún ternario de navItems se
// tocó, el mapeo página→componente es el mismo que en el monolito.
//
// Importa getUser/getQueue/addToQueue/clearQueue (core/auth-store.js),
// puede (core/utils.js), useVisibilityPolling (core/hooks.js), api
// (core/api-client.js), Ico (core/icons.js), AppHeader (shell/) y
// BtnNovedad (shared/), además de LoginPage (shell/) y todas las páginas de
// pages/ que aparecen en pageContent{} o en el atajo de autorregistro.
//
// Depende de React como global UMD (cargado por <script> de CDN en el
// <head> de index.html), igual que en el monolito original -- no se
// importa como módulo ES porque React 18 se sirve como build UMD, no ESM.

import { Ico } from './core/icons.js';
import { api } from './core/api-client.js';
import { getUser, getQueue, addToQueue, clearQueue } from './core/auth-store.js';
import { puede } from './core/utils.js';
import { useVisibilityPolling } from './core/hooks.js';
import { AppHeader } from './shell/AppHeader.js';
import { LoginPage } from './shell/LoginPage.js';
import { BtnNovedad } from './shared/BtnNovedad.js';
import { HomePage } from './pages/HomePage.js';
import { FlotaPage } from './pages/FlotaPage.js';
import { ProveedoresPage } from './pages/proveedores/index.js';
import { VisitaVehicularPage } from './pages/VisitaVehicularPage.js';
import { AccesoPage } from './pages/AccesoPage.js';
import { VisitantesPage } from './pages/VisitantesPage.js';
import { ItemAccesoPage } from './pages/ItemAccesoPage.js';
import { BaseDatosPage } from './pages/basedatos/index.js';
import { CargaMasivaPage } from './pages/CargaMasivaPage.js';
import { RegistrosPage } from './pages/RegistrosPage.js';
import { RondaPage } from './pages/RondaPage.js';
import { NovedadesPage } from './pages/NovedadesPage.js';
import { RondaPanelPage } from './pages/RondaPanelPage.js';
import { MuellesPage } from './pages/muelles/index.js';
import { CitasPage } from './pages/CitasPage.js';
import { ProveedorAutorregistroPage } from './pages/ProveedorAutorregistroPage.js';

const { useState, useEffect, useCallback } = React;
const h = React.createElement;

export function App(){
  const qs = new URLSearchParams(window.location.search);
  if(qs.get('ingreso_proveedor')!=null) return h(ProveedorAutorregistroPage,{token:qs.get('token')});

  const [user,setUser]       = useState(getUser);
  const [page,setPageState]  = useState('home');
  const [online,setOnline]   = useState(navigator.onLine);
  const [queue,setQueue]     = useState(getQueue);
  const [openFlotaId,setOpenFlotaId] = useState(null);

  const navigate = (newPage)=>{
    if(newPage===page) return;
    window.history.pushState({page:newPage},'','');
    setPageState(newPage);
  };

  useEffect(()=>{
    const on  = ()=>setOnline(true);
    const off = ()=>setOnline(false);
    window.addEventListener('online',on);
    window.addEventListener('offline',off);
    return ()=>{ window.removeEventListener('online',on); window.removeEventListener('offline',off); };
  },[]);

  useEffect(()=>{
    window.history.replaceState({page:'home'},'','');
    const onPop = e=>setPageState(e.state?.page||'home');
    window.addEventListener('popstate',onPop);
    return ()=>window.removeEventListener('popstate',onPop);
  },[]);

  // Mantiene sincronizados nombre/rol con la BD: si a este usuario le
  // cambiaron el rol después de iniciar sesión, el localStorage quedaría
  // con datos viejos y el menú mostraría módulos que el backend ya no
  // le permite, causando 403 ("Error cargando datos") en esas pestañas.
  const syncUser = useCallback(()=>{
    api.get('/auth/me').then(u=>{
      if(!u) return;
      setUser(prev=>{
        const merged = {...prev,...u};
        localStorage.setItem('cv_user',JSON.stringify(merged));
        return merged;
      });
    }).catch(()=>{});
  },[]);
  // Se mantiene en 5 min (no es dato operativo urgente) pero también se
  // pausa en background: si la sesión está oculta/bloqueada no hay 403 que
  // prevenir en ese momento, así que no vale la pena seguir consultando.
  useVisibilityPolling(syncUser, 300000, [user?.id], !!user);

  const addOffline = (item)=>{ addToQueue(item); setQueue(getQueue()); };

  const syncQueue = async()=>{
    const q = getQueue();
    if(!q.length||!online) return;
    let ok=0,fail=0;
    for(const item of q){
      try{
        if(item.method==='POST') await api.post(item.endpoint,item.body);
        else if(item.method==='PUT') await api.put(item.endpoint,item.body);
        ok++;
      }catch(e){fail++;}
    }
    clearQueue(); setQueue([]);
    alert(`Sincronización: ${ok} enviados, ${fail} con error.`);
  };

  if(!user) return h(LoginPage,{onLogin:(u)=>setUser(u)});

  const rol = user?.rol||'';
  const navItems =
    rol==='guarda_bodega'        ? [{id:'home',label:'Inicio',icon:'home'},{id:'flota',label:'Flota',icon:'truck'},{id:'prov',label:'Proveedores',icon:'package'},{id:'visitavh',label:'Visita Vh.',icon:'truck'}]
    :rol==='guarda_peatonal'     ? [{id:'home',label:'Inicio',icon:'home'},{id:'acceso',label:'Acceso',icon:'userCheck'},{id:'visit',label:'Visitas',icon:'users'},{id:'sust',label:'Sust.',icon:'alert'},{id:'herr',label:'Herram.',icon:'key'}]
    :rol==='guarda_vehicular'    ? [{id:'home',label:'Inicio',icon:'home'},{id:'flota',label:'Flota',icon:'truck'},{id:'prov',label:'Proveedores',icon:'package'},{id:'visitavh',label:'Visita Vh.',icon:'truck'},{id:'visit',label:'Visitas',icon:'users'}]
    :rol==='recorredor_externo'  ? [{id:'home',label:'Inicio',icon:'home'},{id:'ronda',label:'Ronda',icon:'mapPin'},{id:'novedades',label:'Novedades',icon:'bell'}]
    :rol==='coordinador'         ? [{id:'home',label:'Inicio',icon:'home'},{id:'flota',label:'Flota',icon:'truck'},{id:'prov',label:'Proveedores',icon:'package'},{id:'acceso',label:'Acceso',icon:'userCheck'},{id:'visit',label:'Visitas',icon:'users'}]
    :[
      {id:'home',  label:'Inicio',  icon:'home'},
      {id:'flota', label:'Flota',   icon:'truck'},
      {id:'acceso',label:'Acceso',  icon:'userCheck'},
      {id:'visit', label:'Visitas', icon:'users'},
      {id:'reg',   label:'Reportes',icon:'fileText'},
    ];

  // Módulo Muelles (Fase 2, solo lectura): a diferencia del resto de
  // navItems -- fijos por rol en el bloque de arriba, que NO se toca --
  // este se agrega dinámicamente para cualquier rol con permiso
  // muelles:read (hoy: coordinador y guarda_bodega), sin tener que
  // enumerar roles a mano en cada rama del ternario.
  if(puede(user,'muelles','read') && !navItems.some(it=>it.id==='muelles')){
    navItems.push({id:'muelles',label:'Muelles',icon:'mapPin'});
  }

  // Módulo Citas (Fase 3, solo lectura): mismo patrón que Muelles arriba --
  // se agrega dinámicamente para cualquier rol con permiso citas:read, sin
  // enumerar roles a mano en el ternario fijo de navItems.
  if(puede(user,'citas','read') && !navItems.some(it=>it.id==='citas')){
    navItems.push({id:'citas',label:'Citas',icon:'calendar'});
  }

  const pageContent = {
    home:   h(HomePage,{setPage:navigate,user}),
    flota:  h(FlotaPage,{user,online,addOffline,openId:openFlotaId,onOpened:()=>setOpenFlotaId(null)}),
    prov:   h(ProveedoresPage,{user,online,addOffline}),
    visitavh: h(VisitaVehicularPage,{user,online,addOffline}),
    acceso: h(AccesoPage,{user,online,addOffline}),
    visit:  h(VisitantesPage,{user,online,addOffline}),
    sust:   h(ItemAccesoPage,{tipo:'sustancias',user}),
    herr:   h(ItemAccesoPage,{tipo:'herramientas',user}),
    bd:        h(BaseDatosPage,{user}),
    carga:     h(CargaMasivaPage,null),
    reg:       h(RegistrosPage,null),
    ronda:     h(RondaPage,{user}),
    novedades: h(NovedadesPage,{user}),
    rondapanel: h(RondaPanelPage,{user}),
    muelles: h(MuellesPage,{user}),
    citas:   h(CitasPage,{user}),
  };

  return h('div',{className:'app-wrap'},
    h('div',{className:'app-main'},
      h(AppHeader,{user,page,setPage:navigate,online,offlineQueue:queue.length,onAbrirFlota:(id)=>{setOpenFlotaId(id);navigate('flota');}}),
      queue.length>0&&online&&h('div',{className:'queue-banner'},
        h(Ico,{n:'wifi',s:14}),
        h('p',null,`${queue.length} registros pendientes de sincronizar`),
        h('button',{onClick:syncQueue},'Sincronizar ahora')
      ),
      pageContent[page]||pageContent['home'],
      h(BtnNovedad,{user,moduloActual:page})
    ),
    h('nav',{className:'bnav'},
      navItems.map(it=>h('button',{key:it.id,className:`nav-btn ${page===it.id?'act':''}`,onClick:()=>navigate(it.id)},
        page===it.id&&h('div',{className:'nav-dot'}),
        h(Ico,{n:it.icon,s:22}),
        h('span',null,it.label)
      ))
    )
  );
}
