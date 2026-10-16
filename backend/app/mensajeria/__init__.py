"""Elige el adaptador según la configuración.

    PROVEEDOR_WHATSAPP=consola   -> imprime en pantalla
    PROVEEDOR_WHATSAPP=meta      -> envía de verdad (cuando esté el trámite)

    PROVEEDOR_CORREO=consola     -> imprime en pantalla, NO manda nada
    PROVEEDOR_CORREO=smtp        -> servidor de correo clásico
    PROVEEDOR_CORREO=apps_script -> app web de Google Apps Script
    PROVEEDOR_CORREO=mailjet     -> API de Mailjet (NO su SMTP: ver abajo)

El modo consola reporta el envío como exitoso. Es a propósito —permite
probar el flujo completo sin gastar mensajes— pero es justo por eso el
primer lugar donde mirar cuando el sistema dice "enviado" y no llega nada.
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

    if config.proveedor_correo == "mailjet":
        from app.mensajeria.mailjet import AdaptadorMailjet

        return AdaptadorMailjet(
            config.mailjet_api_key, config.mailjet_api_secret,
            config.correo_remitente, config.nombre_remitente,
        )

    if config.proveedor_correo == "apps_script":
        from app.mensajeria.apps_script import AdaptadorAppsScript

        return AdaptadorAppsScript(
            config.apps_script_url, config.apps_script_token,
            config.correo_remitente, config.nombre_remitente,
        )

    from app.mensajeria.correo import AdaptadorCorreo

    return AdaptadorCorreo(
        config.smtp_host, config.smtp_puerto, config.smtp_usuario,
        config.smtp_contrasena, config.correo_remitente, config.nombre_remitente,
    )
