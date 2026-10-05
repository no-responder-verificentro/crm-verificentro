"""Dependencias compartidas de FastAPI.

Aquí vive el control de acceso. La idea es que ningún endpoint tenga que
escribir `if usuario.perfil == ...`: se cuelga la dependencia del router y
el permiso queda documentado en la firma, visible también en /docs.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.modelos.empleado import Empleado, Perfil
from app.seguridad import TokenInvalido, leer_token

# tokenUrl apunta a /token, no a /login: es el que acepta formulario, que
# es lo que manda el botón «Authorize» de /docs.
esquema_oauth = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

Sesion = Annotated[Session, Depends(obtener_sesion)]

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o sesión expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)


def usuario_actual(
    sesion: Sesion,
    token: Annotated[str, Depends(esquema_oauth)],
) -> Empleado:
    """Resuelve el empleado dueño del token."""
    try:
        carga = leer_token(token)
    except TokenInvalido:
        raise CREDENCIALES_INVALIDAS from None

    empleado = sesion.get(Empleado, int(carga.get("sub", 0)))
    if empleado is None:
        raise CREDENCIALES_INVALIDAS

    # Se revisa contra la base, no contra el token: si a alguien lo dan de
    # baja a media jornada, su token deja de servir de inmediato en lugar
    # de seguir vivo hasta que expire.
    if not empleado.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta está dada de baja.",
        )
    return empleado


Usuario = Annotated[Empleado, Depends(usuario_actual)]


def requiere_perfil(*permitidos: Perfil):
    """Fábrica de dependencias: restringe un endpoint a ciertos perfiles.

        @router.post("/", dependencies=[Depends(requiere_perfil(Perfil.ADMINISTRADOR))])

    El administrador pasa siempre, no hace falta listarlo en cada llamada.
    """

    def verificar(usuario: Usuario) -> Empleado:
        if usuario.perfil is Perfil.ADMINISTRADOR:
            return usuario
        if usuario.perfil not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu perfil no tiene permiso para esta operación.",
            )
        return usuario

    return verificar


# Atajos con nombre, para que los routers se lean solos.
solo_admin = requiere_perfil()
captura = requiere_perfil(Perfil.TECNICO)              # + administrador
consulta = requiere_perfil(Perfil.TECNICO, Perfil.ATENCION)
chatbot = requiere_perfil(Perfil.ATENCION)
