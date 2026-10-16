"""Webhook de WhatsApp.

Meta manda aquí dos cosas distintas:

1. **Acuses** de los mensajes que nosotros enviamos: enviado, entregado, leído
   o fallido. Se vinculan por el `wamid` que guardamos al enviar.
2. **Mensajes entrantes** de los clientes. Abren la ventana de 24 horas y son
   la puerta del chatbot.

Dos cosas que hay que respetar o el webhook se rompe en producción:

- Meta reintenta si no respondemos **200 en pocos segundos**. Por eso aquí solo
  se registra y se responde; nada de trabajo pesado.
- Meta **repite eventos**. El mismo acuse puede llegar dos veces. Como
  `registrar_entrega` solo deja avanzar el estado, repetirlo no hace daño.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sqlalchemy import select

from app.config import obtener_config
from app.dependencias import Sesion
from app.modelos.cliente import Cliente, EstadoContacto
from app.modelos.recordatorio import EstadoEntrega, Recordatorio
from app.servicios import recordatorios as servicio

router = APIRouter(prefix="/webhooks/whatsapp", tags=["Webhooks"],
                   include_in_schema=False)

#: Cómo se traduce cada estado de Meta al nuestro.
ESTADOS = {
    "sent": EstadoEntrega.ENVIADO,
    "delivered": EstadoEntrega.ENTREGADO,
    "read": EstadoEntrega.LEIDO,
    "failed": EstadoEntrega.FALLIDO,
}

#: Lo que el cliente puede escribir para dejar de recibir avisos. Se compara
#: en minúsculas y sin acentos aproximados.
PALABRAS_DE_BAJA = {"baja", "stop", "no", "cancelar", "dar de baja",
                    "darme de baja", "no quiero", "ya no"}


def _firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    """Comprueba que el webhook venga de verdad de Meta.

    Sin esto, cualquiera que conozca la URL podría mandar acuses falsos y
    ensuciar la bitácora. Si no hay secreto configurado —desarrollo— se deja
    pasar, pero en producción el secreto es obligatorio.
    """
    config = obtener_config()
    if not config.whatsapp_app_secret:
        return not config.es_produccion
    if not firma or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(
        config.whatsapp_app_secret.encode(), cuerpo, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperada, firma.removeprefix("sha256="))


@router.get("")
def verificar(request: Request) -> Response:
    """Meta llama aquí UNA vez, al dar de alta el webhook.

    Manda un reto y espera que se lo devolvamos tal cual, junto con el token
    que nosotros configuramos de los dos lados.
    """
    parametros = request.query_params
    config = obtener_config()

    if (parametros.get("hub.mode") == "subscribe"
            and parametros.get("hub.verify_token") == config.whatsapp_verify_token
            and config.whatsapp_verify_token):
        return Response(content=parametros.get("hub.challenge", ""),
                        media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Token de verificación incorrecto.")


@router.post("")
async def recibir(
    request: Request,
    sesion: Sesion,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict:
    cuerpo = await request.body()
    if not _firma_valida(cuerpo, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Firma inválida.")

    datos = await request.json()
    acuses = entrantes = 0

    for entrada in datos.get("entry", []):
        for cambio in entrada.get("changes", []):
            valor = cambio.get("value", {})
            for acuse in valor.get("statuses", []):
                acuses += _aplicar_acuse(sesion, acuse)
            for mensaje in valor.get("messages", []):
                entrantes += _procesar_entrante(sesion, mensaje)

    # Siempre 200, aunque algo no se haya podido procesar: si devolvemos error
    # Meta reintenta el lote completo y reprocesa lo que ya estaba bien.
    return {"acuses": acuses, "entrantes": entrantes}


def _aplicar_acuse(sesion, acuse: dict) -> int:
    wamid = acuse.get("id")
    nuevo = ESTADOS.get(acuse.get("status"))
    if not wamid or nuevo is None:
        return 0

    recordatorio = sesion.scalar(
        select(Recordatorio).where(Recordatorio.id_externo == wamid)
    )
    if recordatorio is None:
        return 0   # acuse de un mensaje que no salió de aquí

    momento = None
    if acuse.get("timestamp"):
        try:
            momento = datetime.fromtimestamp(int(acuse["timestamp"]), UTC).replace(
                tzinfo=None
            )
        except (TypeError, ValueError):
            momento = None

    errores = acuse.get("errors") or []
    codigo = str(errores[0].get("code")) if errores else None
    if errores and not recordatorio.motivo_error:
        recordatorio.motivo_error = str(
            errores[0].get("title") or errores[0].get("message") or ""
        )[:255]

    servicio.registrar_entrega(sesion, recordatorio, nuevo, momento, codigo)
    return 1


def _procesar_entrante(sesion, mensaje: dict) -> int:
    """Un cliente nos escribió.

    Por ahora solo se atiende la baja, que es lo que no puede esperar: si
    alguien pide dejar de recibir avisos y seguimos mandándolos, reporta como
    spam y se cae la entregabilidad de todos. El resto de las respuestas las
    dará el chatbot.
    """
    if mensaje.get("type") != "text":
        return 0

    texto = (mensaje.get("text", {}).get("body") or "").strip().lower()
    if texto not in PALABRAS_DE_BAJA:
        return 0

    numero = "+" + str(mensaje.get("from", "")).lstrip("+")
    cliente = sesion.scalar(
        select(Cliente).where(Cliente.telefono_e164 == numero)
    )
    if cliente is None:
        return 0

    cliente.estado_contacto = EstadoContacto.BAJA
    cliente.consent_whatsapp = False
    sesion.commit()
    return 1
