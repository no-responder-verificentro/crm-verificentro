"""Envío por WhatsApp usando la Cloud API de Meta.

LA REGLA QUE GOBIERNA TODO
--------------------------
Cuando nosotros iniciamos la conversación —que es el caso de todos los
recordatorios— Meta **no acepta texto libre**. Solo se puede enviar una
plantilla previamente aprobada, identificada por su nombre, con sus variables
por separado. El cuerpo que arma `plantillas.py` sirve para la bitácora y para
el correo; a Meta va el nombre de la plantilla más los parámetros.

Si el cliente escribe primero se abre una ventana de 24 horas en la que sí se
puede contestar libre. Eso lo usa el chatbot, no este adaptador.
"""

from __future__ import annotations

import httpx

from app.mensajeria.base import Adaptador, Mensaje, Resultado

VERSION_API = "v21.0"
TIEMPO_ESPERA = 20.0

#: Códigos de error de Meta que conviene distinguir, porque cada uno pide una
#: acción distinta de nuestro lado.
#: https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
ERRORES = {
    131026: ("fallido", "El número no tiene WhatsApp o no puede recibir mensajes."),
    131047: ("fallido", "Pasaron más de 24 h; se requiere plantilla."),
    131049: ("fallido", "Meta decidió no entregarlo para cuidar la experiencia "
                        "del usuario."),
    131050: ("baja", "El usuario dejó de aceptar mensajes de este tipo."),
    132000: ("fallido", "El número de parámetros no coincide con la plantilla."),
    132001: ("fallido", "La plantilla no existe o no está aprobada en ese idioma."),
    132015: ("fallido", "La plantilla está pausada por mala calidad."),
    132016: ("fallido", "La plantilla fue deshabilitada por Meta."),
    130429: ("reintentar", "Se alcanzó el límite de envíos por segundo."),
    131056: ("reintentar", "Demasiados mensajes a este número en poco tiempo."),
    80007:  ("reintentar", "Se alcanzó el límite de la cuenta."),
}


class WhatsAppNoConfigurado(RuntimeError):
    pass


def _json_seguro(respuesta) -> dict:
    try:
        return respuesta.json()
    except ValueError:
        return {}


class AdaptadorWhatsApp(Adaptador):
    nombre = "whatsapp"

    def __init__(self, token: str, phone_id: str, idioma: str = "es_MX"):
        if not token or not phone_id:
            raise WhatsAppNoConfigurado(
                "Faltan WHATSAPP_TOKEN o WHATSAPP_PHONE_ID en el .env. "
                "Mientras no esté el trámite con Meta, usa "
                "PROVEEDOR_WHATSAPP=consola."
            )
        self.token = token
        self.phone_id = phone_id
        self.idioma = idioma

    @property
    def url(self) -> str:
        return f"https://graph.facebook.com/{VERSION_API}/{self.phone_id}/messages"

    def _cuerpo(self, mensaje: Mensaje) -> dict:
        """Arma la petición. Meta pide el número SIN el signo de más."""
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": mensaje.destino.lstrip("+"),
            "type": "template",
            "template": {
                "name": mensaje.plantilla_meta,
                "language": {"code": self.idioma},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": p} for p in mensaje.parametros
                        ],
                    }
                ],
            },
        }

    def enviar(self, mensaje: Mensaje) -> Resultado:
        if not mensaje.plantilla_meta:
            # Falla temprano y claro: sin plantilla registrada Meta lo
            # rechazaría igual, pero con un error críptico.
            return Resultado(
                exito=False, codigo="fallido",
                error=f"El aviso '{mensaje.clave_plantilla}' no tiene plantilla "
                      "registrada en Meta. Revisa PLANTILLAS_META.",
            )

        try:
            respuesta = httpx.post(
                self.url,
                json=self._cuerpo(mensaje),
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=TIEMPO_ESPERA,
            )
        except httpx.HTTPError as exc:
            # Sin respuesta: puede ser la red de aquí. Se marca reintentable
            # para no quemar el contacto por una falla pasajera nuestra.
            return Resultado(exito=False, codigo="reintentar",
                             error=f"No se pudo contactar a Meta: {exc}")

        datos = _json_seguro(respuesta)

        if respuesta.status_code == 200:
            enviados = datos.get("messages") or [{}]
            # El wamid es lo que después llega en los acuses del webhook; sin
            # él no se podrían vincular.
            return Resultado(exito=True, id_externo=enviados[0].get("id"))

        error = datos.get("error", {})
        numero = error.get("code")
        codigo, explicacion = ERRORES.get(
            numero, ("fallido", error.get("message", "Error desconocido de Meta."))
        )
        detalle = (error.get("error_data") or {}).get("details")
        return Resultado(
            exito=False, codigo=codigo,
            error=f"[{numero}] {explicacion}" + (f" · {detalle}" if detalle else ""),
        )
