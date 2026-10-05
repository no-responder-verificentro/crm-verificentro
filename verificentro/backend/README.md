# CRM Verificentro — backend

FastAPI + SQLAlchemy + MySQL.

## Arrancar

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # y edita DB_URL y JWT_SECRETO
mysql -u root -p --default-character-set=utf8mb4 < ../db/schema.sql

python -m jobs.crear_admin "Tu Nombre" tu.correo@verificentro.mx
uvicorn app.main:aplicacion --reload
```

Documentación interactiva en <http://localhost:8000/docs>. El botón
**Authorize** pide correo y contraseña; el campo dice `username` porque es el
nombre estándar de OAuth2, pero ahí va el correo.

```bash
pytest        # 72 pruebas
```

## Estructura

```
app/
├── config.py           variables de entorno
├── database.py         motor y sesión
├── seguridad.py        bcrypt + JWT
├── dependencias.py     usuario actual y permisos por perfil
├── main.py             arranque y routers
│
├── dominio/            ← lógica de negocio pura
│   └── calendario.py     sin FastAPI, sin SQLAlchemy, sin HTTP
├── modelos/            tablas (SQLAlchemy)
├── esquemas/           entrada y salida (Pydantic)
├── servicios/          casos de uso
├── api/v1/             endpoints
├── mensajeria/         adaptadores de WhatsApp y correo
└── webhooks/           acuses de entrega y mensajes entrantes

jobs/                   procesos fuera de la API
tests/
```

La regla de `dominio/`: **ahí no se importa nada de infraestructura**. Por eso
`calendario.py` se prueba en centésimas de segundo sin base de datos, y por
eso sobrevive si algún día cambia el framework.

## Lo que ya funciona

**Autenticación** con JWT y los tres perfiles. El token trae el perfil, pero
el permiso se revisa contra la base en cada petición: si dan de baja a alguien
a media jornada, su sesión muere de inmediato en lugar de seguir viva hasta
que expire el token.

**Permisos por perfil** mediante `requiere_perfil()`. Se cuelga del router
completo, así ningún endpoint tiene que escribir `if perfil == ...` y el
permiso queda visible en `/docs`.

**Alta y baja de empleados**. Dar de baja desactiva la cuenta pero no borra
el registro: el historial de lo que capturó sigue apuntando a su id. Un
administrador no puede darse de baja ni degradarse a sí mismo, que es la
forma más común de quedarse sin ningún administrador.

**Consulta pública de periodo por placa** (`GET /api/v1/calendario/consultar`).
Sin token, porque es la que alimenta la respuesta estrella del chatbot. No
expone ningún dato personal: solo aplica el Artículo 9 a una placa.

```
GET /api/v1/calendario/consultar?placa=yun-047-a

{
  "placa_normalizada": "YUN047A",
  "ultimo_digito": 7,
  "periodos": [
    { "etiqueta": "Febrero – Marzo",      "abierto_hoy": false },
    { "etiqueta": "Agosto – Septiembre",  "abierto_hoy": true, "dias_restantes": 34 }
  ],
  "mensaje": "Te toca ahora: Agosto – Septiembre. Quedan 34 días para que cierre."
}
```

## Detalles de seguridad que ya están cubiertos

- El hash de la contraseña nunca sale en una respuesta: los endpoints declaran
  `response_model` y Pydantic solo serializa los campos públicos.
- Login con correo inexistente y con contraseña incorrecta tardan lo mismo y
  devuelven el mismo mensaje, para no revelar qué correos están registrados.
- bcrypt trunca en 72 bytes; el esquema de entrada rechaza contraseñas más
  largas en lugar de ignorar los caracteres extra en silencio.

## Correo por SMTP

**No depende de Meta.** En cuanto haya credenciales, la mitad del sistema de
recordatorios funciona de verdad. En el `.env`:

```
PROVEEDOR_CORREO=smtp
SMTP_HOST=smtp.tuproveedor.mx
SMTP_PUERTO=587
SMTP_USUARIO=...
SMTP_CONTRASENA=...
URL_PUBLICA=https://tu-servidor-alcanzable-desde-fuera
```

`URL_PUBLICA` no puede ser localhost en producción: es lo que va escrito en
los enlaces de los correos.

Cada correo sale en texto plano y HTML dentro del mismo mensaje —los
solo-HTML caen en spam con más frecuencia— y lleva la cabecera
`List-Unsubscribe` para que el propio cliente de correo ofrezca la baja.

### Medición del clic

Cada correo trae un enlace firmado a `/r/{id}/{firma}`. Al abrirlo se anota el
acuse `clic` y se redirige a la consulta pública con la placa ya puesta.

La firma es un HMAC: sin ella, cualquiera podría marcar como leídos los
correos de otros cambiando el número en la URL. Se compara en tiempo
constante para que tampoco se pueda adivinar midiendo la respuesta.

Se mide el clic y no la apertura porque el "abierto" depende de un pixel
invisible, y desde que Apple precarga las imágenes ese dato miente en las dos
direcciones.

### Orden de los acuses

`registrar_entrega()` solo deja avanzar el estado. Los acuses llegan
desordenados con frecuencia —puede llegar "entregado" después de "leído"—, así
que un evento atrasado se guarda en la bitácora pero no retrocede lo que ya se
sabía.

## Canales activos

`CANALES_ACTIVOS` decide por dónde se generan recordatorios. Un canal apagado
ahí no produce filas en la cola aunque el cliente lo haya autorizado.

```
CANALES_ACTIVOS=["correo"]              # así arranca el verificentro
CANALES_ACTIVOS=["correo","whatsapp"]   # cuando llegue el trámite con Meta
```

Importa porque evita acumular mensajes de WhatsApp que nadie va a poder
enviar. La pantalla de Recordatorios avisa cuando WhatsApp está apagado, para
que nadie suponga que los clientes sin correo están recibiendo algo.

## Reportes

Solo administradores. `GET /api/v1/reportes/…`

**`/efectividad`** es el número que justifica el proyecto: cuántos de los que
recibieron aviso regresaron a verificar dentro de su periodo, contra los que
no. Dos decisiones importantes sobre cómo se calcula:

- **Solo cuenta periodos YA CERRADOS.** Mientras la ventana sigue abierta el
  cliente todavía puede venir; contarlo como incumplimiento falsearía el
  número a la baja.
- **No es un experimento controlado**, y la pantalla lo dice. Quien no recibió
  aviso suele ser quien no dejó consentimiento o tiene los datos mal, así que
  ya era distinto de entrada. Es una señal, no una prueba de causalidad. La
  pantalla también avisa cuando la muestra es demasiado chica para concluir
  nada.

**`/cumplimiento`** por grupo de dígitos, **`/canales`** con la tasa de entrega
de WhatsApp y correo, y **`/exportar`** que descarga las verificaciones del año
en CSV.

El CSV usa punto y coma como separador y lleva BOM al inicio: sin eso, Excel
en español mete todo en una columna y rompe los acentos.

## Seguridad del token

Con `ENTORNO=produccion`, el servidor **se niega a arrancar** si `JWT_SECRETO`
sigue siendo el de ejemplo o mide menos de 32 caracteres. Vale más que no
levante a que levante firmando tokens con una llave que está en el repositorio.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## WhatsApp

El código está completo y probado; solo faltan las credenciales. El trámite
paso a paso está en `CONECTAR_WHATSAPP.md`, en la raíz del proyecto.

**Envío** (`app/mensajeria/whatsapp.py`): manda el nombre de la plantilla
aprobada más sus tres variables, que es lo único que Meta acepta cuando
nosotros iniciamos la conversación. Los nombres de plantilla viven en
`PLANTILLAS_META`, dentro de `app/mensajeria/plantillas.py`, y tienen que
coincidir exactamente con los dados de alta en Meta.

Distingue los errores que importan: número sin WhatsApp, plantilla no
aprobada, límite de envíos y caída de red. Los dos últimos se marcan como
**reintentables**: no son culpa del contacto, y marcarlo como fallido
definitivo lo quemaría injustamente.

**Webhook** (`app/webhooks/whatsapp.py`): recibe los acuses y los mensajes
entrantes en `/webhooks/whatsapp`.

- Siempre responde 200. Si devolviera error, Meta reintentaría el lote
  completo y reprocesaría lo que ya estaba bien.
- Verifica la firma HMAC. Sin eso, cualquiera que conozca la URL podría mandar
  acuses falsos.
- Atiende las bajas solo: si el cliente responde BAJA o STOP, queda marcado y
  deja de recibir avisos. Esto no podía esperar al chatbot.

## Chatbot

Funciona **hoy, gratis y sin depender de nadie**: contesta en la página
pública (`/consulta`). El motor (`app/dominio/chatbot.py`) no sabe de canales,
así que el día que se conecte WhatsApp es el mismo motor con otro adaptador.

**No usa inteligencia artificial, y es una decisión.** Las preguntas de un
verificentro son cinco o seis y se repiten; una coincidencia por palabras
clave las resuelve, es instantánea, no cuesta nada y —lo más importante— es
predecible: nunca va a inventar una fecha de verificación.

Lo que reconoce:

- **Placas escritas de cualquier forma**: `YUN-047-A`, `yun047a`,
  `mi placa es YUN 047 A`, y también el formato viejo `YJX7045`. Exige el
  formato real de placa, así que "cuesta 500 pesos" no se confunde con una.
- **Saludos y agradecimientos**, que se contestan sin anotarse como pregunta
  pendiente. Sin eso el panel se llenaría de "hola".
- **Preguntas del catálogo** por palabras clave.
- **Citas**: ofrece los horarios libres reales de la agenda, no un texto fijo.

Lo que no sabe queda en `chatbot_pendientes`, agrupado y contado. Convertir
esas en respuestas desde la pantalla de Chatbot es lo que hace que mejore con
el uso, y no pasa por revisión de nadie.

## Lo que sigue

1. Modelos y CRUD de clientes, vehículos y verificaciones
2. Cálculo de disponibilidad de citas
3. Adaptadores de mensajería, empezando por `consola`
4. Job de recordatorios
5. Webhooks de acuse
6. Chatbot

## Pendiente de definir con el cliente

Para el cálculo de disponibilidad de citas hacen falta tres datos: cuántas
líneas de verificación hay, cuánto tarda una verificación, y qué parte de la
capacidad se reserva a citas contra la que se deja libre para quien llega sin
cita. Esa última es decisión de negocio: si se agenda el 100%, el que llega
de improviso se queda parado.
