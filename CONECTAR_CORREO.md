# Por dónde salen los correos

El sistema no sabe mandar correo por sí mismo: se lo pide a alguien más. Ese
alguien se elige con **una** variable:

```
PROVEEDOR_CORREO=consola       # imprime en pantalla. NO manda nada.
PROVEEDOR_CORREO=mailjet       # API de Mailjet (no su SMTP)
PROVEEDOR_CORREO=apps_script   # una app web de Google Apps Script
PROVEEDOR_CORREO=smtp          # servidor de correo clásico
```

---

# Antes que nada: ¿está en modo consola?

**Es la causa número uno de "el sistema dice enviado y no llega nada".**

En modo consola el adaptador imprime el correo en la bitácora del servidor y
reporta el envío como exitoso. En la pantalla de Recordatorios todo se ve
verde, el acuse dice *Enviado*, y en la bandeja del cliente no hay nada,
**ni en spam**, porque nunca salió un correo.

Es a propósito: permite construir y probar el flujo completo sin gastar
mensajes ni esperar credenciales. Pero por eso mismo es el primer lugar donde
mirar.

El valor por omisión es `consola`. Si en Render nunca se capturó
`PROVEEDOR_CORREO`, está en consola aunque el `.env` de tu computadora diga
otra cosa.

Desde la versión actual, la pantalla de **Recordatorios** lo avisa con un
letrero en la parte de arriba cuando el sistema está en modo prueba. Si ves
ese letrero, no hay nada más que diagnosticar: faltan las variables.

---

# Mailjet dice que lo bloqueó por spam

Si en el panel de Mailjet los mensajes aparecen como **blocked** o
**spam pre-blocked**, el correo **nunca salió**. No está en spam del
destinatario: Mailjet lo descartó antes de mandarlo porque su filtro decidió
que el servidor del otro lado lo marcaría.

## Dónde dice por qué

**Mailjet → Statistics → Messages**, y abre el mensaje. La columna de detalle
trae el motivo exacto. Eso es lo primero que hay que leer; todo lo demás es
adivinar.

Los motivos que Mailjet lista para un bloqueo son:

- El destinatario reportó antes un correo tuyo como spam.
- Esa dirección ya rebotó de forma permanente.
- **El contenido** disparó su escaneo antispam: mayúsculas, mala proporción
  entre texto e imágenes, palabras típicas de promoción.
- Duplicados, cuando se usa Mailjet como relevo SMTP.

## Por qué el sistema no marcaba error

Porque estaba saliendo por **SMTP**. Mailjet contesta `250 OK` al recibir el
mensaje —eso solo significa "lo acepté"— y *después* le pasa su filtro. Para
cuando lo descarta, nosotros ya habíamos guardado el envío como exitoso.

Visto desde la pantalla era idéntico a un correo que llegó bien.

**Eso ya está arreglado, con dos cambios:**

**1. Se manda por la API, no por SMTP.** La respuesta de la Send API trae el
resultado de cada mensaje, así que un rechazo se ve en el momento.

**2. Hay un webhook para lo que Mailjet decide después.** Mailjet avisa de
cada `sent`, `click`, `bounce`, `blocked`, `spam` y `unsub`, y eso llena los
acuses de la pantalla de Recordatorios. Un bloqueo por contenido ahora
aparece como **spam**, con el motivo de Mailjet en la fila.

## Cómo conectarlo

**1.** En Mailjet → **Account settings** → **API Key Management**, copia la
API Key y la Secret Key.

**2.** Genera un secreto para el webhook:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

**3.** En `backend\.env` y en **Render → Environment**:

```
PROVEEDOR_CORREO=mailjet
MAILJET_API_KEY=la-api-key
MAILJET_API_SECRET=la-secret-key
MAILJET_WEBHOOK_SECRETO=el-secreto-del-paso-2
CORREO_REMITENTE=la-direccion-validada-en-mailjet
```

**4.** En Mailjet → **Account settings** → **Event notifications (webhooks)**,
da de alta esta dirección para todos los eventos:

```
https://TU-API.onrender.com/webhooks/mailjet/EL-SECRETO-DEL-PASO-2
```

El secreto va en la dirección porque Mailjet no firma sus eventos. Sin él,
cualquiera que conociera la URL podría ensuciar la bitácora de entregas.

**5.** Comprueba:

```powershell
python -m jobs.probar_correo tu.correo@gmail.com
```

## Qué hacer si sigue bloqueando por contenido

En orden, lo que más mueve la aguja:

**El remitente tiene que estar validado en Mailjet, y con dominio propio.**
Mandar desde una dirección `@gmail.com` a través de Mailjet es el caso que
más se bloquea: la política de Gmail no autoriza a terceros a enviar en su
nombre, así que la alineación DMARC falla y Mailjet lo sabe antes de
intentarlo. Con un dominio propio validado en Mailjet —SPF y DKIM, que su
panel guía paso a paso— esto deja de pasar. Es la solución de verdad.

**El enlace de seguimiento.** El botón del correo no va directo a la
consulta: pasa por `/r/{id}/{firma}` para registrar el clic. Un redirector
hacia un dominio de reputación baja —`onrender.com`, `netlify.app`— es un
patrón que los escaneos castigan. Si el bloqueo persiste, prueba apuntando el
botón directo a la consulta, aunque se pierda la medición del clic.

**Las mayúsculas.** El encabezado del correo dice `VERIFICENTRO` en
versalitas y el asunto de prueba lleva `[PRUEBA]`. Son detalles, pero suman
en el puntaje del escaneo.

---

# Opción A · Google Apps Script

Un script en la cuenta de Google del verificentro recibe el correo ya armado
y lo manda con `MailApp`. Sale con la identidad de esa cuenta, igual que si
lo escribieras tú desde Gmail.

**A favor:** no hay que guardar la contraseña de aplicación de Gmail en el
servidor —solo viaja un token que inventas tú—, y funciona donde el puerto
587 está cerrado, que es común en los planes gratuitos.

**En contra:** la cuota. Una cuenta Gmail normal permite **100 destinatarios
al día**; una de Google Workspace, 1,500. Para un padrón de 1,500 clientes no
alcanza: el 1 de cada mes se juntan varios grupos de dígitos y pueden salir
cientos de avisos el mismo día.

**Sirve para arrancar y para probar. No para operar en grande.**

## Paso 1 · Crear el script

1. Entra a <https://script.google.com> con la cuenta desde la que van a salir
   los correos.
2. **Nuevo proyecto**. Ponle `Correo Verificentro`.
3. Borra lo que trae y pega el contenido de
   `backend/integraciones/apps_script/Codigo.gs`.

## Paso 2 · Poner el token

Arriba del archivo está esta línea:

```javascript
const TOKEN = 'CAMBIA-ESTO-POR-UNA-CADENA-LARGA-Y-UNICA';
```

Genera una cadena larga —en PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Pégala entre las comillas y guarda. **Anótala**, la vas a necesitar en el
paso 6.

No es un trámite: sin token, cualquiera que descubra la dirección del script
podría mandar correo a nombre del verificentro.

## Paso 3 · Declarar los permisos

Este paso evita el error más común al conectar Apps Script.

En el editor, **Configuración del proyecto** (el engrane de la izquierda) →
marca **«Mostrar el archivo de manifiesto appsscript.json en el editor»**.

Vuelve al editor: ahora aparece `appsscript.json` junto a `Codigo.gs`. Pega
ahí el contenido de `backend/integraciones/apps_script/appsscript.json`.

Lo que hace es nombrar explícitamente los permisos que el script necesita.
Sin eso, Google los deduce leyendo el código, y esa deducción se queda fija
en el momento en que autorizas: si después cambias el código, los permisos
que pide pueden no coincidir con los que te dieron. De ahí sale esto:

```
You do not have permission to call MailApp.getRemainingDailyQuota.
Required permissions: .../auth/script.send_mail
```

## Paso 4 · Autorizarlo

En el selector de funciones de arriba elige **`autorizarYProbar`** y dale
**Ejecutar**.

Google va a pedirte permiso para que el script mande correo a tu nombre.
Acepta. En el camino aparece una pantalla que dice *Google no ha verificado
esta aplicación*: es normal tratándose de un script tuyo. Entra a
**Configuración avanzada** → **Ir a Correo Verificentro (no seguro)**.

Al terminar debe llegarte un correo de prueba a ti mismo.

**Este paso no se salta.** Sin autorizar, el script contesta con una página
HTML en lugar de JSON y el sistema reporta *"el script no respondió en JSON"*.

## Paso 5 · Publicarlo

**Implementar** → **Nueva implementación** → el engrane → **Aplicación web**.

Hazlo DESPUÉS de autorizar, no antes: la implementación se queda con los
permisos que había cuando se creó.

| Campo | Valor |
|---|---|
| Descripción | `Puente de correo` |
| Ejecutar como | **Yo** |
| Quién tiene acceso | **Cualquier persona** |

«Cualquier persona» suena peor de lo que es: lo único que queda expuesto es
una dirección larga e impredecible, y sin el token el script no manda nada.
Si pones «solo yo», el servidor no puede llamarlo.

Al implementar te da una dirección así:

```
https://script.google.com/macros/s/AKfy.../exec
```

**Cópiala.** Tiene que terminar en `/exec`. La que termina en `/dev` es la de
pruebas y solo responde si tú tienes la sesión abierta en ese navegador.

Compruébalo pegándola en el navegador: debe contestar algo como

```json
{"ok":true,"servicio":"Puente de correo · CRM Verificentro",
 "cuenta":"no.responder.verificentro@gmail.com","restantes_hoy":100}
```

## Paso 6 · Conectarlo al sistema

En `backend\.env` y en **Render → Environment**, las mismas cuatro:

```
PROVEEDOR_CORREO=apps_script
APPS_SCRIPT_URL=https://script.google.com/macros/s/AKfy.../exec
APPS_SCRIPT_TOKEN=la-cadena-del-paso-2
CORREO_REMITENTE=no.responder.verificentro@gmail.com
```

`CORREO_REMITENTE` aquí se usa como dirección de respuesta: el remitente real
lo pone Google y es la cuenta dueña del script.

En Render, guardar reinicia el servicio solo.

## Paso 7 · Probarlo

Lo más fácil es **desde la pantalla**: entra a **Recordatorios** y dale a
**«Enviar un correo de prueba»**. Escribes la dirección y listo. No toca la
cola ni la bitácora, y se puede repetir las veces que haga falta —que es lo
que sirve para enseñarle el sistema a alguien.

Desde la terminal hace exactamente lo mismo:

```powershell
cd backend
.venv\Scripts\activate
python -m jobs.probar_correo tu.correo@gmail.com
```

Las dos vías mandan un aviso real, con su formato y su botón, no un «hola
mundo»: lo que se quiere ver es lo que recibe el cliente.

> **Cada vez que cambies el código del script** hay que volver a
> **Implementar → Administrar implementaciones → editar → Nueva versión**.
> Guardar no basta: la dirección `/exec` sigue sirviendo la versión anterior.
> Es lo que más confunde de Apps Script.

## Si sale «You do not have permission to call MailApp...»

Al script le faltan los permisos de correo. Pasa cuando la implementación
publicada se creó **antes** de que lo autorizaras: se quedó con los permisos
de aquel momento, y autorizar después no la actualiza sola.

En este orden:

1. Pega el `appsscript.json` del paso 3, si no lo habías hecho.
2. Ejecuta **`autorizarYProbar`** desde el editor y acepta la pantalla de
   permisos completa. Tiene que llegarte un correo de prueba a ti mismo.
3. **Implementar → Administrar implementaciones → el lápiz → Versión: Nueva
   versión → Implementar.** Este paso es el que casi siempre falta.
4. Abre la dirección `/exec` en el navegador. Debe decir
   `"permisos_de_correo": "correctos"`.

Si en el punto 2 Google no te muestra la pantalla de permisos porque cree que
ya autorizaste, quítale el acceso y vuelve a empezar: en
<https://myaccount.google.com/permissions>, busca el proyecto y elimina su
acceso. La próxima ejecución te lo volverá a pedir, ya con la lista completa.

---

# Opción B · SMTP

Sigue funcionando para Gmail. **Para Mailjet, mejor no**: por SMTP no hay
forma de enterarse de que descartó el mensaje después de aceptarlo. Es
exactamente el problema que nos costó encontrar.

```
PROVEEDOR_CORREO=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PUERTO=587
SMTP_USUARIO=no.responder.verificentro@gmail.com
SMTP_CONTRASENA=la-contrasena-de-aplicacion
CORREO_REMITENTE=no.responder.verificentro@gmail.com
```

La contraseña es una **contraseña de aplicación**, no la normal de la cuenta:
<https://myaccount.google.com/apppasswords>. Requiere verificación en dos
pasos activada.

Con Gmail, `CORREO_REMITENTE` tiene que ser la misma cuenta que
`SMTP_USUARIO`; si no, Google reescribe el remitente.

---

# Si llega pero cae en la carpeta de spam del destinatario

Ojo con la diferencia: esto es distinto de que Mailjet lo bloquee. Aquí el
correo sí salió y sí llegó; el filtro del que recibe lo mandó a spam.

Apps Script y el SMTP de Gmail salen por la misma puerta: la misma cuenta, los mismos
servidores de Google, la misma firma de `gmail.com`. Para el filtro del que
recibe es casi el mismo correo. **Cambiar de uno al otro no arregla el spam.**

Lo que sí pesa, en orden:

**1. El remitente es `@gmail.com`.** Un dominio gratuito mandando correo con
plantilla a muchos destinatarios es sospechoso por definición. Con dominio
propio se firma el correo (SPF, DKIM, DMARC) y el filtro sabe que es tuyo. Un
dominio cuesta unos $200 al año.

**2. El enlace de seguimiento.** El botón del correo no apunta a la consulta
directamente: pasa por `/r/{id}/{firma}` para registrar el clic. Un redirector
hacia un dominio de reputación baja —`onrender.com`, `netlify.app`— es un
patrón que los filtros castigan. Si el spam persiste, lo primero que yo
quitaría es ese redirector, aunque se pierda la medición del clic.

**3. El destinatario.** Las cuentas institucionales —`@uv.mx`,
`@estudiantes.uv.mx`— filtran mucho más duro que un Gmail personal. Que
llegue a un Gmail no significa que llegue a todos lados.

## Cuando quieran resolverlo de raíz

Un dominio propio más un proveedor de correo transaccional. Brevo da 300
correos al día gratis; Resend, 3,000 al mes. Los dos guían la configuración
de SPF y DKIM y reportan entregas y rebotes de verdad.

El sistema ya está preparado: cada proveedor es un adaptador en
`backend/app/mensajeria/`, y agregar uno nuevo es un archivo más y una línea
en `obtener_adaptador`. No hay que tocar el resto del sistema.
