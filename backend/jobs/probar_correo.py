"""Manda un correo de prueba para verificar la configuración.

    python -m jobs.probar_correo tu.correo@gmail.com

Sirve para separar dos problemas que se confunden: que las credenciales estén
mal, o que el sistema de recordatorios tenga un error. Si esto llega, el
correo está bien y cualquier falla posterior es del sistema.

Usa el mismo adaptador que los recordatorios de verdad, sea SMTP, Apps Script
o consola. Si está en consola te lo dice y no finge que mandó nada.
"""

import sys
from datetime import date

from app.config import obtener_config
from app.dominio.calendario import ventanas_del_anio
from app.mensajeria import obtener_adaptador
from app.mensajeria.base import Mensaje
from app.mensajeria.plantillas import construir
from app.modelos.recordatorio import Canal


def _mostrar_configuracion(config, destino: str) -> None:
    print("Configuración leída del .env:")
    print(f"  Proveedor : {config.proveedor_correo}")

    if config.proveedor_correo == "smtp":
        print(f"  Servidor  : {config.smtp_host}:{config.smtp_puerto}")
        print(f"  Usuario   : {config.smtp_usuario or '(vacío)'}")
        print(f"  Contraseña: {'*' * 8 if config.smtp_contrasena else '(vacía)'}")
    elif config.proveedor_correo == "apps_script":
        print(f"  Script    : {config.apps_script_url or '(vacío)'}")
        print(f"  Token     : {'*' * 8 if config.apps_script_token else '(vacío)'}")

    print(f"  Remitente : {config.correo_remitente}")
    print(f"  Destino   : {destino}\n")


def _revisar_antes_de_enviar(config) -> str | None:
    """Devuelve el motivo por el que no tiene caso intentar, o None."""
    if config.proveedor_correo == "consola":
        return (
            "PROVEEDOR_CORREO está en 'consola': el sistema imprime los correos\n"
            "en pantalla y NO manda nada, aunque reporte el envío como exitoso.\n"
            "Es justo lo que hace que parezca que se enviaron y no lleguen.\n\n"
            "Pon PROVEEDOR_CORREO=smtp o PROVEEDOR_CORREO=apps_script.\n"
            "El paso a paso está en CONECTAR_CORREO.md."
        )

    if config.proveedor_correo == "smtp" and not config.smtp_host:
        return "Falta SMTP_HOST en el .env."

    if config.proveedor_correo == "apps_script" and not config.apps_script_url:
        return (
            "Falta APPS_SCRIPT_URL en el .env.\n"
            "Cómo publicar el script está en CONECTAR_CORREO.md."
        )

    return None


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    destino = sys.argv[1].strip()
    config = obtener_config()

    _mostrar_configuracion(config, destino)

    problema = _revisar_antes_de_enviar(config)
    if problema:
        print(problema)
        return 1

    if (config.proveedor_correo == "smtp"
            and config.correo_remitente.endswith("@gmail.com")
            and config.smtp_usuario != config.correo_remitente):
        print(
            "AVISO: con Gmail, CORREO_REMITENTE debe ser la misma cuenta que\n"
            "SMTP_USUARIO. Si no, Google reescribe el remitente.\n"
        )

    try:
        adaptador = obtener_adaptador(Canal.CORREO)
    except RuntimeError as exc:
        print(exc)
        return 1

    # El enlace va DIRECTO a la consulta pública. En un recordatorio real pasa
    # antes por /r/{id}/{firma} para registrar el clic, pero aquí no hay
    # ningún recordatorio que registrar.
    enlace = f"{config.url_consulta}?placa=YUN047A"

    # Se manda un aviso real, no un "hola mundo": así se ve cómo le llega al
    # cliente, con su formato y su botón.
    _, ventana = ventanas_del_anio(7, date.today().year)
    contenido = construir(
        "aviso_2", Canal.CORREO,
        nombre="Prueba del sistema", placa="YUN-047-A",
        ventana=ventana, dias_restantes=ventana.dias_restantes(date.today()),
        enlace=enlace,
    )

    print("Enviando…")
    resultado = adaptador.enviar(Mensaje(
        destino=destino,
        asunto=f"[PRUEBA] {contenido.asunto}",
        cuerpo=contenido.cuerpo,
        clave_plantilla="aviso_2",
        enlace=enlace,
        parrafos=contenido.parrafos,
        pie=contenido.pie,
    ))

    if resultado.exito:
        print(f"\nEnviado. Revisa la bandeja de {destino}")
        print("Si no aparece en unos minutos, mira también la carpeta de spam.")
        print(f"\nEl botón del correo lleva a:\n  {enlace}")
        return 0

    print(f"\nFalló: {resultado.error}")

    if resultado.codigo == "auth":
        print(
            "\nCon Gmail hay que usar una CONTRASEÑA DE APLICACIÓN, no la\n"
            "contraseña normal de la cuenta. Se genera en:\n"
            "  https://myaccount.google.com/apppasswords\n"
            "Requiere tener activada la verificación en dos pasos."
        )
    elif config.proveedor_correo == "apps_script":
        print(
            "\nLo que más falla al conectar Apps Script, en orden:\n"
            "  1. Falta ejecutar 'autorizarYProbar' una vez desde el editor.\n"
            "  2. La implementación no quedó como 'Cualquier persona'.\n"
            "  3. Se cambió el script y no se publicó una versión nueva:\n"
            "     guardar no basta, hay que crear otra implementación.\n"
            "  4. La URL es la de /dev en lugar de la de /exec.\n"
            "\nTodo viene con capturas en CONECTAR_CORREO.md."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
