"""Revisa el entorno y explica por qué no arranca el servidor.

    python -m jobs.diagnostico

No modifica nada: solo comprueba y reporta.
"""

import os
import socket
import sys
import traceback

VERDE, ROJO, AMARILLO, FIN = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def ok(texto):
    print(f"  {VERDE}OK{FIN}    {texto}")


def falla(texto):
    print(f"  {ROJO}FALLA{FIN} {texto}")


def aviso(texto):
    print(f"  {AMARILLO}AVISO{FIN} {texto}")


def titulo(texto):
    print(f"\n{texto}")
    print("-" * len(texto))


def revisar_python():
    titulo("1. Python")
    v = sys.version_info
    print(f"  Versión: {v.major}.{v.minor}.{v.micro}")
    print(f"  Ejecutable: {sys.executable}")

    if ".venv" in sys.executable or "venv" in sys.executable:
        ok("Estás dentro del entorno virtual.")
    else:
        falla("NO estás en el entorno virtual. Corre .venv\\Scripts\\activate")

    if (v.major, v.minor) >= (3, 14):
        aviso(
            f"Python {v.major}.{v.minor} es muy reciente. Algunas librerías "
            "todavía no lo soportan bien.\n        Si nada más funciona, "
            "instalar Python 3.12 suele resolverlo."
        )


def revisar_terminal():
    titulo("2. Terminal")
    if sys.stdin is None or not sys.stdin.isatty():
        falla(
            "La entrada estándar NO es interactiva.\n"
            "        Por eso no se puede escribir la contraseña, y puede ser "
            "también\n        la causa de que el servidor termine solo."
        )
    else:
        ok("La entrada es interactiva.")


def revisar_configuracion():
    titulo("3. Configuración")
    if not os.path.exists(".env"):
        falla("No existe el archivo .env. Cópialo de .env.example.")
        return None
    ok("El archivo .env existe.")

    try:
        from app.config import obtener_config

        config = obtener_config()
        destino = config.db_url.split("@")[-1]  # sin usuario ni contraseña
        ok(f"Configuración leída. Base de datos: {destino}")
        return config
    except Exception:
        falla("No se pudo leer la configuración:")
        traceback.print_exc()
        return None


def revisar_base_de_datos():
    titulo("4. Base de datos")
    try:
        from sqlalchemy import text

        from app.database import motor

        with motor.connect() as conexion:
            version = conexion.execute(text("SELECT VERSION()")).scalar()
        ok(f"Conexión correcta. MySQL {version}")

        from app.modelos import Empleado

        from app.database import SesionLocal

        with SesionLocal() as sesion:
            cuantos = sesion.query(Empleado).count()
        if cuantos:
            ok(f"Hay {cuantos} empleado(s) registrado(s).")
        else:
            aviso("No hay empleados. Corre: python -m jobs.crear_admin ...")
    except Exception as exc:
        falla(f"{type(exc).__name__}: {exc}")


def revisar_esquema():
    """Compara las columnas que espera el código contra las que hay.

    Es el error más común al recibir una versión nueva: si el esquema cambió y
    no se recargó, la API devuelve error 500 con un "Unknown column" enterrado
    en el traceback.
    """
    titulo("5. Esquema de la base")
    try:
        from sqlalchemy import inspect

        from app.database import Base, motor
        import app.modelos  # noqa: F401  registra todos los modelos

        inspector = inspect(motor)
        existentes = set(inspector.get_table_names())
        faltantes = []

        for tabla in Base.metadata.sorted_tables:
            if tabla.name not in existentes:
                faltantes.append(f"tabla '{tabla.name}' completa")
                continue
            columnas = {c["name"] for c in inspector.get_columns(tabla.name)}
            for columna in tabla.columns:
                if columna.name not in columnas:
                    faltantes.append(f"{tabla.name}.{columna.name}")

        if faltantes:
            falla("La base está atrasada respecto al código. Falta:")
            for f in faltantes[:12]:
                print(f"          {f}")
            print(
                "\n        Revisa la carpeta db/ por si hay una migración que"
                "\n        aplicar. Si no, recarga db/schema.sql (borra datos)."
            )
        else:
            ok("La base tiene todas las tablas y columnas que el código espera.")
    except Exception as exc:
        falla(f"No se pudo revisar: {type(exc).__name__}: {exc}")


def revisar_aplicacion():
    titulo("6. Aplicación")
    try:
        from app.main import aplicacion

        rutas = [r for r in aplicacion.routes if hasattr(r, "methods")]
        ok(f"La aplicación carga. {len(rutas)} rutas registradas.")
    except Exception:
        falla("La aplicación NO carga:")
        traceback.print_exc()


def revisar_puerto(puerto=8000):
    titulo(f"7. Puerto {puerto}")
    prueba = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        prueba.bind(("127.0.0.1", puerto))
        ok("El puerto está libre.")
    except OSError as exc:
        falla(
            f"No se puede usar el puerto: {exc}\n"
            f"        Arranca en otro:  python -m uvicorn app.main:aplicacion "
            f"--port 8001"
        )
    finally:
        prueba.close()


def revisar_uvicorn():
    titulo("8. Uvicorn")
    try:
        import uvicorn

        ok(f"Instalado, versión {uvicorn.__version__}")
    except ImportError:
        falla("No está instalado. Corre: pip install -r requirements.txt")
        return

    print("\n  Intentando arrancar el servidor…")
    print("  Si funciona, verás 'Uvicorn running' y se quedará corriendo.")
    print("  Detenlo con Ctrl+C.\n")
    try:
        uvicorn.run("app.main:aplicacion", host="127.0.0.1", port=8000,
                    log_level="info")
        aviso(
            "El servidor terminó por su cuenta, sin error.\n"
            "        Eso no es normal: algo lo está cerrando desde fuera."
        )
    except KeyboardInterrupt:
        print()
        ok("Lo detuviste tú. El servidor funcionaba bien.")
    except Exception:
        falla("El servidor tronó:")
        traceback.print_exc()


def main() -> int:
    print("=" * 62)
    print("  DIAGNÓSTICO — CRM Verificentro")
    print("=" * 62)
    revisar_python()
    revisar_terminal()
    revisar_configuracion()
    revisar_base_de_datos()
    revisar_esquema()
    revisar_aplicacion()
    revisar_puerto()
    revisar_uvicorn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
