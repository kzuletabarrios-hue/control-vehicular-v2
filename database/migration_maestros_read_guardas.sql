-- Migración: dar acceso de lectura a maestros (tiendas/distribucion) a guarda_bodega y guarda_vehicular
-- Necesario para que el selector de tiendas cargue en el formulario de Flota Propia
-- Fecha: 2026-06-26

UPDATE roles
SET permisos = permisos || '{"maestros":["read"]}'::jsonb
WHERE nombre IN ('guarda_bodega','guarda_vehicular');
