"""Elige el adaptador según la configuración.

    PROVEEDOR_WHATSAPP=consola   -> imprime en pantalla
    PROVEEDOR_WHATSAPP=meta      -> envía de verdad (cuando esté el trámite)
"""

from __future__ import annotations

from app.config import obtener_config
from app.mensajeria.base import Adaptador, Mensaje, Resultado  # noqa: F401
from app.mensajeria.consola import AdaptadorConsola
from app.modelos.recordatorio import Canal


def obtener_adaptador(canal: Canal, silencioso: bool = False) -> Adaptador:
    config = obtener_config()

    if canal is Canal.WHATSAPP:
        if config.proveedor_whatsapp == "consola":
            return AdaptadorConsola("whatsapp", silencioso)
        from app.mensajeria.whatsapp import AdaptadorWhatsApp

        return AdaptadorWhatsApp(
            config.whatsapp_token, config.whatsapp_phone_id,
            config.whatsapp_idioma,
        )

    if config.proveedor_correo == "consola":
        return AdaptadorConsola("correo", silencioso)
    from app.mensajeria.correo import AdaptadorCorreo

    return AdaptadorCorreo(
        config.smtp_host, config.smtp_puerto, config.smtp_usuario,
        config.smtp_contrasena, config.correo_remitente, config.nombre_remitente,
    )
