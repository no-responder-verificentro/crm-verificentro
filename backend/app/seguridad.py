"""Contraseñas y tokens.

Aislado a propósito: si algún día se cambia bcrypt por argon2, o JWT por
sesiones en Redis, solo se toca este archivo.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import obtener_config

config = obtener_config()

# bcrypt trunca en 72 bytes. Si alguien manda una contraseña más larga,
# los caracteres extra se ignoran en silencio y dos contraseñas distintas
# podrían coincidir. Mejor rechazarla desde el esquema de entrada.
LIMITE_BCRYPT = 72


class TokenInvalido(Exception):
    """El token está vencido, mal firmado o malformado."""


def hashear_contrasena(contrasena: str) -> str:
    if len(contrasena.encode("utf-8")) > LIMITE_BCRYPT:
        raise ValueError("La contraseña excede el límite de 72 bytes.")
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode()


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode())
    except ValueError:
        # Hash corrupto o con formato desconocido: se trata como fallo.
        return False


def crear_token(empleado_id: int, perfil: str) -> str:
    ahora = datetime.now(UTC)
    carga = {
        "sub": str(empleado_id),
        "perfil": perfil,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=config.jwt_minutos_vigencia),
    }
    return jwt.encode(carga, config.jwt_secreto, algorithm=config.jwt_algoritmo)


def leer_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, config.jwt_secreto, algorithms=[config.jwt_algoritmo]
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalido(str(exc)) from exc
