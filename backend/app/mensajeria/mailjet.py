"""Envío de correo por la API de Mailjet (Send API v3.1).

Por qué por API y no por SMTP, que es como estaba:

Mailjet acepta el mensaje por SMTP y contesta `250 OK` en el acto. Pero
*después* le pasa su propio filtro antispam, y si decide que el servidor del
destinatario lo marcaría, lo descarta sin enviarlo —lo que en su panel sale
como **spam pre-blocked**—. Para nosotros ya era tarde: el `250` se había
reportado como envío exitoso y el recordatorio quedaba en «Enviado». Correo
que nunca salió, acuse que decía que sí.

Con la Send API, el resultado de cada mensaje viene en la respuesta
(`Status: success` o `error` con su `ErrorMessage`), así que un bloqueo deja
de ser invisible. Y para lo que Mailjet decide más tarde está el webhook de
`app/webhooks/mailjet.py`, que trae los eventos `blocked`, `spam` y `bounce`.

Documentación:
https://dev.mailjet.com/docs/email-api/send-api-v31/send-basic-email
https://documentation.mailjet.com/hc/en-us/articles/360048398994
"""

from __future__ import annotations

import httpx

from app.mensajeria.base import Adaptador, Mensaje, Resultado
from app.mensajeria.correo import cuerpo_html

URL = "https://api.mailjet.com/v3.1/send"
TIEMPO_ESPERA = 30

#: Errores de Mailjet que no son culpa del destinatario. Se marcan como
#: rebote suave —que queda fuera de ENTREGA_FALLIDA— para que un problema de
#: nuestra cuenta no termine marcando al cliente como no localizable.
#: https://dev.mailjet.com/docs/email-api/send-api-v31/send-api-errors
PREFIJOS_PASAJEROS = ("mj-0002", "mj-0004", "mj-0006", "send-0003")


class MailjetNoConfigurado(RuntimeError):
    pass


class AdaptadorMailjet(Adaptador):
    nombre = "correo"

    def __init__(self, api_key: str, api_secret: str, remitente: str,
                 nombre_remitente: str = "Verificentro"):
        if not api_key or not api_secret:
            raise MailjetNoConfigurado(
                "Faltan MAILJET_API_KEY o MAILJET_API_SECRET en el .env. "
                "Se sacan de Mailjet → Account settings → API Key Management. "
                "Ver CONECTAR_CORREO.md."
            )
        if not remitente:
            raise MailjetNoConfigurado(
                "Falta CORREO_REMITENTE. Mailjet solo manda desde una "
                "dirección que esté validada en la cuenta."
            )
        self.api_key = api_key
        self.api_secret = api_secret
        self.remitente = remitente
        self.nombre_remitente = nombre_remitente

    def _cuerpo(self, mensaje: Mensaje) -> dict:
        return {
            "Messages": [
                {
                    "From": {"Email": self.remitente,
                             "Name": self.nombre_remitente},
                    "To": [{"Email": mensaje.destino}],
                    "Subject": mensaje.asunto or "Recordatorio de verificación",
                    # Las dos versiones en el mismo mensaje. Un correo
                    # solo-HTML puntúa peor en los filtros antispam.
                    "TextPart": mensaje.cuerpo,
                    "HTMLPart": cuerpo_html(mensaje),
                    "Headers": {
                        "List-Unsubscribe": f"<mailto:{self.remitente}?subject=BAJA>",
                    },
                }
            ]
        }

    def enviar(self, mensaje: Mensaje) -> Resultado:
        try:
            respuesta = httpx.post(
                URL,
                json=self._cuerpo(mensaje),
                auth=(self.api_key, self.api_secret),
                timeout=TIEMPO_ESPERA,
            )
        except httpx.HTTPError as exc:
            return Resultado(exito=False, codigo="rebote_suave",
                             error=f"No se pudo contactar a Mailjet: {exc}")

        if respuesta.status_code == 401:
            return Resultado(
                exito=False, codigo="fallido",
                error="Mailjet rechazó las credenciales. Revisa "
                      "MAILJET_API_KEY y MAILJET_API_SECRET.",
            )

        try:
            datos = respuesta.json()
        except ValueError:
            return Resultado(
                exito=False, codigo="rebote_suave",
                error=f"Mailjet respondió {respuesta.status_code} sin JSON.",
            )

        mensajes = datos.get("Messages") or []
        if not mensajes:
            return Resultado(
                exito=False, codigo="fallido",
                error=_error_global(datos) or "Mailjet no devolvió resultado.",
            )

        primero = mensajes[0]

        if primero.get("Status") == "success":
            destinos = primero.get("To") or [{}]
            # El MessageID es con lo que después llegan los eventos del
            # webhook; sin él no se podrían vincular.
            identificador = destinos[0].get("MessageID")
            return Resultado(
                exito=True,
                id_externo=str(identificador) if identificador else None,
            )

        return _a_resultado(primero.get("Errors") or [])


def _a_resultado(errores: list) -> Resultado:
    if not errores:
        return Resultado(exito=False, codigo="fallido",
                         error="Mailjet rechazó el mensaje sin decir por qué.")

    primero = errores[0]
    codigo_mj = str(primero.get("ErrorCode") or "")
    detalle = str(primero.get("ErrorMessage") or "Error de Mailjet.")

    pasajero = codigo_mj.lower().startswith(PREFIJOS_PASAJEROS)
    return Resultado(
        exito=False,
        codigo="rebote_suave" if pasajero else "fallido",
        error=f"[{codigo_mj}] {detalle}" if codigo_mj else detalle,
    )


def _error_global(datos: dict) -> str | None:
    """Mailjet también contesta errores fuera del arreglo de mensajes."""
    if datos.get("ErrorMessage"):
        return str(datos["ErrorMessage"])
    mensajes = datos.get("Messages")
    if isinstance(mensajes, dict) and mensajes.get("Errors"):
        return str(mensajes["Errors"][0].get("ErrorMessage"))
    return None
