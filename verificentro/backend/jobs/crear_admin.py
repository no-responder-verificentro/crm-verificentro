"""Crea el primer administrador.

Problema del huevo y la gallina: el endpoint de alta de empleados exige ser
administrador, así que el primero no se puede crear por la API.

    python -m jobs.crear_admin "Darly Juárez" darly@verificentro.mx

Pide la contraseña sin mostrarla en pantalla. Si tu terminal no lo permite
—pasa en algunas configuraciones de PowerShell— pásala como tercer argumento:

    python -m jobs.crear_admin "Darly Juárez" darly@verificentro.mx miClave123

Ojo: así queda en el historial de la terminal. Cámbiala después desde el
sistema, o limpia el historial.
"""

import getpass
import sys

from app.database import SesionLocal
from app.modelos import Empleado, Perfil
from app.seguridad import hashear_contrasena

MINIMO = 8


def _pedir_contrasena() -> str | None:
    """Pide la contraseña dos veces. Devuelve None si algo salió mal."""
    try:
        contrasena = getpass.getpass("Contraseña: ")
        confirmacion = getpass.getpass("Confírmala: ")
    except (EOFError, KeyboardInterrupt):
        print(
            "\nNo se pudo leer la contraseña desde esta terminal.\n"
            "Pásala como tercer argumento:\n"
            '    python -m jobs.crear_admin "Nombre" correo@dominio.mx miClave123'
        )
        return None

    if not contrasena:
        print("No se recibió ninguna contraseña. Pásala como tercer argumento.")
        return None
    if contrasena != confirmacion:
        print("Las contraseñas no coinciden.")
        return None
    return contrasena


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        if len(sys.argv) == 2:
            print(
                "\nRecibí un solo argumento. Revisa que haya un ESPACIO entre\n"
                "el nombre entre comillas y el correo."
            )
        return 1

    nombre = sys.argv[1]
    correo = sys.argv[2].strip().lower()

    if "@" not in correo:
        print(f"'{correo}' no parece un correo. ¿Faltó el espacio antes de él?")
        return 1

    with SesionLocal() as sesion:
        if sesion.query(Empleado).filter(Empleado.correo == correo).one_or_none():
            print(f"Ya existe una cuenta con el correo {correo}.")
            return 1

        contrasena = sys.argv[3] if len(sys.argv) == 4 else _pedir_contrasena()
        if contrasena is None:
            return 1

        if len(contrasena) < MINIMO:
            print(f"La contraseña debe tener al menos {MINIMO} caracteres.")
            return 1

        sesion.add(
            Empleado(
                nombre=nombre,
                correo=correo,
                hash_contrasena=hashear_contrasena(contrasena),
                perfil=Perfil.ADMINISTRADOR,
            )
        )
        sesion.commit()

    print(f"Listo. {nombre} ya puede entrar como administrador con {correo}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
