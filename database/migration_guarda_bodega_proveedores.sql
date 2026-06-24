-- Migración: dar acceso de lectura y escritura en proveedores al rol guarda_bodega
-- Ejecutar en la base de datos PostgreSQL del proyecto
-- Fecha: 2026-06-16

UPDATE roles
SET permisos = jsonb_set(
    permisos,
    '{proveedores}',
    '["read","write"]'::jsonb
)
WHERE nombre = 'guarda_bodega';
