"""Manda un correo de prueba para verificar la configuración SMTP.

    python -m jobs.probar_correo tu.correo@gmail.com

Sirve para separar dos problemas que se confunden: que las credenciales estén
mal, o que el sistema de recordatorios tenga un error. Si esto llega, el SMTP
está bien y cualquier falla posterior es del sistema.
"""

import sys
from datetime import date

from app.config import obtener_config
from app.dominio.calendario import ventanas_del_anio
from app.mensajeria.base import Mensaje
from app.mensajeria.correo import AdaptadorCorreo, CorreoNoConfigurado
from app.mensajeria.plantillas import construir
from app.modelos.recordatorio import Canal


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    destino = sys.argv[1].strip()
    config = obtener_config()

    print("Configuración leída del .env:")
    print(f"  Servidor  : {config.smtp_host}:{config.smtp_puerto}")
    print(f"  Usuario   : {config.smtp_usuario or '(vacío)'}")
    print(f"  Contraseña: {'*' * 8 if config.smtp_contrasena else '(vacía)'}")
    print(f"  Remitente : {config.correo_remitente}")
    print(f"  Destino   : {destino}\n")

    if not config.smtp_host:
        print("Falta SMTP_HOST en el .env.")
        return 1

    if (config.correo_remitente.endswith("@gmail.com")
            and config.smtp_usuario != config.correo_remitente):
        print(
            "AVISO: con Gmail, CORREO_REMITENTE debe ser la misma cuenta que\n"
            "SMTP_USUARIO. Si no, Google reescribe el remitente.\n"
        )

    try:
        adaptador = AdaptadorCorreo(
            config.smtp_host, config.smtp_puerto, config.smtp_usuario,
            config.smtp_contrasena, config.correo_remitente,
            config.nombre_remitente,
        )
    except CorreoNoConfigurado as exc:
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
        print(f"El botón del correo lleva a:\n  {enlace}")
        print(
            "\nPara que ese enlace abra, el frontend tiene que estar corriendo:\n"
            "    cd ..\\frontend\n"
            "    npm run dev"
        )
        return 0

    print(f"\nFalló: {resultado.error}")
    if resultado.codigo == "auth":
        print(
            "\nCon Gmail hay que usar una CONTRASEÑA DE APLICACIÓN, no la\n"
            "contraseña normal de la cuenta. Se genera en:\n"
            "  https://myaccount.google.com/apppasswords\n"
            "Requiere tener activada la verificación en dos pasos."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
