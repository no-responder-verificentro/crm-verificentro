"""Empleados. Solo administradores."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencias import Sesion, Usuario, solo_admin
from app.esquemas.empleado import (
    EmpleadoEditado,
    EmpleadoNuevo,
    EmpleadoPublico,
)
from app.modelos.empleado import Empleado
from app.seguridad import hashear_contrasena

router = APIRouter(
    prefix="/empleados",
    tags=["Empleados"],
    dependencies=[Depends(solo_admin)],
)


@router.get("", response_model=list[EmpleadoPublico])
def listar(sesion: Sesion, incluir_bajas: bool = False) -> list[Empleado]:
    consulta = sesion.query(Empleado)
    if not incluir_bajas:
        consulta = consulta.filter(Empleado.activo.is_(True))
    return consulta.order_by(Empleado.nombre).all()


@router.post("", response_model=EmpleadoPublico, status_code=status.HTTP_201_CREATED)
def registrar(datos: EmpleadoNuevo, sesion: Sesion) -> Empleado:
    existente = (
        sesion.query(Empleado).filter(Empleado.correo == datos.correo).one_or_none()
    )
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una cuenta con ese correo.",
        )

    empleado = Empleado(
        nombre=datos.nombre,
        correo=datos.correo,
        hash_contrasena=hashear_contrasena(datos.contrasena),
        perfil=datos.perfil,
    )
    sesion.add(empleado)
    sesion.commit()
    sesion.refresh(empleado)
    return empleado


@router.patch("/{empleado_id}", response_model=EmpleadoPublico)
def editar(
    empleado_id: int,
    datos: EmpleadoEditado,
    sesion: Sesion,
    usuario: Usuario,
) -> Empleado:
    empleado = sesion.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    cambios = datos.model_dump(exclude_unset=True)

    # Nadie puede quitarse a sí mismo el acceso ni degradar su propio perfil:
    # es la forma más común de quedarse sin ningún administrador.
    if empleado.id == usuario.id:
        if cambios.get("activo") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes darte de baja a ti mismo.",
            )
        if "perfil" in cambios and cambios["perfil"] != empleado.perfil:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes cambiar tu propio perfil.",
            )

    for campo, valor in cambios.items():
        setattr(empleado, campo, valor)

    sesion.commit()
    sesion.refresh(empleado)
    return empleado


@router.delete("/{empleado_id}", response_model=EmpleadoPublico)
def dar_de_baja(empleado_id: int, sesion: Sesion, usuario: Usuario) -> Empleado:
    """Desactiva la cuenta. NO borra: el historial de lo que capturó se queda."""
    if empleado_id == usuario.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes darte de baja a ti mismo.",
        )

    empleado = sesion.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    empleado.activo = False
    sesion.commit()
    sesion.refresh(empleado)
    return empleado
