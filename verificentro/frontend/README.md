# CRM Verificentro — frontend

React 19 + Vite + Tailwind 4, en JavaScript.

## Arrancar

El backend tiene que estar corriendo primero (`uvicorn app.main:aplicacion --reload`).

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Abre <http://localhost:5173> y entra con la cuenta que creaste con
`python -m jobs.crear_admin`.

## Estructura

```
src/
├── api/
│   ├── cliente.js      el único fetch: token, errores, URL base
│   └── recursos.js     una función por operación de la API
├── contexto/
│   └── Sesion.jsx      empleado actual y permisos por perfil
├── componentes/        Layout, RutaProtegida, Pastilla, Aviso, Vacio, Cargando
├── paginas/            una por pantalla del Figma
├── utils/formato.js    teléfonos, fechas, etiquetas de estado
└── index.css           paleta de la marca + clases repetidas
```

## Decisiones

**Todo el HTTP pasa por `api/cliente.js`.** Adjunta el token, traduce los
errores de FastAPI a un mensaje en español, y distingue el 422 (validación,
que llega como lista de campos) del 409 (regla de negocio, que llega como
texto). Ninguna pantalla arma una petición a mano.

**La paleta vive en `index.css`.** Los colores del manual —guinda, verde,
dorado— se declaran una vez con `@theme` y quedan como utilidades:
`bg-guinda`, `text-verde`, `border-dorado`.

**El menú se filtra por perfil.** Un técnico no ve Empleados ni Reportes.
Esto es solo para la interfaz: el permiso de verdad lo impone el backend en
cada petición. Ocultar un botón nunca es una medida de seguridad.

**La búsqueda descarta respuestas viejas.** Si el usuario teclea rápido, la
respuesta de "YU" puede llegar después de la de "YUN"; se compara contra un
contador para no pisar los resultados correctos.

**El periodo se calcula también en el navegador**, para que el técnico vea
qué le toca al auto conforme teclea la placa. Es solo retroalimentación
visual: lo que se guarda es lo que calcula la base.

## Lo que ya funciona

- Login y sesión persistente (si dan de baja al empleado, la sesión muere)
- Clientes: búsqueda unificada por nombre, teléfono, correo, placa o NIV
- Alta de cliente y vehículo, con el cálculo del periodo en vivo
- Menú completo, con marcador en las secciones que faltan

## Lo que sigue

Ficha del vehículo, verificaciones, dashboard, empleados. Las tres primeras
ya tienen su API lista.
