"""Envío de correo por SMTP.

A diferencia de WhatsApp, esto no depende de ninguna aprobación: en cuanto
haya credenciales funciona. Por eso conviene conectarlo primero.

El correo sale en dos versiones dentro del mismo mensaje: texto plano y HTML.
Los clientes de correo eligen la que pueden mostrar, y tener la de texto
mejora la entregabilidad —un correo solo-HTML tiene más probabilidad de caer
en spam.
"""

from __future__ import annotations

import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.mensajeria.base import Adaptador, Mensaje, Resultado

PUERTO_SSL = 465


class CorreoNoConfigurado(RuntimeError):
    pass


def _a_html(mensaje: Mensaje) -> str:
    """Arma la versión HTML.

    El enlace NO va como texto: aquí se convierte en botón. Si apareciera de
    las dos formas, el correo se ve repetido.
    """
    piezas = mensaje.parrafos or tuple(
        p for p in mensaje.cuerpo.split("\n\n") if p.strip()
    )
    enlace = mensaje.enlace
    parrafos = "".join(
        f'<p style="margin:0 0 14px;line-height:1.55">{p}</p>'
        for p in piezas
        if not (enlace and enlace in p)
    )
    boton = ""
    if enlace:
        boton = (
            f'<p style="margin:22px 0"><a href="{enlace}" '
            'style="background:#9e1b45;color:#fff;text-decoration:none;'
            'padding:12px 22px;border-radius:8px;font-weight:bold;'
            'display:inline-block">Consultar mi periodo</a></p>'
        )
    pie = "".join(
        f'<p style="margin:0 0 6px;font-size:12px;color:#777;line-height:1.5">'
        f"{linea}</p>"
        for linea in mensaje.pie
    ) or (
        '<p style="margin:0;font-size:12px;color:#777;line-height:1.5">'
        "Av. Ruíz Cortines No. 256, Col. Centro · Lunes a sábado de 9:00 a 16:00"
        "</p>"
    )

    return (
        '<!doctype html><html lang="es-MX"><body style="margin:0;padding:24px;'
        'background:#f5f3f0;font-family:Arial,Helvetica,sans-serif;color:#29292b">'
        '<div style="max-width:560px;margin:0 auto;background:#fff;'
        'border-radius:16px;padding:32px">'
        '<p style="margin:0 0 20px;font-size:20px;font-weight:bold;color:#9e1b45">'
        "VERIFICENTRO</p>"
        f"{parrafos}{boton}"
        '<hr style="border:none;border-top:1px solid #e0ddd9;margin:24px 0">'
        f"{pie}</div></body></html>"
    )


class AdaptadorCorreo(Adaptador):
    nombre = "correo"

    def __init__(self, host: str, puerto: int, usuario: str,
                 contrasena: str, remitente: str, nombre_remitente: str = "Verificentro"):
        if not host:
            raise CorreoNoConfigurado(
                "Falta SMTP_HOST en el .env. Mientras tanto usa "
                "PROVEEDOR_CORREO=consola."
            )
        self.host, self.puerto = host, puerto
        self.usuario, self.contrasena = usuario, contrasena
        self.remitente = remitente
        self.nombre_remitente = nombre_remitente

    def _conectar(self):
        contexto = ssl.create_default_context()
        if self.puerto == PUERTO_SSL:
            return smtplib.SMTP_SSL(self.host, self.puerto, context=contexto,
                                    timeout=20)
        servidor = smtplib.SMTP(self.host, self.puerto, timeout=20)
        servidor.starttls(context=contexto)
        return servidor

    def enviar(self, mensaje: Mensaje) -> Resultado:
        correo = EmailMessage()
        correo["From"] = formataddr((self.nombre_remitente, self.remitente))
        correo["To"] = mensaje.destino
        correo["Subject"] = mensaje.asunto or "Recordatorio de verificación"
        correo["Message-ID"] = make_msgid(domain=self.remitente.split("@")[-1])
        # Deja que el cliente de correo ofrezca darse de baja en su propia
        # interfaz. Mejora la entregabilidad y evita reportes de spam.
        correo["List-Unsubscribe"] = f"<mailto:{self.remitente}?subject=BAJA>"

        correo.set_content(mensaje.cuerpo)
        correo.add_alternative(_a_html(mensaje), subtype="html")

        try:
            with self._conectar() as servidor:
                if self.usuario:
                    servidor.login(self.usuario, self.contrasena)
                servidor.send_message(correo)
        except smtplib.SMTPRecipientsRefused:
            return Resultado(exito=False, codigo="rebote_duro",
                             error="El servidor rechazó la dirección.")
        except smtplib.SMTPAuthenticationError:
            return Resultado(exito=False, codigo="auth",
                             error="Credenciales SMTP incorrectas.")
        except (smtplib.SMTPException, OSError) as exc:
            return Resultado(exito=False, codigo="smtp",
                             error=f"{type(exc).__name__}: {exc}")

        return Resultado(exito=True,
                         id_externo=correo["Message-ID"] or uuid.uuid4().hex)
