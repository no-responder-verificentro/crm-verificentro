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
- **Clientes**: búsqueda unificada por nombre, teléfono, correo, placa o NIV
- **Alta de cliente y vehículo**, con el cálculo del periodo en vivo
- **Ficha del vehículo**: estado del periodo, historial de verificaciones,
  registro de verificación y cambio de placa
- **Verificaciones**: bitácora con indicadores, filtros de fecha y resultado,
  y búsqueda por placa, cliente o folio
- **Panel de control**: indicadores, gráfica de verificaciones por mes y tabla
  de seguimiento ordenada por urgencia, con filtros por estado
- **Recordatorios**: cola de lo que va a salir con pausar/reanudar/cancelar,
  bitácora de lo enviado con su acuse, y aviso de contactos no localizables
- **Citas**: horarios libres del día, apartado desde el mostrador, agenda con
  cancelación y marcado de no presentados
- **Consulta pública** (`/consulta`): cualquiera escribe su placa y ve cuándo
  le toca, sin registrarse. Es a donde llega el cliente desde el correo, y la
  misma respuesta que dará el chatbot
- **Reportes** (solo administradores): efectividad de los recordatorios,
  cumplimiento por dígito, entrega por canal y exportación a Excel
- **Empleados**: alta, cambio de perfil, baja y reactivación, más la matriz de
  permisos visible. Nadie puede darse de baja ni degradarse a sí mismo
- **Chatbot**: el chat en la página pública y la pantalla para administrar el
  catálogo y atender las preguntas que no supo contestar
- Menú filtrado por perfil

### El flujo completo

Buscas al cliente por su placa → entras a su ficha → ves que le quedan 28 días
→ registras la verificación → el encabezado cambia a **Ya verificó** y el
vehículo deja de recibir avisos de ese periodo.

## Lo que sigue

El frontend está completo. Falta montarlo: ver `SUBIR_A_PRODUCCION.md`.

La gráfica del panel está hecha con divs y Tailwind, sin librería de
gráficas: para barras simples no hace falta agregar 200 kB al paquete.
