# CRM Verificentro

Sistema de seguimiento y recordatorios de verificación vehicular.

```
COMO_EJECUTAR.md        cómo prender cada cosa en tu computadora
DESPLIEGUE.md           subirlo a Aiven + Render + Netlify, gratis
CONECTAR_CORREO.md      por dónde salen los correos, y por qué no llegan
SUBIR_A_PRODUCCION.md   Git, y la alternativa de montarlo en el local
CONECTAR_WHATSAPP.md    el trámite con Meta, cuando lo decidan
db/schema.sql           base de datos MySQL
backend/                API en Python (FastAPI) — 380 pruebas
frontend/               interfaz en React
```

Si es tu primera vez, empieza por `COMO_EJECUTAR.md`.
Para ponerlo en línea, `DESPLIEGUE.md`.

## En celular

La interfaz se adapta sola; no hay una versión aparte que mantener.

- **Menos de 1024px** — el menú lateral se guarda y se abre con el botón de las
  tres rayas de la barra superior. Las tablas se parten en tarjetas: cada
  renglón pasa a ser un bloque con el nombre arriba y una etiqueta por dato, en
  lugar de obligar a arrastrar la pantalla de lado.
- **1024px o más** — el menú vuelve a estar fijo a la izquierda y las tablas
  vuelven a ser tablas.

Lo que controla ese comportamiento está en dos lugares:
`frontend/src/componentes/Layout.jsx` para el menú, y el bloque final de
`frontend/src/index.css` para las tablas. Ahí está explicado cómo marcar una
tabla nueva: la clase `tabla-responsiva`, un `data-etiqueta` por celda y
`celda-titulo` en la que hace de encabezado de la tarjeta.
