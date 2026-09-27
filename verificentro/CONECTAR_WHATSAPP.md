# Conectar WhatsApp — trámite y sistema, paso a paso

Dos frentes que avanzan en paralelo. El del sistema ya está hecho: el código
está escrito y probado, esperando credenciales. El del trámite es el que toma
tiempo y depende de ustedes.

---

# PARTE 1 · El trámite con Meta

## Antes de empezar: dos decisiones

**El número.** Tiene que ser uno que **no esté activo en WhatsApp ni en
WhatsApp Business**. Al registrarlo en la Cloud API deja de funcionar en el
celular. Si el verificentro ya atiende por WhatsApp desde un teléfono,
consigan un número nuevo para los avisos automáticos; si usan el mismo,
pierden ese chat.

**Los documentos.** Para la verificación del negocio piden, según el caso:
acta constitutiva o constancia de situación fiscal, comprobante de domicilio a
nombre del negocio, y a veces un estado de cuenta bancario. **El nombre legal
tiene que coincidir exactamente** con el que registren en Meta.

---

## Paso 1 · Cuenta de Facebook con verificación en dos pasos

Quien vaya a administrar esto necesita una cuenta personal de Facebook con
2FA activado. No sirve una cuenta nueva y vacía: Meta desconfía de ellas.

## Paso 2 · Portafolio comercial

En <https://business.facebook.com> → crear un portafolio comercial (antes
"Business Manager").

- Nombre legal del negocio, tal como está en los documentos
- Sitio web y dirección
- Correo de contacto

## Paso 3 · Verificación del negocio

Business Manager → Configuración del negocio → **Centro de seguridad** →
Iniciar verificación.

Es el paso que más tarda: de días a semanas. **Empiécenlo primero**, porque
todo lo demás lo espera.

Se suben los documentos y Meta valida que el negocio existe y que la persona
está autorizada. Si rechazan, casi siempre es porque el nombre no coincide
letra por letra con el documento.

## Paso 4 · Crear la app

<https://developers.facebook.com> → Mis apps → Crear app → tipo **Empresa** →
vincularla al portafolio del paso 2.

Anotar el **ID de la app** y el **secreto de la app** (Configuración →
Básica). El secreto va en `WHATSAPP_APP_SECRET`.

## Paso 5 · Agregar el producto WhatsApp

En la app → Agregar producto → **WhatsApp** → Configurar.

Meta crea automáticamente una cuenta de WhatsApp Business (WABA) y un **número
de prueba**. Ese número sirve para probar con hasta 5 destinatarios que
ustedes registren, y es útil antes de meter el número real.

## Paso 6 · Registrar el número real

En el panel de WhatsApp de la app → Agregar número de teléfono.

- Se verifica por SMS o llamada
- Se define el **nombre para mostrar** (el que ve el cliente). Tiene que estar
  relacionado con el negocio; "Verificentro Ruiz Cortines" pasa, "Avisos" no

Al terminar, anotar el **ID del número de teléfono**. Ojo: es un ID numérico
largo, **no es el número telefónico**. Va en `WHATSAPP_PHONE_ID`.

## Paso 7 · Token permanente

El token que aparece en pantalla al principio **vence en 24 horas**. Para
producción hace falta uno permanente:

Business Manager → Configuración del negocio → **Usuarios del sistema** →
Agregar → rol Administrador.

Asignarle activos: la **app** y la **cuenta de WhatsApp (WABA)**, ambas con
control total.

Generar token con estos permisos:

- `whatsapp_business_messaging`
- `whatsapp_business_management`

Ese token va en `WHATSAPP_TOKEN`. **Se muestra una sola vez.**

## Paso 8 · Método de pago

Configuración de la WABA → Facturación → agregar tarjeta.

Sin esto solo funciona el número de prueba. Meta cobra por mensaje entregado;
las plantillas de categoría *Utility* son las más baratas.

## Paso 9 · Dar de alta las cinco plantillas

Administrador de WhatsApp → Plantillas de mensajes → Crear.

**Categoría: Utility.** No Marketing. Si las clasifican como marketing suben
de precio, bajan de entregabilidad y aparece el botón de "dejar de recibir
promociones".

Los nombres tienen que ser **exactamente** estos, porque son los que el
sistema busca (`app/mensajeria/plantillas.py`, diccionario `PLANTILLAS_META`):

| Nombre en Meta | Cuándo sale |
|---|---|
| `verificentro_aviso_previo` | 15 días antes de que abra |
| `verificentro_periodo_abierto` | el día que abre |
| `verificentro_mitad_periodo` | a la mitad |
| `verificentro_ultimos_dias` | 5 días antes del cierre |
| `verificentro_periodo_vencido` | al día siguiente del cierre |

Las tres variables van **en este orden** en todas:

```
{{1}} nombre de pila        ejemplo: Ana
{{2}} placa                 ejemplo: YUN-047-A
{{3}} fecha de cierre       ejemplo: 30 de septiembre
```

Idioma: **Español (MX)**, que corresponde a `es_MX`.

Los textos están en `app/mensajeria/plantillas.py`. Revísenlos con el jefe
antes de mandarlos: cambiarlos después implica volver a esperar la aprobación.

La aprobación tarda de minutos a un día.

## Paso 10 · Webhook

Necesita una **URL pública con HTTPS**. `localhost` no sirve: Meta tiene que
poder llamarla desde internet. Es aquí donde el sistema tiene que salir de la
laptop.

Para probar mientras tanto, un túnel sirve:

```powershell
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
```

Da una dirección `https://algo.trycloudflare.com` que apunta a tu máquina.

En la app → WhatsApp → Configuración → Webhooks:

- **URL de devolución de llamada:** `https://tu-dominio/webhooks/whatsapp`
- **Token de verificación:** una palabra que inventes, la misma que pongas en
  `WHATSAPP_VERIFY_TOKEN`
- Suscribirse a los campos: **`messages`** (trae acuses y mensajes entrantes)
  y **`message_template_status_update`** (avisa si Meta pausa una plantilla)

Al guardar, Meta llama una vez al webhook para verificarlo. Si el backend está
corriendo y el token coincide, queda listo.

## Paso 11 · Límites de arranque

La cuenta empieza pudiendo iniciar conversación con **250 usuarios distintos
al día**. Sube sola a 1,000, 10,000 y más, conforme el número mantenga buena
calidad.

Con 1,500 clientes repartidos en cinco grupos de dígitos, un día de avisos
toca a unos 300. **Va a toparse el límite los primeros días.** Los que no
salgan quedan en la cola como error y se reintentan; no se pierden.

---

# PARTE 2 · El sistema

Ya está programado y probado. Falta configurarlo.

## Lo único que hay que tocar

En el archivo `.env` del backend:

```
CANALES_ACTIVOS=["correo","whatsapp"]
PROVEEDOR_WHATSAPP=meta

WHATSAPP_TOKEN=el-token-permanente-del-paso-7
WHATSAPP_PHONE_ID=el-id-numerico-del-paso-6
WHATSAPP_VERIFY_TOKEN=la-palabra-que-inventaste
WHATSAPP_APP_SECRET=el-secreto-de-la-app-del-paso-4
WHATSAPP_IDIOMA=es_MX

URL_PUBLICA=https://tu-dominio
```

Reiniciar el backend y listo.

## Qué hace el sistema ya

**Envía por plantilla.** No manda texto libre: arma el nombre de la plantilla
más las tres variables, que es lo único que Meta acepta cuando nosotros
iniciamos la conversación.

**Entiende los errores de Meta.** Distingue el que no tiene WhatsApp, la
plantilla no aprobada, el límite de envíos y la caída de red. Los dos últimos
se marcan como reintentables, porque no son culpa del contacto y marcarlo como
fallido definitivo lo quemaría injustamente.

**Recibe los acuses.** El webhook traduce `sent`, `delivered`, `read` y
`failed` a los estados de la bitácora, vinculándolos por el identificador que
Meta devuelve al enviar. Los acuses solo avanzan: si llega "entregado" después
de "leído", se guarda en la bitácora pero no retrocede.

**Atiende las bajas solo.** Si el cliente responde BAJA, STOP o "darme de
baja", queda marcado y deja de recibir avisos en la siguiente corrida del job.
Esto no podía esperar al chatbot: si alguien pide dejar de recibir mensajes y
seguimos mandándolos, reporta como spam y se cae la entregabilidad de todos.

**Verifica la firma de los webhooks.** Sin eso, cualquiera que conozca la URL
podría mandar acuses falsos.

## Cómo probarlo antes de ir en serio

Con el número de prueba que da Meta en el paso 5, registrando tu propio
celular como destinatario permitido:

```powershell
python -m jobs.generar_recordatorios --dias 90
python -m jobs.enviar_pendientes
```

Revisa en la pantalla de Recordatorios que el acuse pase de *enviado* a
*entregado* y a *leído*. Si eso funciona, el circuito completo está cerrado.

---

# El orden que yo seguiría

1. **Esta semana:** juntar documentos y arrancar la verificación del negocio
   (pasos 1 a 3). Es lo que bloquea todo.
2. **Mientras esperan:** revisar los cinco textos con el jefe, y decidir el
   número.
3. **Al aprobarse:** pasos 4 a 9 en una tarde.
4. **En paralelo:** decidir dónde va a vivir el sistema, porque el webhook
   necesita una dirección pública y estable. Eso también resuelve el pendiente
   de tener los jobs corriendo solos.
