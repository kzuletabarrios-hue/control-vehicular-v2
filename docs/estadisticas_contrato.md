# Contrato de datos — Pestaña "Estadísticas" (dashboard-estadisticas)

Autor: Jorge Peña (Arquitecto de BD). Fecha: 2026-09-26.
Validado contra la BD local de pruebas (`bash scripts/dev_test_db.sh reset` +
datos ficticios insertados dentro de una transacción con `ROLLBACK`, incluido
cruce de medianoche). No se tocó producción ni `DATABASE_URL` real en ningún
momento.

## 0. Decisión de arquitectura: UN solo endpoint

`GET /dashboard/estadisticas?fecha_desde=YYYY-MM-DD&fecha_hasta=YYYY-MM-DD`

Devuelve las 6 secciones (A–F) en un único JSON. Razones:

- La pestaña se carga **bajo demanda** al abrir la pestaña (no hay polling),
  así que el costo de "una respuesta más pesada" se paga una sola vez, no en
  cada refresco.
- Todas las tarjetas/gráficas de una misma pestaña deben mostrar **el mismo
  rango de fechas coherente** — separarlo en 6 llamadas obliga al frontend a
  orquestar 6 fetches en paralelo y a manejar 6 estados de loading/error
  independientes para una sola pantalla, sin ningún beneficio real de
  rendimiento a estos volúmenes.
- Mismo patrón ya usado y probado en este archivo: `/resumen` ya arma "1 query
  para todos los conteos en lugar de 10 queries separadas". Este endpoint
  sigue el mismo espíritu, con 6 queries (una por sección) en vez de 10, cada
  una ya indexada.
- Medido contra la BD local con datos de prueba: cada query individual usa
  `Index Scan`/`Index Only Scan` o un `Seq Scan` de costo ~11 (ver sección 4)
  — al volumen real de producción (9.095 / 4.326 / 3.951 / 983 filas) las 6
  queries combinadas corren en milisegundos. No hay motivo de rendimiento
  para dividir el endpoint.

**Único caso en que recomendaría separar**: si a futuro se agrega una
sub-pestaña "detalle por placa" con drill-down bajo demanda (ej. históricos de
una placa específica) — eso sí debe ser su propio endpoint con su propio
filtro, no parte de esta carga inicial.

Si el volumen crece 20-30x (flota/proveedores por encima de ~100.000 filas)
y el endpoint combinado empieza a sentirse lento en la pestaña, el primer
candidato a separar es la sección B (tiempo en muelle), por ser la única que
hace aritmética de fechas fila por fila sin poder apoyarse en un índice de
rango sobre la expresión combinada.

### Validaciones de entrada (aplican a todo el endpoint)

- `fecha_desde` y `fecha_hasta` opcionales. Si faltan ambos: default a los
  últimos 30 días en **zona horaria Colombia** — mismo patrón exacto que
  `/resumen` (`_BOG = timezone(timedelta(hours=-5))`, `datetime.now(_BOG).date()`).
  No hay import de `zoneinfo`/tabla de horario de verano en el repo: Bogotá
  no tiene horario de verano, así que el offset fijo `-5` ya usado en
  `dashboard.py`/`muelles.py` es correcto y no hay que "mejorarlo" con
  `zoneinfo` en esta tarea (mantener consistencia con el resto del router).
- Si solo llega uno de los dos, se aplica el mismo criterio: fecha faltante
  se completa a 30 días antes de `fecha_hasta` u hoy si falta `fecha_desde`,
  y a hoy si falta `fecha_hasta`.
- `fecha_desde > fecha_hasta` → `400 Bad Request` (`"fecha_desde no puede ser mayor a fecha_hasta"`).
- Rango máximo **366 días** (cubre año + bisiesto): si `fecha_hasta - fecha_desde > 366` → `400 Bad Request`
  (`"El rango máximo permitido es de 366 días"`). Evita que alguien pida
  "desde 2020" y fuerce un `generate_series` de miles de días con recálculo
  fila por fila en la sección B/D.
- Formato inválido (no parseable como fecha) → `400 Bad Request`.
- Permisos: reutiliza `require_permiso("dashboard", "read")`, exactamente
  igual que `/resumen` y `/tiempo-autorregistro`. Verificado contra
  `supabase/migrations/20260601101430_auth_schema.sql` y
  `20260804110000_alta_formal_coordinador_retroactivo.sql`: **admin,
  supervisor, operador y coordinador ya tienen `"dashboard":["read"]`** —
  no hace falta ninguna migración de permisos nueva para exponer este
  endpoint a los 4 roles pedidos.

### Convención de bind params (SQLAlchemy `text()`)

Sigo el patrón **real y exacto** de `dashboard.py` (no una interpretación
literal del nombre): el parámetro de la función/query string es
`fecha_desde`/`fecha_hasta` (igual que `tiempo_autorregistro`), pero el bind
param dentro del SQL con `text()` es `:desde` / `:hasta` — exactamente como
en `tiempo_autorregistro` (líneas 268-277 de `dashboard.py`). Lo dejo explícito
para que no haya ambigüedad entre "`:fecha_desde`/`:fecha_hasta`" y
"`:desde`/`:hasta`": uso el segundo, por ser el que el archivo ya usa hoy.

```python
from datetime import date, datetime, timedelta, timezone
_BOG = timezone(timedelta(hours=-5))

RANGO_MAX_DIAS = 366

def _resolver_rango(fecha_desde: str | None, fecha_hasta: str | None) -> tuple[date, date]:
    hoy = datetime.now(_BOG).date()
    try:
        hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else hoy
        desde = date.fromisoformat(fecha_desde) if fecha_desde else (hasta - timedelta(days=30))
    except ValueError:
        raise HTTPException(400, "Formato de fecha inválido, use YYYY-MM-DD")
    if desde > hasta:
        raise HTTPException(400, "fecha_desde no puede ser mayor a fecha_hasta")
    if (hasta - desde).days > RANGO_MAX_DIAS:
        raise HTTPException(400, f"El rango máximo permitido es de {RANGO_MAX_DIAS} días")
    return desde, hasta
```

---

## 1. Hallazgo de calidad de datos que condiciona la sección B (léase antes)

Antes de decidir la definición de "tiempo en muelle" de proveedores, revisé
`backend/routers/proveedores.py` y `backend/routers/muelles.py` (código real,
no solo el nombre de las columnas):

- `proveedores.hora_muelle_asignado` (migración
  `20260811110030_proveedores_hora_muelle_asignado_column.sql`) se pobló **una
  sola vez por backfill** (`hora_muelle_asignado = hora_ingreso` para filas
  con `muelle_descargue` no vacío) el día de esa migración. **Ningún endpoint
  la vuelve a escribir de ahí en adelante**: `confirmar_autorregistro` (línea
  ~1386 de `proveedores.py`), que es el que asigna `muelle_descargue` y fija
  `hora_ingreso_confirmado`, nunca toca `hora_muelle_asignado`. Es decir, para
  cualquier proveedor confirmado a muelle **después** del 2026-08-11, esta
  columna queda `NULL` — es una columna efectivamente muerta para datos
  nuevos, pese a que su migración documenta la intención contraria.
- `proveedores.hora_muelle_liberado` sí se escribe en tiempo real, pero solo
  si el guarda usa el botón "Liberar muelle" (`PUT /proveedores/{id}/liberar-muelle`),
  un paso **independiente y opcional** de "Registrar salida" (el propio
  docstring del endpoint lo dice: el vehículo puede desocupar el muelle y
  seguir un rato más dentro del CEDI antes de salir). No hay garantía de que
  todo viaje completado tenga este campo poblado.

**Conclusión**: usar `hora_muelle_asignado → hora_muelle_liberado` para un
promedio histórico agregado subestimaría sistemáticamente la muestra (numerador
NULL para casi todo lo posterior a agosto) y mezclaría dos poblaciones no
comparables (backfill congelado vs. eventos reales esporádicos).

**Definición elegida para la sección B**: `hora_ingreso_confirmado` (con
`hora_ingreso` como fallback — mismo patrón exacto que ya usa
`muelles.py` línea 264: `base_hora = r.hora_ingreso_confirmado or r.hora_ingreso`)
→ `hora_salida`, **solo sobre `estado_confirmacion = 'confirmado'` y
`hora_salida IS NOT NULL`**. Es exactamente la contraparte "cerrada" del
criterio de "en muelle" que ya usan `dashboard.py` (`estado_confirmacion =
'confirmado' AND hora_salida IS NULL`) y `muelles.py`/`proveedores.py`
(mismo filtro) para "sigue en muelle" — así que Inicio, Muelles y esta nueva
pestaña de Estadísticas nunca se van a contradecir sobre qué es "estar en
muelle". Es, en sentido estricto, "tiempo dentro del CEDI desde que se
confirma su ingreso a muelle hasta que registra salida por portería" (incluye
cualquier tramo de logística inversa, cola de salida, etc.), no
milimétricamente "tiempo físico ocupando el andén" — pero es la única
definición con cobertura de datos consistente hoy.

**Recomendación a María/Alejandro (fuera de esta entrega, para considerar
después)**: si el negocio quiere de verdad "tiempo ocupando el andén físico",
hay que corregir primero `confirmar_autorregistro` para que también escriba
`hora_muelle_asignado`, y volver `hora_muelle_liberado` un paso obligatorio
antes de `hora_salida`. Ya con eso, la query de la sección B se cambia a
`hora_muelle_asignado → hora_muelle_liberado` sin ningún otro ajuste (queda
documentada como alternativa comentada en la query B más abajo).

---

## 1.5. Corrección de María (backend) al pasar estas queries a `text()`

Al implementar el endpoint (2026-09-26) encontré un error real al ejecutar
las 4 queries de este documento que usan
`generate_series(:desde::date, :hasta::date, ...)` (secciones A, B-por_día,
E, F-por_día) tal cual estaban escritas: SQLAlchemy lanzaba
`ProgrammingError: error de sintaxis en o cerca de ":"` **solo** en esa
línea, mientras que los mismos bind params `:desde`/`:hasta` en las
cláusulas `WHERE ... BETWEEN :desde AND :hasta` de las mismas queries se
compilaban bien.

Causa: el compilador de `TextClause` de SQLAlchemy usa una regex que
reconoce `:nombre` como bind param solo si el carácter siguiente **no**
es otro `:` (`(?<![:\w\\]):(\w+)(?!:)`) -- es un guardrail deliberado de
SQLAlchemy para no confundirse con dos bind params pegados, pero como
efecto secundario rompe exactamente el patrón `:parametro::tipo` que se
usa aquí para castear un bind param a `date` en Postgres. Con
`:desde::date`, SQLAlchemy no reconoce `:desde` como bind param en
absoluto y lo deja como texto literal, que Postgres no puede parsear.

Corrección aplicada en `backend/routers/dashboard.py`: envolver el bind
param entre paréntesis antes del cast, `(:desde)::date` /
`(:hasta)::date`, en las 4 queries que lo necesitan. El paréntesis rompe
la adyacencia `:nombre::` que dispara el guardrail de SQLAlchemy, sin
cambiar el resultado del cast en Postgres. Verificado con `EXPLAIN` +
ejecución real contra la BD local de pruebas: mismo plan, mismo
resultado, ya no hay error de sintaxis.

No aplica a las demás queries de este documento (B-global, D-global,
D-top_placas, F-global) porque ninguna castea un bind param con `::`
directamente -- solo comparan `fecha BETWEEN :desde AND :hasta`, patrón
que sí compila bien.

Si Laura o Diego copian estas queries directamente de este documento
para otra prueba (ej. un script `psql` suelto fuera de SQLAlchemy), el
`:desde::date` original SÍ funciona ahí (psql interpreta `:desde` como
variable de `psql`, no como bind param de SQLAlchemy) -- el ajuste de
paréntesis solo es necesario dentro de `sqlalchemy.text()`.

---

## 2. Queries SQL (SQLAlchemy `text()`, bind params `:desde` / `:hasta`)

Todas reciben `{"desde": desde.isoformat(), "hasta": hasta.isoformat()}` (o los
objetos `date` directamente; SQLAlchemy los serializa igual).

### A. Tendencia diaria por módulo

```sql
WITH serie AS (
    SELECT generate_series(:desde::date, :hasta::date, interval '1 day')::date AS dia
),
flota_d AS (
    SELECT fecha AS dia, COUNT(*) AS n
    FROM flota_propia
    WHERE fecha BETWEEN :desde AND :hasta
    GROUP BY fecha
),
prov_d AS (
    SELECT fecha AS dia, COUNT(*) AS n
    FROM proveedores
    WHERE fecha BETWEEN :desde AND :hasta
    GROUP BY fecha
),
acceso_d AS (
    -- anulado = FALSE: misma convención que el resto del repo
    -- (idx_ca_activos_fecha ya cubre exactamente fecha+anulado=false)
    SELECT fecha AS dia, COUNT(*) AS n
    FROM control_acceso
    WHERE fecha BETWEEN :desde AND :hasta AND anulado = FALSE
    GROUP BY fecha
),
visitantes_d AS (
    SELECT fecha AS dia, COUNT(*) AS n
    FROM visitantes
    WHERE fecha BETWEEN :desde AND :hasta
    GROUP BY fecha
)
SELECT
    s.dia,
    COALESCE(f.n, 0) AS flota,
    COALESCE(p.n, 0) AS proveedores,
    COALESCE(a.n, 0) AS control_acceso,
    COALESCE(v.n, 0) AS visitantes
FROM serie s
LEFT JOIN flota_d      f ON f.dia = s.dia
LEFT JOIN prov_d       p ON p.dia = s.dia
LEFT JOIN acceso_d     a ON a.dia = s.dia
LEFT JOIN visitantes_d v ON v.dia = s.dia
ORDER BY s.dia;
```

### B. Tiempo en muelle de proveedores (global + por día)

Global:

```sql
WITH base AS (
    SELECT
        p.id,
        (p.fecha + COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso)) AS ingreso_ts,
        (COALESCE(p.fecha_salida, p.fecha) + p.hora_salida)             AS salida_ts_base
    FROM proveedores p
    WHERE p.fecha BETWEEN :desde AND :hasta
      AND p.estado_confirmacion = 'confirmado'
      AND p.hora_salida IS NOT NULL
      AND COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso) IS NOT NULL
),
calc AS (
    SELECT
        id, ingreso_ts,
        -- Cruce de medianoche: si fecha_salida vino NULL (hueco de dato) y la
        -- hora de salida es "menor" que la de ingreso, se infiere +1 día.
        -- Si fecha_salida SÍ está poblada, ya trae la fecha real y no hace
        -- falta inferir nada (puede o no cruzar medianoche, da igual).
        CASE WHEN salida_ts_base < ingreso_ts
             THEN salida_ts_base + interval '1 day'
             ELSE salida_ts_base
        END AS salida_ts
    FROM base
),
minutos AS (
    SELECT id, EXTRACT(EPOCH FROM (salida_ts - ingreso_ts)) / 60.0 AS min
    FROM calc
)
SELECT
    ROUND(AVG(min)::numeric, 1)                                        AS promedio_minutos,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min))::numeric, 1) AS mediana_minutos,
    COUNT(*)                                                           AS n_validos
FROM minutos
-- Umbral de exclusión: <=0 (dato corrupto/orden invertido) y >1440 min (24h,
-- ningún proveedor debería seguir "confirmado sin salida" más de un día
-- completo; si ocurre es un olvido de registrar salida, no una medición real).
WHERE min > 0 AND min <= 1440;
```

Por día (mismo cálculo, `GROUP BY` la fecha de ingreso, relleno de días sin
datos con `promedio_minutos`/`mediana_minutos = null` y `n_validos = 0` — a
diferencia de A/E, aquí **no** se rellena con `0`, porque `0` minutos sería un
dato falso, no "no hubo actividad"):

```sql
WITH base AS (
    SELECT
        p.id, p.fecha AS dia,
        (p.fecha + COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso)) AS ingreso_ts,
        (COALESCE(p.fecha_salida, p.fecha) + p.hora_salida)             AS salida_ts_base
    FROM proveedores p
    WHERE p.fecha BETWEEN :desde AND :hasta
      AND p.estado_confirmacion = 'confirmado'
      AND p.hora_salida IS NOT NULL
      AND COALESCE(p.hora_ingreso_confirmado, p.hora_ingreso) IS NOT NULL
),
calc AS (
    SELECT
        dia, ingreso_ts,
        CASE WHEN salida_ts_base < ingreso_ts
             THEN salida_ts_base + interval '1 day'
             ELSE salida_ts_base
        END AS salida_ts
    FROM base
),
minutos AS (
    SELECT dia, EXTRACT(EPOCH FROM (salida_ts - ingreso_ts)) / 60.0 AS min
    FROM calc
),
validos AS (
    SELECT * FROM minutos WHERE min > 0 AND min <= 1440
),
serie AS (
    SELECT generate_series(:desde::date, :hasta::date, interval '1 day')::date AS dia
)
SELECT
    s.dia,
    ROUND(AVG(v.min)::numeric, 1)                                        AS promedio_minutos,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.min))::numeric, 1) AS mediana_minutos,
    COUNT(v.min)                                                         AS n_validos
FROM serie s
LEFT JOIN validos v ON v.dia = s.dia
GROUP BY s.dia
ORDER BY s.dia;
```

Alternativa comentada (NO usar hoy, solo queda documentada para cuando María
corrija que `hora_muelle_asignado` se escriba en tiempo real — ver sección 1):

```sql
-- (p.fecha + COALESCE(p.hora_muelle_asignado, p.hora_ingreso_confirmado, p.hora_ingreso)) AS ingreso_ts,
-- ... WHERE p.hora_muelle_liberado IS NOT NULL  -- en vez de p.hora_salida
```

### C. Ingresos por hora del día (0-23)

```sql
WITH horas AS (
    SELECT generate_series(0, 23) AS hora
),
ca_h AS (
    SELECT EXTRACT(HOUR FROM hora_ingreso)::int AS hora, COUNT(*) AS n
    FROM control_acceso
    WHERE fecha BETWEEN :desde AND :hasta
      AND anulado = FALSE
      AND hora_ingreso IS NOT NULL
    GROUP BY 1
),
prov_h AS (
    SELECT EXTRACT(HOUR FROM hora_ingreso)::int AS hora, COUNT(*) AS n
    FROM proveedores
    WHERE fecha BETWEEN :desde AND :hasta
      AND hora_ingreso IS NOT NULL
    GROUP BY 1
),
flota_h AS (
    -- Filtra por fecha_salida (la fecha real del evento hora_salida_cedi),
    -- no por fecha (fecha de creación del registro) -- son columnas
    -- distintas desde 20260626114921_fecha_salida_llegada.sql.
    SELECT EXTRACT(HOUR FROM hora_salida_cedi)::int AS hora, COUNT(*) AS n
    FROM flota_propia
    WHERE fecha_salida BETWEEN :desde AND :hasta
      AND hora_salida_cedi IS NOT NULL
    GROUP BY 1
)
SELECT
    h.hora,
    COALESCE(ca.n, 0) AS control_acceso,
    COALESCE(p.n, 0)  AS proveedores,
    COALESCE(f.n, 0)  AS flota_salidas_cedi
FROM horas h
LEFT JOIN ca_h   ca ON ca.hora = h.hora
LEFT JOIN prov_h p  ON p.hora  = h.hora
LEFT JOIN flota_h f ON f.hora  = h.hora
ORDER BY h.hora;
```

### D. Flota — tiempo de ruta (salida CEDI → llegada), global + top N por placa

Global:

```sql
WITH rutas AS (
    SELECT
        f.id, f.placa,
        (f.fecha_salida + f.hora_salida_cedi) AS salida_ts,
        (f.fecha_llegada + f.hora_llegada)    AS llegada_ts
    FROM flota_propia f
    WHERE f.fecha_salida BETWEEN :desde AND :hasta
      AND f.fecha_salida  IS NOT NULL AND f.hora_salida_cedi IS NOT NULL
      AND f.fecha_llegada IS NOT NULL AND f.hora_llegada     IS NOT NULL
),
minutos AS (
    SELECT id, placa, EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 AS min
    FROM rutas
)
SELECT
    ROUND(AVG(min)::numeric, 1)                                        AS promedio_minutos,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min))::numeric, 1) AS mediana_minutos,
    COUNT(*)                                                           AS n_validos
FROM minutos
-- Umbral: <=0 (llegada registrada antes de la salida -- error de captura) y
-- >2880 min (48h -- ningún viaje de flota propia entre CEDI y tiendas debería
-- tomar más de 2 días; si pasa, es un olvido de registrar la llegada real,
-- no una ruta real). Ambas fechas ya vienen explícitas por columna
-- (fecha_salida / fecha_llegada), así que NO hace falta inferir cruce de
-- medianoche aquí -- a diferencia de la sección B, donde solo hay una fecha
-- de referencia (proveedores.fecha) para dos eventos.
WHERE min > 0 AND min <= 2880;
```

Top N por placa (`N = 10`, configurable en el backend; ordenado por más
viajes primero, luego por promedio descendente para resaltar placas lentas
con volumen relevante):

```sql
WITH rutas AS (
    SELECT
        f.id, f.placa,
        (f.fecha_salida + f.hora_salida_cedi) AS salida_ts,
        (f.fecha_llegada + f.hora_llegada)    AS llegada_ts
    FROM flota_propia f
    WHERE f.fecha_salida BETWEEN :desde AND :hasta
      AND f.fecha_salida  IS NOT NULL AND f.hora_salida_cedi IS NOT NULL
      AND f.fecha_llegada IS NOT NULL AND f.hora_llegada     IS NOT NULL
),
minutos AS (
    SELECT id, placa, EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 AS min
    FROM rutas
    WHERE EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 > 0
      AND EXTRACT(EPOCH FROM (llegada_ts - salida_ts)) / 60.0 <= 2880
)
SELECT
    placa,
    ROUND(AVG(min)::numeric, 1)                                        AS promedio_minutos,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min))::numeric, 1) AS mediana_minutos,
    COUNT(*)                                                           AS n_viajes
FROM minutos
GROUP BY placa
ORDER BY n_viajes DESC, promedio_minutos DESC
LIMIT 10;
```

### E. Flota — pallets y contenedores despachados por día

```sql
WITH serie AS (
    SELECT generate_series(:desde::date, :hasta::date, interval '1 day')::date AS dia
),
flota_agg AS (
    -- SUM ignora NULL automáticamente: filas sin n_pallets/n_contenedores
    -- (0.4%/6% de huecos según el diagnóstico de calidad) simplemente no
    -- suman, no se tratan como error ni bloquean el resto del día.
    SELECT fecha AS dia, SUM(n_pallets) AS pallets, SUM(n_contenedores) AS contenedores
    FROM flota_propia
    WHERE fecha BETWEEN :desde AND :hasta
    GROUP BY fecha
)
SELECT
    s.dia,
    COALESCE(fa.pallets, 0)::int      AS pallets,
    COALESCE(fa.contenedores, 0)::int AS contenedores
FROM serie s
LEFT JOIN flota_agg fa ON fa.dia = s.dia
ORDER BY s.dia;
```

### F. Flota — cumplimiento de sellos (global + por día)

Global:

```sql
SELECT
    COUNT(*) AS total_viajes,
    COUNT(*) FILTER (WHERE sello IS NOT NULL AND btrim(sello) <> '') AS con_sello_salida,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE sello IS NOT NULL AND btrim(sello) <> '')
        / NULLIF(COUNT(*), 0)
    , 1) AS pct_sello_salida,
    COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL) AS viajes_con_llegada,
    COUNT(*) FILTER (
        WHERE hora_llegada IS NOT NULL
          AND sello_entrada IS NOT NULL AND btrim(sello_entrada) <> ''
    ) AS con_sello_entrada,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE hora_llegada IS NOT NULL
              AND sello_entrada IS NOT NULL AND btrim(sello_entrada) <> ''
        )
        / NULLIF(COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL), 0)
    , 1) AS pct_sello_entrada
FROM flota_propia
WHERE fecha BETWEEN :desde AND :hasta;
```

**Actualización de María (backend, 2026-10-02) — desglose por tipo de sello
en `global`**: se agregó al mismo `SELECT` global (mismo `FROM`/`WHERE`, sin
tocar la query `por_dia` de abajo) el conteo por tipo de sello Digital vs.
Plástico, para la nueva tarjeta "Tipo de sello" de Laura en la pestaña
Estadísticas:

```sql
    COUNT(*) FILTER (WHERE tipo_sello = 'Digital') AS tipo_salida_digital,
    COUNT(*) FILTER (WHERE tipo_sello = 'Plástico') AS tipo_salida_plastico,
    COUNT(*) FILTER (WHERE tipo_sello IS NULL OR btrim(tipo_sello) = '') AS tipo_salida_sin_tipo,
    COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL AND tipo_sello_entrada = 'Digital') AS tipo_entrada_digital,
    COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL AND tipo_sello_entrada = 'Plástico') AS tipo_entrada_plastico,
    COUNT(*) FILTER (
        WHERE hora_llegada IS NOT NULL
          AND (tipo_sello_entrada IS NULL OR btrim(tipo_sello_entrada) = '')
    ) AS tipo_entrada_sin_tipo
```

Reglas, consistentes con el resto de la sección F:

- Valores exactos `'Digital'` y `'Plástico'` (con tilde) — los mismos
  literales que ya guarda/compara `frontend/js/pages/FlotaPage.js`
  (`PUT /flota/{id}` con `tipo_sello`/`tipo_sello_entrada`). **No** se
  normaliza con `UPPER()`/`unaccent()`: hacerlo divergiría silenciosamente
  de lo que el frontend ya escribe y compara hoy.
- `tipo_sello_entrada` hereda el mismo filtro `hora_llegada IS NOT NULL` que
  `con_sello_entrada`/`pct_sello_entrada` — un viaje aún en ruta no cuenta en
  ninguna de las 3 categorías de entrada, aunque ya traiga un
  `tipo_sello_entrada` cargado de antemano.
- `NULL` y `''` (vacío) cuentan igual como `sin_tipo` — mismo criterio
  `btrim(...) = ''` que ya usa `con_sello_salida`/`con_sello_entrada`.
- Las 3 categorías de cada dirección siempre reconcilian con el total de esa
  dirección: `digital + plastico + sin_tipo == total_viajes` (salida) /
  `== viajes_con_llegada` (entrada).
- **Solo se agrega a `global`**, no a `por_dia` (no fue pedido y la query
  `por_dia` no se modificó).

Por día (relleno con `0`/`null` según corresponda cuando no hay viajes ese
día — porcentaje sin denominador queda `null`, nunca `0` falso):

```sql
WITH serie AS (
    SELECT generate_series(:desde::date, :hasta::date, interval '1 day')::date AS dia
),
agg AS (
    SELECT
        fecha AS dia,
        COUNT(*) AS total_viajes,
        COUNT(*) FILTER (WHERE sello IS NOT NULL AND btrim(sello) <> '') AS con_sello_salida,
        COUNT(*) FILTER (WHERE hora_llegada IS NOT NULL) AS viajes_con_llegada,
        COUNT(*) FILTER (
            WHERE hora_llegada IS NOT NULL
              AND sello_entrada IS NOT NULL AND btrim(sello_entrada) <> ''
        ) AS con_sello_entrada
    FROM flota_propia
    WHERE fecha BETWEEN :desde AND :hasta
    GROUP BY fecha
)
SELECT
    s.dia,
    COALESCE(a.total_viajes, 0)      AS total_viajes,
    COALESCE(a.con_sello_salida, 0)  AS con_sello_salida,
    ROUND(100.0 * COALESCE(a.con_sello_salida, 0) / NULLIF(a.total_viajes, 0), 1) AS pct_sello_salida,
    COALESCE(a.viajes_con_llegada, 0) AS viajes_con_llegada,
    COALESCE(a.con_sello_entrada, 0)  AS con_sello_entrada,
    ROUND(100.0 * COALESCE(a.con_sello_entrada, 0) / NULLIF(a.viajes_con_llegada, 0), 1) AS pct_sello_entrada
FROM serie s
LEFT JOIN agg a ON a.dia = s.dia
ORDER BY s.dia;
```

---

## 3. Contrato JSON de la respuesta

`GET /dashboard/estadisticas?fecha_desde=2026-08-27&fecha_hasta=2026-09-26`

Reglas generales de tipos:

- Fechas: string `"YYYY-MM-DD"`.
- Minutos: número (float) con **1 decimal**, o `null` si no hay muestras.
- Porcentajes: número (float) con **1 decimal**, escala 0-100 (no 0-1), o
  `null` si el denominador es 0 (nunca `0` falso).
- Conteos (`n`, `total`, `pallets`, etc.): entero, `0` cuando no hay
  registros ese día (relleno explícito vía `generate_series`, secciones A, E
  y los conteos de F; **no** aplica a promedios/medianas de B/D, que van en
  `null`).

```json
{
  "fecha_desde": "2026-08-27",
  "fecha_hasta": "2026-09-26",
  "tendencia_diaria": [
    {
      "fecha": "2026-08-27",
      "flota": 42,
      "proveedores": 51,
      "control_acceso": 118,
      "visitantes": 9
    }
  ],
  "tiempo_muelle_proveedores": {
    "global": {
      "promedio_minutos": 187.3,
      "mediana_minutos": 155.0,
      "n_validos": 812
    },
    "por_dia": [
      {
        "fecha": "2026-08-27",
        "promedio_minutos": 172.4,
        "mediana_minutos": 150.0,
        "n_validos": 28
      },
      {
        "fecha": "2026-08-28",
        "promedio_minutos": null,
        "mediana_minutos": null,
        "n_validos": 0
      }
    ]
  },
  "ingresos_por_hora": [
    {
      "hora": 0,
      "control_acceso": 0,
      "proveedores": 0,
      "flota_salidas_cedi": 0
    },
    {
      "hora": 6,
      "control_acceso": 34,
      "proveedores": 12,
      "flota_salidas_cedi": 8
    }
  ],
  "tiempo_ruta_flota": {
    "global": {
      "promedio_minutos": 245.8,
      "mediana_minutos": 210.0,
      "n_validos": 3801
    },
    "top_placas": [
      {
        "placa": "ABC123",
        "promedio_minutos": 310.2,
        "mediana_minutos": 295.0,
        "n_viajes": 61
      }
    ]
  },
  "carga_despachada_por_dia": [
    {
      "fecha": "2026-08-27",
      "pallets": 512,
      "contenedores": 34
    }
  ],
  "cumplimiento_sellos": {
    "global": {
      "total_viajes": 3951,
      "con_sello_salida": 3947,
      "pct_sello_salida": 99.9,
      "viajes_con_llegada": 3928,
      "con_sello_entrada": 3900,
      "pct_sello_entrada": 99.3,
      "tipo_sello_salida": {
        "digital": 3012,
        "plastico": 935,
        "sin_tipo": 4
      },
      "tipo_sello_entrada": {
        "digital": 2890,
        "plastico": 1010,
        "sin_tipo": 28
      }
    },
    "por_dia": [
      {
        "fecha": "2026-08-27",
        "total_viajes": 42,
        "con_sello_salida": 42,
        "pct_sello_salida": 100.0,
        "viajes_con_llegada": 41,
        "con_sello_entrada": 40,
        "pct_sello_entrada": 97.6
      },
      {
        "fecha": "2026-08-28",
        "total_viajes": 0,
        "con_sello_salida": 0,
        "pct_sello_salida": null,
        "viajes_con_llegada": 0,
        "con_sello_entrada": 0,
        "pct_sello_entrada": null
      }
    ]
  }
}
```

### Notas de contrato específicas para María (backend) y Laura (frontend)

- `tendencia_diaria`, `carga_despachada_por_dia`, `ingresos_por_hora` y
  `cumplimiento_sellos.por_dia` **siempre** traen una fila por cada día/hora
  del rango — el frontend nunca tiene que rellenar huecos ni manejar arrays
  de longitud variable para dibujar el eje X completo.
- `tiempo_muelle_proveedores.por_dia` y `top_placas` de `tiempo_ruta_flota`
  son la única excepción a "relleno con 0": ahí un día sin muestras válidas
  es `null` en los promedios (nunca `0`), y `top_placas` es un array corto
  (máx. 10) sin relleno — si hay menos de 10 placas con viajes válidos en el
  rango, el array trae menos de 10 elementos.
- `n_validos` / `n_viajes` siempre viajan junto al promedio/mediana
  correspondiente: Laura debe usarlos para decidir si vale la pena mostrar
  el dato (p. ej. no destacar un "promedio" calculado sobre 1 sola muestra) —
  criterio de UX a definir con Laura, el contrato solo garantiza que el
  número de muestras siempre está disponible.
- Todos los porcentajes ya vienen redondeados a 1 decimal en SQL — no
  recalcular ni volver a redondear en frontend ni en backend.
- `cumplimiento_sellos.global.tipo_sello_salida`/`tipo_sello_entrada` son
  campos nuevos (2026-10-02), **solo en `global`**, con forma fija
  `{"digital": int, "plastico": int, "sin_tipo": int}`. El frontend debe
  tolerar que un backend desplegado antes de este cambio no los traiga
  todavía (`undefined`) — usar optional chaining y mostrar el mismo estado
  "Sin datos en el rango" del resto de las tarjetas, nunca romper.

---

## 4. Índices: no se requiere ninguno nuevo

Validado con `EXPLAIN` contra la BD local de pruebas (mismo esquema que
producción, migraciones aplicadas 1:1):

- `control_acceso` filtrado por rango de fecha + `anulado = FALSE` (secciones
  A y C) usa `Index Only Scan` sobre `idx_ca_activos_fecha (fecha DESC, hora_ingreso DESC) WHERE anulado = FALSE`
  — el índice parcial ya existente cubre exactamente este filtro.
- `proveedores` filtrado por rango de fecha (sección B) usa `Index Scan`
  sobre `idx_prov_fecha`.
- `flota_propia` filtrado por `fecha_salida` (secciones C y D, no hay índice
  dedicado a esa columna, solo a `fecha`) resuelve con `Seq Scan`, costo
  `~11` en el plan de Postgres — al volumen real (3.951 filas totales) un
  `Seq Scan` completo de la tabla cuesta submilisegundos. **No se justifica**
  un índice nuevo sobre `fecha_salida`/`fecha_llegada` a este volumen.
- `visitantes` filtrado por fecha usa `idx_vis_fecha`.

**No se incluye ninguna migración nueva en `supabase/migrations/`** — no hay
nada que crear. Punto de vigilancia a futuro (no accionable hoy): si
`flota_propia` crece más de ~10x (order de 40.000+ filas) y las queries C/D
por `fecha_salida` empiezan a pesar, el candidato sería:

```sql
-- Migración futura, NO incluida ahora (documentada como referencia):
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fp_fecha_salida ON flota_propia (fecha_salida) WHERE fecha_salida IS NOT NULL;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fp_fecha_llegada ON flota_propia (fecha_llegada) WHERE fecha_llegada IS NOT NULL;
```

---

## 5. Reglas de validación y exclusión (resumen)

| Sección | Filtro de inclusión | Umbral de exclusión | Motivo |
|---|---|---|---|
| A | ninguno adicional | — | conteo simple |
| A (control_acceso) | `anulado = FALSE` | — | convención del repo (soft-delete) |
| B | `estado_confirmacion='confirmado'`, `hora_salida IS NOT NULL`, ingreso (confirmado o fallback) no nulo | `min <= 0` o `min > 1440` (24h) | dato corrupto / olvido de registrar salida |
| C | `hora_ingreso`/`hora_salida_cedi` no nulo | — | conteo por hora, sin promedio que umbralizar |
| D | `fecha_salida`, `hora_salida_cedi`, `fecha_llegada`, `hora_llegada` todos no nulos | `min <= 0` o `min > 2880` (48h) | llegada antes que salida / olvido de registrar llegada |
| E | ninguno (SUM ignora NULL) | — | agregación tolerante a huecos de captura |
| F (salida) | ninguno | — | `sello` no vacío/no NULL cuenta como cumplimiento |
| F (entrada) | `hora_llegada IS NOT NULL` (solo viajes que ya llegaron) | — | pedido explícito: no penalizar viajes aún en ruta |
| F (tipo_sello_salida) | ninguno adicional | — | valores exactos `'Digital'`/`'Plástico'`; `NULL`/`''` → `sin_tipo` |
| F (tipo_sello_entrada) | `hora_llegada IS NOT NULL` (mismo criterio que con_sello_entrada) | — | no contar tipo de entrada de un viaje aún en ruta |

Fin del contrato.
