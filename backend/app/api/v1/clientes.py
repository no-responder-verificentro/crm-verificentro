"""Clientes y sus vehículos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencias import Sesion, Usuario, captura, consulta, solo_admin
from app.esquemas.cliente import (
    CambioDePlaca,
    ClienteConVehiculos,
    ClienteEditado,
    ClienteNuevo,
    ClientePublico,
    VehiculoDetalle,
    VehiculoEditado,
    VehiculoNuevo,
    VehiculoPublico,
)
from app.modelos.cliente import Cliente
from app.modelos.vehiculo import Vehiculo
from app.servicios import clientes as servicio
from app.servicios.clientes import ReglaDeNegocio

router = APIRouter(prefix="/clientes", tags=["Clientes"])


def _obtener(sesion, cliente_id: int) -> Cliente:
    cliente = sesion.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado."
        )
    return cliente


def _con_vehiculos(cliente: Cliente) -> ClienteConVehiculos:
    salida = ClienteConVehiculos.model_validate(cliente)
    salida.vehiculos = [
        servicio.describir_vehiculo(v) for v in cliente.vehiculos if v.activo
    ]
    return salida


# ------------------------------------------------------------------ listar --

@router.get(
    "",
    response_model=list[ClienteConVehiculos],
    dependencies=[Depends(consulta)],
)
def listar(
    sesion: Sesion,
    buscar: str | None = Query(
        default=None,
        description="Nombre, teléfono, correo, placa o número de serie.",
    ),
    limite: int = Query(default=50, ge=1, le=200),
    desplazamiento: int = Query(default=0, ge=0),
) -> list[ClienteConVehiculos]:
    encontrados = servicio.buscar_clientes(sesion, buscar, limite, desplazamiento)
    return [_con_vehiculos(c) for c in encontrados]


@router.get(
    "/{cliente_id}",
    response_model=ClienteConVehiculos,
    dependencies=[Depends(consulta)],
)
def ficha(cliente_id: int, sesion: Sesion) -> ClienteConVehiculos:
    return _con_vehiculos(_obtener(sesion, cliente_id))


# -------------------------------------------------------------------- alta --

@router.post(
    "",
    response_model=ClienteConVehiculos,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(captura)],
)
def registrar(datos: ClienteNuevo, sesion: Sesion, usuario: Usuario):
    """Alta de mostrador: cliente y, opcionalmente, su primer vehículo."""
    try:
        cliente = servicio.crear_cliente(sesion, datos, usuario.id)
    except ReglaDeNegocio as exc:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None
    return _con_vehiculos(cliente)


# ---------------------------------------------------------------- edición --

@router.patch(
    "/{cliente_id}",
    response_model=ClientePublico,
    dependencies=[Depends(solo_admin)],
)
def editar(cliente_id: int, datos: ClienteEditado, sesion: Sesion) -> Cliente:
    """Editar datos de contacto está restringido a administradores.

    Es lo que quedó en la matriz de permisos: técnico y atención los ven,
    pero no los modifican.
    """
    cliente = _obtener(sesion, cliente_id)
    cambios = datos.model_dump(exclude_unset=True)

    if "telefono" in cambios:
        cliente.telefono_e164 = cambios.pop("telefono")
    for campo, valor in cambios.items():
        setattr(cliente, campo, valor)

    sesion.commit()
    sesion.refresh(cliente)
    return cliente


@router.post(
    "/{cliente_id}/baja-de-contacto",
    response_model=ClientePublico,
    dependencies=[Depends(captura)],
)
def baja_de_contacto(cliente_id: int, sesion: Sesion) -> Cliente:
    """El cliente pidió no recibir más mensajes.

    Se apagan los consentimientos, no se borran sus datos: se necesitan para
    la bitácora de verificaciones.
    """
    return servicio.dar_de_baja_contacto(sesion, _obtener(sesion, cliente_id))


# ------------------------------------------------------------- vehículos --

@router.post(
    "/{cliente_id}/vehiculos",
    response_model=VehiculoPublico,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(captura)],
)
def agregar_vehiculo(
    cliente_id: int, datos: VehiculoNuevo, sesion: Sesion, usuario: Usuario
) -> VehiculoPublico:
    """Un cliente puede tener varios vehículos, cada uno con su calendario."""
    _obtener(sesion, cliente_id)
    try:
        vehiculo = servicio.crear_vehiculo(sesion, cliente_id, datos, usuario.id)
        sesion.commit()
    except ReglaDeNegocio as exc:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None
    sesion.refresh(vehiculo)
    return servicio.describir_vehiculo(vehiculo)


vehiculos = APIRouter(prefix="/vehiculos", tags=["Vehículos"])


def _obtener_vehiculo(sesion, vehiculo_id: int) -> Vehiculo:
    vehiculo = sesion.get(Vehiculo, vehiculo_id)
    if vehiculo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado."
        )
    return vehiculo


@vehiculos.get(
    "/{vehiculo_id}",
    response_model=VehiculoDetalle,
    dependencies=[Depends(consulta)],
)
def detalle(vehiculo_id: int, sesion: Sesion) -> VehiculoDetalle:
    vehiculo = _obtener_vehiculo(sesion, vehiculo_id)
    base = servicio.describir_vehiculo(vehiculo)
    salida = VehiculoDetalle(**base.model_dump())
    salida.verificaciones = sorted(
        vehiculo.verificaciones, key=lambda v: v.fecha, reverse=True
    )
    return salida


@vehiculos.patch(
    "/{vehiculo_id}",
    response_model=VehiculoPublico,
    dependencies=[Depends(captura)],
)
def editar_vehiculo(
    vehiculo_id: int, datos: VehiculoEditado, sesion: Sesion
) -> VehiculoPublico:
    vehiculo = _obtener_vehiculo(sesion, vehiculo_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(vehiculo, campo, valor)
    sesion.commit()
    sesion.refresh(vehiculo)
    return servicio.describir_vehiculo(vehiculo)


@vehiculos.post(
    "/{vehiculo_id}/cambio-de-placa",
    response_model=VehiculoPublico,
    dependencies=[Depends(captura)],
)
def cambio_de_placa(
    vehiculo_id: int, datos: CambioDePlaca, sesion: Sesion, usuario: Usuario
) -> VehiculoPublico:
    """Reemplazo de placa conservando el historial.

    Puede cambiar el periodo que le toca: en la tarjeta de ejemplo la placa
    anterior terminaba en 5 y la nueva en 7, o sea que pasó de Enero-Febrero
    a Febrero-Marzo.
    """
    vehiculo = _obtener_vehiculo(sesion, vehiculo_id)
    try:
        vehiculo = servicio.cambiar_placa(sesion, vehiculo, datos, usuario.id)
    except ReglaDeNegocio as exc:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None
    return servicio.describir_vehiculo(vehiculo)
