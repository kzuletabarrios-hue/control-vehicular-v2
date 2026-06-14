# Control de Acceso y Operaciones CEDI R10

Versión mejorada con autenticación JWT, roles, migración de datos y modo offline.

---

## Novedades v2

- Login con email/contraseña y roles (admin, supervisor, operador, consulta)
- Refresh token automático — no se cierra sesión inesperadamente
- Captura de foto directamente desde la cámara del celular
- Modo offline — guarda en cola y sincroniza al recuperar conexión
- Botón "Duplicar registro" en flota — ahorra tiempo en rutas repetitivas
- Script de migración desde Google Sheets CSV
- Audit log — trazabilidad de quién modificó qué y cuándo

---

## Deploy en 4 pasos

### Paso 1 — Base de datos (Supabase)

```
1. Ejecutar database/schema.sql        (tablas originales)
2. Ejecutar database/auth_schema.sql   (usuarios, roles, auditoría)
```

Usuario inicial creado automáticamente:
- Email: admin@cedirex.com
- Contraseña: Admin2024!
- **Cambiar la contraseña al primer ingreso**

### Paso 2 — Migrar datos existentes

```bash
pip install psycopg2-binary pandas python-dotenv

# Crear carpeta y exportar Google Sheets
mkdir csv_exports
# Descargar cada hoja como CSV y colocar en csv_exports/

# Configurar base de datos
cp backend/.env.example backend/.env
# Editar .env con tu DATABASE_URL de Supabase

# Ejecutar migración
cd backend
python ../migrate.py
```

### Paso 3 — Backend (Render.com)

Variables de entorno requeridas:

| Variable              | Valor                                      |
|-----------------------|--------------------------------------------|
| DATABASE_URL          | Connection string de Supabase              |
| SECRET_KEY            | Cadena aleatoria larga (mínimo 32 chars)   |
| ACCESS_TOKEN_MINUTES  | 60 (recomendado)                           |
| REFRESH_TOKEN_DAYS    | 30 (recomendado)                           |

Comando de inicio: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Paso 4 — Frontend

Editar `frontend/index.html` línea ~18:
```js
const API_BASE = 'https://TU-APP.onrender.com/api';
```
Subir a Netlify arrastrando la carpeta `frontend/`.

---

## Roles y permisos

| Rol         | Crear | Editar | Eliminar | Exportar | Usuarios |
|-------------|-------|--------|----------|----------|----------|
| admin       | ✅    | ✅     | ✅       | ✅       | ✅       |
| supervisor  | ✅    | ✅     | ✗        | ✅       | ✗        |
| operador    | ✅    | ✅     | ✗        | ✗        | ✗        |
| consulta    | ✗     | ✗      | ✗        | ✅       | ✗        |

---

## Generar SECRET_KEY segura

```python
import secrets
print(secrets.token_hex(32))
```
