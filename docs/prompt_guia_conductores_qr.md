# Prompt para generar la guía de autorregistro QR (conductores)

Copia y pega este prompt en Canva (Magic Design / generar diseño), ChatGPT+imagen, o cualquier herramienta de diseño con IA.

---

## Prompt

Diseña un afiche/infografía en español (Colombia), tamaño carta u oficio, vertical, para pegar físicamente en la portería vehicular de un centro de distribución (CEDI). El público son conductores de camiones y furgones que entregan mercancía — texto muy simple, pocas palabras, letra grande, con íconos claros para cada paso (no asumir que todos saben usar apps).

**Título:** "Registra tu ingreso escaneando el QR"

**Instrucciones a mostrar, en 6 pasos numerados con ícono para cada uno:**

1. **Busca el QR en la portería** — Está pegado o en una pantalla, junto a la entrada de vehículos.
2. **Escanea el QR con la cámara de tu celular** — No necesitas instalar ninguna app. Se abre una página web sola.
3. **Llena tus datos** — Placa, tu nombre, documento, teléfono, tipo de vehículo, fecha de tu ARL, si tienes tus elementos de protección (EPP), tipo y formato de la carga, cantidad de pallets y quién la maneja.
4. **Agrega la empresa y el número de orden de compra** — A la(s) que traes mercancía. Si traes para varias, agrégalas todas antes de enviar.
5. **Envía el formulario** — Tienes hasta 30 minutos desde que escaneas el QR para completarlo con calma.
6. **Espera la confirmación del guarda** — Un mensaje te avisa que tu registro quedó enviado; el guarda de portería confirma tu ingreso en un momento.

**Nota importante a destacar (en un recuadro aparte, con ícono de alerta):** El código QR cambia cada pocos minutos por seguridad — no sirve una foto guardada de antes, debes escanear el QR real que está en portería en ese momento.

**Estilo visual:** colores corporativos azul marino y ámbar/naranja, íconos tipo flat/línea simple (celular, QR, camión, check ✓), fondo blanco, mucho espacio en blanco, tipografía grande y legible a distancia, numeración destacada (círculos grandes con el número). Nada de párrafos largos — frases cortas tipo bullet.

---

## Contexto (por si la herramienta permite subir referencia, no hace falta incluirlo en el prompt)

- El flujo real ya está implementado en la app "Control de Acceso y Operaciones CEDI R10".
- El QR se genera desde el módulo Proveedores → "QR Ingreso" (pantalla tipo kiosco que se refresca sola).
- El formulario público vive en `/?ingreso_proveedor=1&token=...`.
