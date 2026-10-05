# Desplegar en Aiven + Render + Netlify

Todo gratis. Tres servicios, cada uno con lo suyo:

```
Aiven     →  la base de datos MySQL
Render    →  el backend (la API en Python)
Netlify   →  el frontend (lo que ve la gente)
```

**El orden importa.** Cada paso necesita un dato del anterior:

```
1. GitHub   →  los otros tres leen el código de ahí
2. Aiven    →  da la dirección de la base
3. Render   →  necesita esa dirección. Devuelve la URL de la API
4. Netlify  →  necesita la URL de la API. Devuelve el dominio público
5. Volver a Render a ponerle el dominio de Netlify
```

Ese último paso es el que se olvida y deja la pantalla en blanco. Lo explico
al final.

---

# PASO 1 · GitHub

Si aún no está:

```powershell
cd C:\proyectos\crm-verificentro\verificentro
git init
git add .
git status
```

**Revisa que NO aparezca `.env`.** Ahí están las contraseñas. Si sale, el
`.gitignore` no está en esa carpeta.

```powershell
git commit -m "Sistema completo listo para desplegar"
```

En GitHub → **New** → `crm-verificentro` → **Private** → sin marcar ninguna
casilla extra.

```powershell
git remote add origin https://github.com/TU-USUARIO/crm-verificentro.git
git branch -M main
git push -u origin main
```

---

# PASO 2 · Aiven · la base de datos

**2.1** Entra a <https://aiven.io> y crea cuenta.

**2.2** Create service → **MySQL** → plan **Free** → región la más cercana
(suele ser `aws-us-east-1`) → nombre `verificentro-db` → Create.

Tarda unos minutos en quedar en *Running*.

**2.3** En la pestaña **Overview** anota:

- Host
- Port (no es 3306, Aiven usa otro)
- User (suele ser `avnadmin`)
- Password
- Database name (suele ser `defaultdb`)

**2.4** Descarga el **CA Certificate** (el botón está ahí mismo). Es un
archivo `ca.pem`. Aiven exige conexión cifrada y sin ese archivo no deja
entrar.

Guárdalo en `backend/ca.pem`. **Sí se sube a Git**: es un certificado público,
no un secreto.

```powershell
git add backend/ca.pem
git commit -m "Certificado de Aiven"
git push
```

**2.5** Carga el esquema. Desde tu computadora:

```powershell
mysql -h EL-HOST -P EL-PUERTO -u avnadmin -p --ssl-ca=backend\ca.pem defaultdb < db\schema.sql
```

Te pide la contraseña de Aiven.

**2.6** Comprueba que cargó:

```powershell
mysql -h EL-HOST -P EL-PUERTO -u avnadmin -p --ssl-ca=backend\ca.pem defaultdb -e "SHOW TABLES;"
```

Deben salir las 14 tablas.

**2.7** Arma la cadena de conexión y guárdala en un bloc de notas, la vas a
necesitar en el paso siguiente:

```
mysql+pymysql://avnadmin:LA-CONTRASENA@EL-HOST:EL-PUERTO/defaultdb?charset=utf8mb4&ssl_ca=ca.pem
```

---

# PASO 3 · Render · el backend

**3.1** <https://render.com> → crea cuenta con GitHub, así ya ve tus
repositorios.

**3.2** New → **Web Service** → conecta `crm-verificentro`.

Render detecta el archivo `render.yaml` y llena casi todo solo. Si te pide los
datos a mano, son estos:

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:aplicacion --host 0.0.0.0 --port $PORT`
- Instance Type: **Free**

**3.3** En **Environment**, agrega las variables. Las que faltan por capturar:

| Variable | Valor |
|---|---|
| `DB_URL` | la cadena del paso 2.7 |
| `SMTP_USUARIO` | `no.responder.verificentro@gmail.com` |
| `SMTP_CONTRASENA` | la contraseña de aplicación de Gmail |
| `CORREO_REMITENTE` | `no.responder.verificentro@gmail.com` |
| `URL_PUBLICA` | la URL que Render te dio, sin barra al final |
| `URL_CONSULTA` | `https://TU-SITIO.netlify.app/consulta` |
| `ORIGENES_PERMITIDOS` | `["https://TU-SITIO.netlify.app"]` |

Las dos últimas todavía no las sabes. **Pon cualquier cosa por ahora** y
regresa en el paso 5.

`JWT_SECRETO` lo genera Render solo. No lo toques.

**3.4** Create Web Service. El primer despliegue tarda unos minutos.

**3.5** Comprueba. Render te da una URL como
`https://verificentro-api.onrender.com`. Ábrela con `/salud` al final:

```
https://verificentro-api.onrender.com/salud
```

Debe responder `{"estado":"ok","entorno":"produccion"}`.

**3.6** Crea tu usuario administrador. En Render → pestaña **Shell**:

```bash
python -m jobs.crear_admin "Darly Juárez" darly@verificentro.mx TuContrasena123
```

---

# PASO 4 · Netlify · el frontend

**4.1** <https://app.netlify.com> → Add new site → Import an existing project
→ GitHub → `crm-verificentro`.

Netlify lee `netlify.toml` y ya sabe qué hacer. Si te lo pide a mano:

- Base directory: `frontend`
- Build command: `npm run build`
- Publish directory: `frontend/dist`

**4.2** Antes de desplegar, en **Environment variables**, agrega una:

```
VITE_API_URL = https://verificentro-api.onrender.com/api/v1
```

Ojo con el `/api/v1` al final. Sin eso, nada funciona.

**Importante:** en Vite las variables se incrustan **al compilar**, no se leen
al abrir la página. Si la cambias después, hay que volver a desplegar.

**4.3** Deploy site.

**4.4** Netlify te da un dominio como `https://pequeno-nombre-123.netlify.app`.
Puedes cambiarlo en Site configuration → Change site name, a algo como
`verificentro-ruiz-cortines`.

**Anota ese dominio.**

---

# PASO 5 · Cerrar el círculo

Aquí es donde se atora todo el mundo. Vuelve a **Render → Environment** y
corrige las dos variables que dejaste en blanco:

```
URL_CONSULTA        = https://TU-SITIO.netlify.app/consulta
ORIGENES_PERMITIDOS = ["https://TU-SITIO.netlify.app"]
```

Guarda. Render se reinicia solo.

**Por qué importa:** el navegador bloquea que una página de un dominio llame a
otro, salvo que ese otro lo autorice. Si el dominio de Netlify no está en
`ORIGENES_PERMITIDOS`, la pantalla de inicio de sesión se queda cargando para
siempre **sin mostrar ningún error visible**. En la consola del navegador —F12
— aparece algo de CORS. Es el síntoma más confuso de todo el despliegue.

---

# PASO 6 · Los recordatorios

Render gratuito **no tiene tareas programadas**, así que los jobs siguen
corriendo en la computadora del verificentro, contra la base de Aiven.

No es un parche: es mejor así. Esa máquina está prendida en horario de trabajo
y no depende de que Render esté despierto.

En esa computadora, el `.env` del backend apunta a Aiven igual que Render:

```
DB_URL=mysql+pymysql://avnadmin:...@host:puerto/defaultdb?charset=utf8mb4&ssl_ca=ca.pem
PROVEEDOR_CORREO=smtp
SMTP_HOST=smtp.gmail.com
SMTP_USUARIO=no.responder.verificentro@gmail.com
SMTP_CONTRASENA=...
CANALES_ACTIVOS=["correo"]
URL_PUBLICA=https://verificentro-api.onrender.com
URL_CONSULTA=https://TU-SITIO.netlify.app/consulta
```

Y las dos tareas en el Programador de tareas de Windows:

- **7:00 a. m.** → `-m jobs.generar_recordatorios`
- **9:00 a. m.** → `-m jobs.enviar_pendientes`

El detalle completo está en `SUBIR_A_PRODUCCION.md`, paso 9.

---

# PASO 7 · Comprobar que todo quedó

- [ ] `https://TU-API.onrender.com/salud` responde ok
- [ ] Entras al sistema desde el dominio de Netlify
- [ ] Das de alta un cliente de prueba y aparece en el listado
- [ ] `https://TU-SITIO.netlify.app/consulta` abre y el chat contesta
- [ ] Recargar `/consulta` **no** da 404 (eso lo arregla `_redirects`)
- [ ] Desde la computadora del verificentro:
      `python -m jobs.diagnostico` sale en verde contra Aiven
- [ ] `python -m jobs.probar_correo tu.correo@gmail.com` llega

---

# Lo que hay que saber de los planes gratuitos

**Render duerme el servicio tras 15 minutos sin uso.** El primer visitante
después espera entre 30 y 60 segundos. Durante el día no pasa, porque el
mostrador lo mantiene despierto; de madrugada sí.

**Aiven limita las conexiones.** Por eso el `.env` trae `DB_POOL=3`. No lo
subas sin necesidad: entre Render y los jobs se agotan rápido.

**Netlify no duerme.** El frontend siempre carga al instante; lo que tarda es
la primera respuesta de la API.

**Render redespliega solo** cada vez que haces `git push` a `main`. Netlify
también. O sea que actualizar el sistema es:

```powershell
git add .
git commit -m "Qué cambiaste"
git push
```

Y en dos o tres minutos está en línea.

---

# Si algo no funciona

**La pantalla de inicio se queda cargando, sin error** — es CORS.
`ORIGENES_PERMITIDOS` en Render no tiene el dominio exacto de Netlify.
Revisa que sea `https://` y sin barra al final.

**"No se pudo conectar con el servidor"** — o Render está despertando (espera
un minuto y recarga), o `VITE_API_URL` en Netlify está mal. Acuérdate de que
hay que volver a desplegar Netlify después de cambiarla.

**Recargar `/consulta` da 404** — falta `frontend/public/_redirects`.

**El backend no arranca en Render** — ve a Logs. Si dice *Access denied*, la
`DB_URL` está mal. Si menciona SSL, falta `&ssl_ca=ca.pem` o el archivo no se
subió a Git.

**`JWT_SECRETO` es demasiado corto** — en producción el servidor se niega a
arrancar con el de ejemplo. Deja que Render lo genere.
