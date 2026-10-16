"""Envío de correo a través de una app web de Google Apps Script.

El script vive en la cuenta de Google del verificentro y manda el correo con
`MailApp`. Aquí solo se le hace una petición HTTPS con el contenido ya armado.

Por qué existiendo ya el SMTP:

- No hay que guardar la contraseña de aplicación de Gmail en el servidor. Lo
  único que viaja es un token que nosotros inventamos y que solo sirve para
  hablarle a ese script.
- Funciona donde el puerto 587 está cerrado, que es común en los planes
  gratuitos de hosting.
- El correo sale con la identidad de la cuenta de Google, igual que si lo
  mandaras tú a mano desde Gmail.

Lo que NO resuelve: la cuota. Una cuenta de Gmail normal permite 100
destinatarios al día; una de Google Workspace, 1,500. El SMTP de Gmail da
unos 500. Para un padrón grande hay que pasar a un proveedor de correo
transaccional con dominio propio.

Documentación de las cuotas:
https://developers.google.com/apps-script/guides/services/quotas
"""

from __future__ import annotations

import uuid

import httpx

from app.mensajeria.base import Adaptador, Mensaje, Resultado
from app.mensajeria.correo import cuerpo_html

#: Apps Script tarda en despertar si el script llevaba rato sin usarse, y
#: cada envío es una ejecución completa del lado de Google.
TIEMPO_ESPERA = 60

#: Errores que no son culpa del destinatario. Se marcan como rebote suave
#: —no como fallo— para que el contacto no se queme por algo pasajero.
PASAJEROS = ("cuota", "limite", "quota", "limit", "timeout", "temporal")


class AppsScriptNoConfigurado(RuntimeError):
    pass


class AdaptadorAppsScript(Adaptador):
    nombre = "correo"

    def __init__(self, url: str, token: str, remitente: str,
                 nombre_remitente: str = "Verificentro"):
        if not url:
            raise AppsScriptNoConfigurado(
                "Falta APPS_SCRIPT_URL en el .env. Lee CONECTAR_CORREO.md "
                "para publicar el script, o usa PROVEEDOR_CORREO=consola "
                "mientras tanto."
            )
        if not url.endswith("/exec"):
            raise AppsScriptNoConfigurado(
                f"APPS_SCRIPT_URL debe terminar en /exec y termina en "
                f"'{url.rsplit('/', 1)[-1]}'. La que acaba en /dev es la de "
                "pruebas y solo responde si tú tienes la sesión abierta."
            )
        if not token:
            raise AppsScriptNoConfigurado(
                "Falta APPS_SCRIPT_TOKEN. Sin él, cualquiera que descubra la "
                "dirección del script podría mandar correo a tu nombre."
            )
        self.url = url
        self.token = token
        self.remitente = remitente
        self.nombre_remitente = nombre_remitente

    def _cuerpo(self, mensaje: Mensaje) -> dict:
        return {
            "token": self.token,
            "para": mensaje.destino,
            "asunto": mensaje.asunto or "Recordatorio de verificación",
            "texto": mensaje.cuerpo,
            "html": cuerpo_html(mensaje),
            "nombre_remitente": self.nombre_remitente,
            "responder_a": self.remitente,
        }

    def enviar(self, mensaje: Mensaje) -> Resultado:
        try:
            # follow_redirects es obligatorio: una app web de Apps Script
            # contesta con un 302 hacia script.googleusercontent.com y la
            # respuesta de verdad está del otro lado.
            respuesta = httpx.post(
                self.url, json=self._cuerpo(mensaje),
                timeout=TIEMPO_ESPERA, follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            return Resultado(
                exito=False, codigo="rebote_suave",
                error=f"No se pudo contactar al script: {exc}",
            )

        if respuesta.status_code != 200:
            # Un 401 o un 403 casi siempre es que el script no se publicó
            # como "cualquier persona".
            return Resultado(
                exito=False, codigo="fallido",
                error=_explicar_http(respuesta.status_code),
            )

        try:
            datos = respuesta.json()
        except ValueError:
            # Google devuelve una página HTML cuando el script truena antes de
            # llegar a nuestro código, o cuando falta autorizarlo.
            return Resultado(
                exito=False, codigo="fallido",
                error="El script no respondió en JSON. Lo más común es que le "
                      "falte la autorización: ábrelo y ejecútalo una vez a mano.",
            )

        if datos.get("ok"):
            return Resultado(
                exito=True,
                id_externo=datos.get("id") or uuid.uuid4().hex,
            )

        detalle = str(datos.get("error") or "Error desconocido del script.")
        pasajero = any(p in detalle.lower() for p in PASAJEROS)
        return Resultado(
            exito=False,
            codigo="rebote_suave" if pasajero else "fallido",
            error=detalle,
        )


def _explicar_http(codigo: int) -> str:
    if codigo in (401, 403):
        return (
            f"Google respondió {codigo}. El script no está publicado para "
            "'Cualquier persona': vuelve a implementarlo con ese acceso."
        )
    if codigo == 404:
        return (
            "Google respondió 404. La dirección del script no existe; "
            "revisa APPS_SCRIPT_URL."
        )
    return f"Google respondió {codigo}."
