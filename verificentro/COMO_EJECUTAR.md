# Cómo ejecutar el sistema

Guía para Windows. Cada instrucción viene con el comando exacto y con lo que
deberías ver si salió bien.

---

## Versión de Python: usa la 3.12

**No uses Python 3.13 ni 3.14.** Las versiones recién salidas tardan meses en
que todas las librerías tengan sus binarios compilados para Windows, y
mientras tanto el servidor muere sin dar ningún mensaje, con código de salida
`-1073741819` (violación de acceso). No es un error del proyecto y no se puede
arreglar desde el código.

```powershell
winget install Python.Python.3.12
```

Cierra la terminal y abre una nueva. Comprueba que aparezca en la lista:

```powershell
py -0
```

Y crea el entorno virtual apuntando explícitamente a esa versión:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python --version          # debe decir 3.12.x
pip install -r requirements.txt
```

---

## Antes que nada: qué es una terminal

Cuando digo *"corre esto"* o *"ejecuta esto"*, me refiero a escribirlo en una
ventana de terminal y presionar Enter.

Para abrir una en la carpeta correcta: entra a la carpeta del proyecto en el
Explorador de archivos, haz clic en la barra de dirección de arriba, escribe
`powershell` y presiona Enter. Se abre una ventana negra ya parada en esa
carpeta.

Sabes en qué carpeta estás porque aparece al inicio de la línea:

```
PS C:\proyectos\crm-verificentro\backend>
```

Casi todos los errores de *"no se encontró el archivo"* son porque la terminal
está parada en otra carpeta. Para cambiarte usas `cd` (change directory):

```powershell
cd C:\proyectos\crm-verificentro\backend
```

---

## El sistema tiene tres piezas

Piensa en un restaurante:

**MySQL** es la bodega. Guarda los datos. Se queda prendido solo, no hay que
arrancarlo cada vez.

**El backend** es la cocina. Recibe los pedidos, aplica las reglas (calcula el
periodo, valida la placa, revisa permisos) y guarda o consulta en la bodega.
Vive en la carpeta `backend`.

**El frontend** es el comedor. Es lo que la persona ve y toca en el navegador.
No sabe nada de reglas: todo se lo pregunta al backend. Vive en `frontend`.

Para trabajar necesitas **la cocina y el comedor prendidos al mismo tiempo**, o
sea dos terminales abiertas a la vez. No es que una reemplace a la otra.

---

## 1. Comprobar que MySQL está prendido

MySQL normalmente arranca solo con Windows. Para confirmarlo:

```powershell
mysql -u root -p --default-character-set=utf8mb4 -e "SELECT VERSION();"
```

Te pide tu contraseña de MySQL (al escribirla no se ve nada, es normal) y
responde con el número de versión.

Si dice que `mysql` no se reconoce como comando, MySQL no está en el PATH.
Usa la ruta completa:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p -e "SELECT VERSION();"
```

---

## 2. Ejecutar el backend

**Qué significa:** dejar corriendo el programa de Python que atiende las
peticiones. Mientras esté corriendo, la terminal se queda "ocupada"
mostrando lo que pasa. Eso es normal y correcto.

Abre una terminal y escribe, línea por línea:

```powershell
cd C:\proyectos\crm-verificentro\backend
.venv\Scripts\activate
python -m uvicorn app.main:aplicacion --reload
```

Usa `python -m uvicorn` y no `uvicorn` a secas: así se garantiza que se use el
del entorno virtual y no otro que ande suelto en el sistema.

Si el comando termina sin imprimir nada, quítale `--reload`:

```powershell
python -m uvicorn app.main:aplicacion
```

El `--reload` levanta un proceso hijo que vigila los archivos, y ese mecanismo
falla en algunas combinaciones de Python y Windows. Sin él todo funciona
igual, solo que hay que reiniciar a mano tras cada cambio.

La primera línea te para en la carpeta. La segunda enciende el entorno virtual
(verás `(.venv)` al inicio de la línea). La tercera arranca el servidor.

**Cómo sabes que funcionó.** Aparece algo así y se queda ahí:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Compruébalo abriendo <http://localhost:8000/salud> en el navegador. Debe
responder `{"estado":"ok","entorno":"desarrollo"}`.

**Para detenerlo:** presiona `Ctrl` + `C` en esa terminal.

**Deja esa ventana abierta.** Si la cierras, el backend se apaga y el frontend
deja de funcionar.

---

## 3. Ejecutar el frontend

**Qué significa:** arrancar el servidor de desarrollo que arma la página y la
sirve en el navegador.

Abre una **segunda** terminal, sin cerrar la del backend:

```powershell
cd C:\proyectos\crm-verificentro\frontend
npm run dev
```

**Cómo sabes que funcionó:**

```
  VITE ready in 412 ms
  ➜  Local:   http://localhost:5173/
```

Abre <http://localhost:5173> y te aparece la pantalla de inicio de sesión.

**Para detenerlo:** `Ctrl` + `C`.

Mientras esté corriendo, cada vez que guardes un cambio en el código la página
se actualiza sola. No hay que reiniciar nada.

---

## 4. Correr las pruebas

**Qué significa:** ejecutar los 133 casos que comprueban que la lógica sigue
correcta. Corre esto cada vez que cambies algo del backend.

```powershell
cd C:\proyectos\crm-verificentro\backend
.venv\Scripts\activate
pytest
```

Esperado: `72 passed, 61 skipped`. Los saltados son los que necesitan una base
de datos de pruebas. Para incluirlos:

```powershell
$env:TEST_DB_URL="mysql+pymysql://root:TU_CONTRASENA@localhost/verificentro_test?charset=utf8mb4"
pytest
```

Ahora deben pasar las 133. Esa base `verificentro_test` se borra y se vuelve a
crear en cada corrida, así que **no la apuntes a la base real**.

---

## Llenar la base con datos de demostración

Sirve para ver las pantallas con contenido y para tener algo que enseñar en
una junta sin capturar veinte clientes a mano.

```powershell
cd backend
.venv\Scripts\activate
python -m jobs.datos_prueba
```

Crea 8 clientes y 10 vehículos con dígitos de placa repartidos, de forma que
siempre haya alguien al corriente, alguien con el periodo abierto y alguien
vencido, sin importar en qué mes lo corras. Incluye historial de
verificaciones, un rechazo y un par de citas.

Para quitarlos (tu usuario administrador NO se borra):

```powershell
python -m jobs.datos_prueba --borrar
```

Solo funciona con `ENTORNO=desarrollo` en el archivo `.env`.

---

## Conectar el correo (Gmail)

El correo no depende de Meta: se puede conectar hoy.

**1. Activa la verificación en dos pasos** en la cuenta
`verificentroruizcortinesx@gmail.com`, en
<https://myaccount.google.com/security>. Sin esto no aparece el siguiente paso.

**2. Genera una contraseña de aplicación** en
<https://myaccount.google.com/apppasswords>. Ponle de nombre "Verificentro CRM".
Google te da 16 letras en cuatro bloques. **Cópiala en ese momento: no se
vuelve a mostrar.**

**3. Ponla en el archivo `.env`** del backend:

```
PROVEEDOR_CORREO=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PUERTO=587
SMTP_USUARIO=verificentroruizcortinesx@gmail.com
SMTP_CONTRASENA=las16letrassinespacios
CORREO_REMITENTE=verificentroruizcortinesx@gmail.com
NOMBRE_REMITENTE=Verificentro
URL_PUBLICA=http://localhost:8000
```

La contraseña va sin espacios. Y el `.env` nunca se sube a Git.

**4. Prueba antes de conectar nada:**

```powershell
python -m jobs.probar_correo tu.correo.personal@gmail.com
```

Te manda un aviso real, con su formato y su enlace, para que veas cómo le
llega al cliente. Si llega, el SMTP está bien.

**5. Ya conectado**, los recordatorios por correo salen de verdad:

```powershell
python -m jobs.enviar_pendientes
```

### Límites de Gmail

Una cuenta gratuita permite unos **500 destinatarios al día**. Para empezar
sobra, pero conviene tener el número en mente: si el padrón crece a más de
250 clientes con correo, un día de avisos grande puede toparlo. Cuando eso
pase, hay servicios pensados para esto (Brevo, Amazon SES) que cuestan poco
y no tienen ese tope.

### Quién lee las bajas

Los correos traen "responde BAJA" y la cabecera de baja apunta a esa misma
cuenta. Alguien tiene que revisar esa bandeja: cuando llegue una baja, se
marca al cliente desde la ficha con **Baja de contacto**.

---

## Los recordatorios

Son dos comandos y hacen cosas distintas:

```powershell
python -m jobs.generar_recordatorios     # llena la cola. NO envía nada.
python -m jobs.enviar_pendientes         # toma la cola y la entrega
```

**Es normal que el primero diga "0 nuevos en la cola" casi todos los días.**
El sistema solo genera un aviso cuando la fecha coincide exactamente con uno
de los cinco momentos del periodo. Está pensado para correr cada mañana: hoy
nada, mañana nada, y el día que toca aparecen.

Para ver la pantalla con contenido, o para ponerte al corriente si el
servidor estuvo apagado, genera varios días de golpe:

```powershell
python -m jobs.generar_recordatorios --dias 90
```

Adelantar la generación es seguro: cada recordatorio lleva su fecha de salida
y el job de envío la respeta.

En producción se programan con el Programador de tareas de Windows:

```
07:00  python -m jobs.generar_recordatorios
09:00  python -m jobs.enviar_pendientes
```

---

## Rutina de un día de trabajo

1. Terminal 1: `cd backend`, `.venv\Scripts\activate`, `uvicorn app.main:aplicacion --reload`
2. Terminal 2: `cd frontend`, `npm run dev`
3. Navegador: <http://localhost:5173>
4. Al terminar: `Ctrl` + `C` en las dos terminales

---

## Cuando te mando archivos nuevos

Descomprime **encima** de tu carpeta y acepta reemplazar. El zip no trae
`.venv`, ni `.env`, ni `.git`, así que esos se quedan.

Después, con el entorno encendido:

```powershell
cd C:\proyectos\crm-verificentro\backend
.venv\Scripts\activate
pip install -r requirements.txt
```

Si no hay dependencias nuevas termina en un segundo diciendo que ya está todo.
Córrelo siempre, por si acaso.

**Si algo deja de funcionar después de actualizar**, casi siempre es que la
base quedó atrasada respecto al código. El diagnóstico lo detecta y dice
exactamente qué falta:

```powershell
python -m jobs.diagnostico
```

Cuando el esquema cambia, dejo una **migración** en la carpeta `db\`, que
agrega lo que falta **sin borrar datos**:

```powershell
mysql -u root -p --default-character-set=utf8mb4 verificentro < db\migracion_01_bloques_por_cita.sql
```

Solo si no hay migración disponible hay que recargar todo. **Esto sí borra
los datos**, así que únicamente mientras estemos en desarrollo:

```powershell
cd C:\proyectos\crm-verificentro
mysql -u root -p --default-character-set=utf8mb4 -e "DROP DATABASE IF EXISTS verificentro;"
mysql -u root -p --default-character-set=utf8mb4 < db\schema.sql
cd backend
python -m jobs.crear_admin "Darly Juárez" darly@verificentro.mx
```

Cuida el **espacio** entre el nombre entre comillas y el correo. Sin él,
PowerShell los junta en un solo argumento y el comando no hace nada.

Si tu terminal no te deja escribir la contraseña, pásala como tercer
argumento:

```powershell
python -m jobs.crear_admin "Darly Juárez" darly@verificentro.mx miClave123
```

El último paso es necesario porque al borrar la base se borran también los
empleados, incluido tú.

---

## Si algo no arranca

```powershell
python -m jobs.diagnostico
```

Revisa versión de Python, entorno virtual, si la terminal es interactiva,
configuración, base de datos, la aplicación, el puerto y uvicorn. Al final
intenta arrancar el servidor mostrando cualquier error.

---

## Errores comunes

**`No module named uvicorn`** — no está encendido el entorno virtual. Fíjate
si la línea empieza con `(.venv)`. Si no, corre `.venv\Scripts\activate`.
Hay que hacerlo **cada vez que abres una terminal nueva**; no queda encendido
para siempre.

Para comprobar cuál Python estás usando:

```powershell
python -c "import sys; print(sys.executable)"
```

Debe apuntar a `...\backend\.venv\Scripts\python.exe`.


**`No module named 'app'`** — la terminal está parada en la carpeta
equivocada. `pytest` y `uvicorn` se corren desde `backend`, no desde la raíz ni
desde dentro de `app`.

**`No se pudo conectar con el servidor`** en el navegador — el backend no está
corriendo. Revisa la terminal 1.

**`Access denied for user 'root'`** — la contraseña de MySQL en tu archivo
`.env` no es la correcta.

**`Incorrect string value` con acentos** — le faltó
`--default-character-set=utf8mb4` al comando de `mysql`.

**`'.venv\Scripts\activate' no se reconoce`** — todavía no has creado el
entorno virtual:

```powershell
cd C:\proyectos\crm-verificentro\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**El comando termina solo, sin imprimir nada, con código `-1073741819`** —
ese número es `0xC0000005`, violación de acceso: una librería en C se cayó.
Casi siempre es una extensión nativa incompatible con tu versión de Python.
Arranca sin código nativo para confirmarlo:

```powershell
python -m uvicorn app.main:aplicacion --http h11 --ws none
```

Si así sí arranca, quita las extensiones:

```powershell
pip uninstall -y httptools watchfiles
```

Si aun así falla, instala **Python 3.12** en vez de 3.13 o 3.14. Las versiones
recién salidas tardan meses en tener todas las librerías compiladas.

**`No se puede cargar el archivo ... activate.ps1 porque la ejecución de
scripts está deshabilitada`** — es una restricción de Windows. Se habilita
solo para tu usuario con:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
