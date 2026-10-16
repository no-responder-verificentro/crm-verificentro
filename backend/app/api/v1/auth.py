"""Autenticación."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencias import Sesion, Usuario
from app.esquemas.empleado import Credenciales, EmpleadoPublico, Token
from app.modelos.empleado import Empleado
from app.seguridad import (
    crear_token,
    hashear_contrasena,
    verificar_contrasena,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Hash de descarte para gastar el mismo tiempo cuando el correo no existe.
# Sin esto, un atacante mide el tiempo de respuesta y descubre qué correos
# están registrados.
_HASH_SEÑUELO = hashear_contrasena("contrasena-que-nadie-usa")


@router.post("/login", response_model=Token)
def login(datos: Credenciales, sesion: Sesion) -> Token:
    empleado = (
        sesion.query(Empleado).filter(Empleado.correo == datos.correo).one_or_none()
    )

    if empleado is None:
        verificar_contrasena(datos.contrasena, _HASH_SEÑUELO)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
        )

    if not verificar_contrasena(datos.contrasena, empleado.hash_contrasena):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
        )

    if not empleado.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta está dada de baja.",
        )

    empleado.ultimo_acceso = datetime.now(UTC).replace(tzinfo=None)
    sesion.commit()

    return Token(
        access_token=crear_token(empleado.id, empleado.perfil.value),
        perfil=empleado.perfil,
        nombre=empleado.nombre,
    )


@router.post("/token", response_model=Token, include_in_schema=False)
def token_formulario(
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()], sesion: Sesion
) -> Token:
    """Mismo login, pero recibiendo formulario en vez de JSON.

    Existe solo para que el botón «Authorize» de /docs funcione: Swagger manda
    `username` y `password` como formulario, no como JSON. La aplicación de
    React usa /login.
    """
    return login(
        Credenciales(correo=formulario.username, contrasena=formulario.password),
        sesion,
    )


@router.get("/yo", response_model=EmpleadoPublico)
def sesion_actual(usuario: Usuario) -> Empleado:
    """El frontend lo llama al cargar para saber qué menú pintar."""
    return usuario
