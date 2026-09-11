// ── APP HEADER ──
// Extraído de frontend/index.html (líneas 773-802, dentro de la sección
// "/* ── HEADER COMPONENT ── */" que arranca en la línea 708 y también
// contiene BusquedaSheet -- ver nota de desviación en shell/BusquedaSheet.js
// sobre por qué se separan en dos módulos). Contenido idéntico al original:
// el código viejo en index.html NO fue tocado ni borrado (ver notas de la
// Fase 2 del plan de migración) -- este módulo es una copia autocontenida,
// lista para que la Fase 6 lo importe cuando quede conectado vía
// <script type="module">.
//
// Nota sobre el rol del usuario y la navegación (regla 7 del encargo): en
// el monolito, AppHeader NO decide qué módulos de navegación mostrar según
// el rol -- ese cálculo (`navItems`, con el ternario por `user.rol` y los
// permisos granulares vía `puede(user,...)`) vive enteramente en App() root
// (línea ~6482 en adelante) y se renderiza en un <nav> separado, fuera de
// AppHeader. AppHeader solo usa `user` para el avatar/iniciales y para
// abrir PerfilSheet; y usa `page` únicamente para el título (titleMap). Se
// replica exactamente esa división de responsabilidades, sin inventar
// lógica de rol/nav aquí -- App() root (fuera del alcance de esta fase,
// pendiente para la Fase 6) sigue siendo quien decide navItems.

import { api } from '../core/api-client.js';
import { getRefresh, clearAuth } from '../core/auth-store.js';
import { Ico } from '../core/icons.js';
import { initials } from '../core/utils.js';
import { BusquedaSheet } from './BusquedaSheet.js';
import { PerfilSheet } from './PerfilSheet.js';

const { useState } = React;
const h = React.createElement;

export function AppHeader({user,page,setPage,online,offlineQueue,onAbrirFlota}){
  const [perfilOpen,setPerfilOpen] = useState(false);
  const [buscarOpen,setBuscarOpen] = useState(false);
  const titleMap = {home:'Inicio',flota:'Flota Propia',prov:'Proveedores',acceso:'Control Acceso',visit:'Visitantes',visitavh:'Visita Vehicular',bd:'Base de Datos',reg:'Registros',carga:'Carga Masiva'};

  const logout = async () => {
    try{ await api.post('/auth/logout',{refresh_token:getRefresh()}); }catch(e){}
    clearAuth(); window.location.reload();
  };

  return h('div',{className:'header'},
    h('div',{className:'header-inner'},
      h('div',{className:'header-brand'},
        h('h1',null,titleMap[page]||'CEDI R10'),
        h('span',null,'CEDI R10')
      ),
      h('div',{className:'header-right'},
        !online&&h('span',{className:'offline-badge'},h(Ico,{n:'wifiOff',s:11}),' Sin red'),
        offlineQueue>0&&h('span',{className:'offline-badge',style:{background:'rgba(245,158,11,.25)',borderColor:'rgba(245,158,11,.5)'}},`${offlineQueue} pendientes`),
        h('button',{className:'btn-icon',title:'Buscar ingreso',onClick:()=>setBuscarOpen(true)},h(Ico,{n:'search',s:15})),
        h('div',{className:'user-chip',onClick:()=>setPerfilOpen(true)},
          h('div',{className:'user-avatar'},initials(user?.nombre||'')),
          h('span',{className:'user-name'},user?.nombre?.split(' ')[0]||'Usuario')
        )
      )
    ),
    buscarOpen&&h(BusquedaSheet,{onClose:()=>setBuscarOpen(false),onAbrirFlota}),
    perfilOpen&&h(PerfilSheet,{user,onClose:()=>setPerfilOpen(false),onLogout:()=>{setPerfilOpen(false);logout();}})
  );
}
