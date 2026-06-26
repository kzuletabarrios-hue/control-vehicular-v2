# backend/main.py  (v2 — con autenticación)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    auth, flota, conductores, proveedores,
    control_acceso, visitantes, bd_maestros, export, dashboard, carga_masiva,
    rondas, novedades, busqueda, visita_vehicular, uploads
)

app = FastAPI(
    title="Control de Acceso y Operaciones CEDI R10",
    description="API con autenticación JWT y roles",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,           prefix="/api/auth",          tags=["Autenticación"])
app.include_router(flota.router,          prefix="/api/flota",         tags=["Flota Propia"])
app.include_router(conductores.router,    prefix="/api/conductores",   tags=["Conductores"])
app.include_router(proveedores.router,    prefix="/api/proveedores",   tags=["Proveedores"])
app.include_router(control_acceso.router, prefix="/api/control-acceso",tags=["Control Acceso"])
app.include_router(visitantes.router,     prefix="/api/visitantes",    tags=["Visitantes"])
app.include_router(bd_maestros.router,    prefix="/api/maestros",      tags=["Maestros BD"])
app.include_router(export.router,         prefix="/api/export",        tags=["Exportación Excel"])
app.include_router(dashboard.router,      prefix="/api/dashboard",     tags=["Dashboard"])
app.include_router(carga_masiva.router,   prefix="/api/carga",         tags=["Carga Masiva"])
app.include_router(rondas.router,         prefix="/api/rondas",        tags=["Rondas"])
app.include_router(novedades.router,      prefix="/api/novedades",     tags=["Novedades"])
app.include_router(busqueda.router,       prefix="/api/busqueda",      tags=["Búsqueda"])
app.include_router(visita_vehicular.router,prefix="/api/visita-vehicular",tags=["Visita Vehicular"])
app.include_router(uploads.router,          prefix="/api",               tags=["Uploads"])

@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "version": "2.1.0"}
