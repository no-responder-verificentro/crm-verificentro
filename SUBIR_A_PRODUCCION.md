# Subir el proyecto: Git y servidor

Paso a paso, sin dar nada por sabido.

---

# PARTE 1 · Git y GitHub

## Qué es y por qué lo necesitas

**Git** guarda la historia de tu código: cada cambio, cuándo y por qué. Si algo
se rompe, regresas a como estaba. **GitHub** es donde vive esa historia en
internet, para que no dependa de tu laptop.

Sin esto, si se te echa a perder la computadora pierdes el proyecto completo.

## Paso 1 · Instalar Git

Descárgalo de <https://git-scm.com/download/win>. Instalador siguiente,
siguiente, siguiente: los valores por omisión están bien.

Cierra y abre PowerShell, y comprueba:

```powershell
git --version
```

Debe responder algo como `git version 2.x`.

## Paso 2 · Decirle quién eres

Una sola vez en tu vida, no por proyecto:

```powershell
git config --global user.name "Darly Juárez"
git config --global user.email "tu.correo@ejemplo.com"
```

Ese nombre queda escrito en cada cambio que hagas.

## Paso 3 · Crear la cuenta de GitHub

En <https://github.com> → Sign up. Es gratis.

Activa la verificación en dos pasos cuando te la ofrezca: GitHub la va a
exigir tarde o temprano.

## Paso 4 · Preparar el proyecto

```powershell
cd C:\proyectos\crm-verificentro\verificentro
git init
git add .
git status
```

`git status` te lista todo lo que se va a subir. **Revísalo con calma antes de
seguir.**

Busca que **NO aparezca** ninguna de estas:

- `.env` — ahí está la contraseña de MySQL y la del correo
- `.venv/` — son miles de archivos que se regeneran solos
- `node_modules/` — lo mismo

Si aparecen, el archivo `.gitignore` no está en su lugar. Debe estar en esta
misma carpeta, junto a `backend` y `frontend`.

Cuando esté limpio:

```powershell
git commit -m "Sistema completo: clientes, verificaciones, citas, recordatorios y chatbot"
```

## Paso 5 · Subirlo

En GitHub → botón verde **New** → nombre `crm-verificentro` → **Private**.

Privado, no público: el código no tiene contraseñas, pero sí la estructura de
los datos de sus clientes y la lógica del negocio.

**No marques** ninguna de las casillas de "Add a README", "Add .gitignore" ni
licencia. Ya los tienes.

GitHub te muestra unos comandos. Son estos:

```powershell
git remote add origin https://github.com/TU-USUARIO/crm-verificentro.git
git branch -M main
git push -u origin main
```

Te va a pedir usuario y contraseña. **La contraseña normal ya no funciona**:
hay que usar un *token*. GitHub abre una ventana del navegador para
autorizarlo; acepta y listo.

Refresca GitHub: ahí está tu proyecto.

## Paso 6 · El día a día

Cada vez que termines algo:

```powershell
git add .
git commit -m "Describe qué cambiaste"
git push
```

Y antes de empezar a trabajar, si lo tocaste desde otra computadora:

```powershell
git pull
```

**Un consejo que vale oro:** haz commit seguido, con mensajes que digan *qué*
cambiaste, no "cambios" ni "update". Dentro de seis meses vas a agradecerlo.

---

# PARTE 2 · Dónde va a vivir el sistema

Aquí hay que decidir, y la respuesta depende de para qué lo quieren.

## Opción A · La computadora del verificentro (gratis)

El sistema corre en una PC del negocio y los empleados lo usan desde cualquier
otra máquina de la misma red, escribiendo la dirección de esa computadora.

**A favor:** no cuesta nada, los datos se quedan en el negocio, no depende de
internet para operar, y es lo más rápido de montar.

**En contra:** la consulta pública y el chatbot no se ven desde fuera, y la PC
tiene que estar siempre prendida.

**Es lo que yo haría para arrancar.** Los empleados ya están ahí, y el correo
sale igual porque solo necesita internet de salida, no que los demás entren.

## Opción B · Un servidor en internet (unos $100 pesos al mes)

Un VPS en Hetzner, DigitalOcean o Vultr. Por unos 5 o 6 dólares al mes tienes
una máquina prendida siempre, con dirección pública.

**A favor:** la consulta pública y el chatbot quedan accesibles para los
clientes, el sistema no depende de una PC del local, y cuando conecten WhatsApp
el webhook ya tiene a dónde llegar.

**En contra:** cuesta, y hay que administrarlo.

## Opción C · Gratis en internet, para mostrar (no para operar)

Render tiene un plan gratuito. Sirve para enseñarle el sistema a tu jefe desde
cualquier lado, pero **apaga el servidor cuando nadie lo usa** y tarda casi un
minuto en despertar. Para una demostración está bien; para operar, no.

## Mi recomendación

**Arranquen con la Opción A.** Es gratis, es hoy, y resuelve el 90% del valor:
el mostrador captura, los recordatorios salen por correo, y el jefe ve sus
reportes.

Cuando decidan conectar WhatsApp, pasan a la Opción B, que es cuando de verdad
hace falta una dirección pública.

---

# PARTE 3 · Montarlo en la computadora del verificentro

## Paso 1 · Preparar esa computadora

Instalar, en este orden:

1. **Python 3.12** — <https://python.org>, marcando *Add Python to PATH*
2. **MySQL** — <https://dev.mysql.com/downloads/installer/>, anotando la
   contraseña de root
3. **Node.js** — <https://nodejs.org>, versión LTS
4. **Git** — <https://git-scm.com/download/win>

## Paso 2 · Bajar el proyecto

```powershell
mkdir C:\verificentro
cd C:\verificentro
git clone https://github.com/TU-USUARIO/crm-verificentro.git .
```

## Paso 3 · Base de datos

```powershell
mysql -u root -p --default-character-set=utf8mb4 -e "CREATE DATABASE verificentro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p --default-character-set=utf8mb4 < db\schema.sql
```

## Paso 4 · Backend

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

En el `.env`, lo mínimo:

```
ENTORNO=produccion
DB_URL=mysql+pymysql://root:TU_CONTRASENA@localhost:3306/verificentro?charset=utf8mb4
JWT_SECRETO=      # ver abajo
PROVEEDOR_CORREO=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PUERTO=587
SMTP_USUARIO=verificentroruizcortinesx@gmail.com
SMTP_CONTRASENA=la-contrasena-de-aplicacion
CORREO_REMITENTE=verificentroruizcortinesx@gmail.com
CANALES_ACTIVOS=["correo"]
```

El secreto se genera así, y se pega tal cual:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Con `ENTORNO=produccion` el servidor **se niega a arrancar** si dejas el
secreto de ejemplo. Es a propósito.

Crea tu usuario y comprueba que todo esté en orden:

```powershell
python -m jobs.crear_admin "Tu Nombre" tu.correo@verificentro.mx TuContrasena123
python -m jobs.diagnostico
```

## Paso 5 · Averiguar la dirección de esa computadora

```powershell
ipconfig
```

Busca **Dirección IPv4**, algo como `192.168.1.50`. Esa es la dirección que
van a escribir los demás.

## Paso 6 · Frontend

```powershell
cd ..\frontend
npm install
notepad .env
```

Pon la IP de la computadora, no localhost, porque las otras máquinas van a
buscar ahí:

```
VITE_API_URL=http://192.168.1.50:8000/api/v1
```

Y compila la versión final:

```powershell
npm run build
```

Eso crea una carpeta `dist` con la aplicación lista.

## Paso 7 · Dejar los dos corriendo

Dos ventanas de PowerShell, cada una con lo suyo:

```powershell
cd C:\verificentro\backend
.venv\Scripts\activate
python -m uvicorn app.main:aplicacion --host 0.0.0.0 --port 8000
```

El `--host 0.0.0.0` es la parte importante: significa "acepta conexiones de
otras computadoras". Con `127.0.0.1` solo se vería desde esa misma máquina.

```powershell
cd C:\verificentro\frontend
npx serve dist -l 5173
```

Desde cualquier computadora de la red, `http://192.168.1.50:5173`.

## Paso 8 · Permitir el paso en el firewall

Windows bloquea por omisión. Una vez, como administrador:

```powershell
New-NetFirewallRule -DisplayName "Verificentro API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Verificentro Web" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow
```

## Paso 9 · Que los recordatorios salgan solos

Esto es lo que convierte el proyecto en un sistema. Abre el **Programador de
tareas** de Windows → Crear tarea básica.

**Tarea 1 — generar la cola**

- Nombre: `Verificentro - generar recordatorios`
- Desencadenador: Diariamente, 7:00 a. m.
- Acción: Iniciar un programa
  - Programa: `C:\verificentro\backend\.venv\Scripts\python.exe`
  - Argumentos: `-m jobs.generar_recordatorios`
  - Iniciar en: `C:\verificentro\backend`

**Tarea 2 — enviarlos**

Igual, pero a las **9:00 a. m.** y con argumentos `-m jobs.enviar_pendientes`.

En las dos, marca **Ejecutar tanto si el usuario inició sesión como si no**.

Para probar sin esperar al día siguiente: clic derecho en la tarea → Ejecutar.

## Paso 10 · Respaldos

Si esto se pierde, se pierde el padrón de clientes. Una tarea más, diaria a
las 11 de la noche:

- Programa: `cmd.exe`
- Argumentos:
  `/c "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe" -u root -pTU_CONTRASENA verificentro > C:\respaldos\verificentro-%date:~-4%%date:~3,2%%date:~0,2%.sql`

Crea antes la carpeta `C:\respaldos`. Y **copia esos archivos de vez en cuando
a otro lado** —una USB, Drive—: un respaldo en el mismo disco no sirve de nada
si el disco es lo que falla.

---

# Lista de verificación

Antes de dárselo a los empleados:

- [ ] El proyecto está en GitHub, privado, y `.env` **no** se subió
- [ ] `python -m jobs.diagnostico` sale todo en verde
- [ ] `python -m jobs.probar_correo tu.correo@gmail.com` llega
- [ ] Desde otra computadora de la red abre `http://IP:5173`
- [ ] Los tres perfiles creados, cada quien con su cuenta
- [ ] Las dos tareas programadas corren bien al ejecutarlas a mano
- [ ] El respaldo genera un archivo que se puede abrir
- [ ] `JWT_SECRETO` es uno generado, no el de ejemplo
- [ ] El aviso de privacidad está impreso en el mostrador

Ese último sigue pendiente desde el primer día. El sistema guarda el
consentimiento con fecha y versión, pero el documento en sí no existe todavía.
