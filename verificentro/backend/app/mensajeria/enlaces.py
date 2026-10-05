"""Enlaces firmados para medir el clic en los correos.

Por qué el clic y no la apertura: el "abierto" se mide con un pixel invisible,
y desde que Apple precarga las imágenes de todos los correos ese dato miente
en las dos direcciones. El clic sí es voluntario y verificable.

Cada enlace lleva una firma para que nadie pueda marcar como leídos los
recordatorios de otro simplemente cambiando el número en la URL.
"""

from __future__ import annotations

import hashlib
import hmac

from app.config import obtener_config

LARGO_FIRMA = 16


def firmar(recordatorio_id: int) -> str:
    config = obtener_config()
    mensaje = f"clic:{recordatorio_id}".encode()
    llave = config.jwt_secreto.encode()
    return hmac.new(llave, mensaje, hashlib.sha256).hexdigest()[:LARGO_FIRMA]


def verificar(recordatorio_id: int, firma: str) -> bool:
    # compare_digest en lugar de == : compara en tiempo constante, para que
    # nadie pueda adivinar la firma midiendo cuánto tarda la respuesta.
    return hmac.compare_digest(firmar(recordatorio_id), firma or "")


def enlace_de_seguimiento(recordatorio_id: int) -> str:
    config = obtener_config()
    base = config.url_publica.rstrip("/")
    return f"{base}/r/{recordatorio_id}/{firmar(recordatorio_id)}"
