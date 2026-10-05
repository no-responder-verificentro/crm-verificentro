"""Casos de uso de clientes y vehículos.

Los endpoints se quedan delgados: reciben, delegan aquí y devuelven. Así la
misma lógica la puede llamar mañana el chatbot o un script de carga masiva.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.dominio.calendario import estado_de_cumplimiento
from app.dominio.placas import normalizar_niv
from app.esquemas.cliente import (
    CambioDePlaca,
    ClienteNuevo,
    PeriodoResumen,
    VehiculoNuevo,
    VehiculoPublico,
)
from app.modelos.cliente import Cliente, EstadoContacto
from app.modelos.vehiculo import MotivoPlaca, Vehiculo, VehiculoPlaca


class ReglaDeNegocio(Exception):
    """Algo válido en formato pero inaceptable para el negocio."""


def _ahora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalizar_placa_sql(placa: str) -> str:
    return "".join(c for c in placa.upper() if c.isalnum())


# ------------------------------------------------------------------ altas --

def crear_cliente(
    sesion: Session, datos: ClienteNuevo, empleado_id: int
) -> Cliente:
    cliente = Cliente(
        nombre=datos.nombre,
        telefono_e164=datos.telefono,
        correo=datos.correo,
        consent_whatsapp=datos.consentimiento.whatsapp,
        consent_correo=datos.consentimiento.correo,
        consent_origen=datos.consentimiento.origen,
        aviso_privacidad_ver=datos.consentimiento.aviso_privacidad_ver,
        registrado_por=empleado_id,
    )
    if datos.consentimiento.whatsapp or datos.consentimiento.correo:
        cliente.consent_fecha = _ahora()

    sesion.add(cliente)
    sesion.flush()   # necesitamos el id para el vehículo

    if datos.vehiculo is not None:
        crear_vehiculo(sesion, cliente.id, datos.vehiculo, empleado_id)

    sesion.commit()
    sesion.refresh(cliente)
    return cliente


def crear_vehiculo(
    sesion: Session, cliente_id: int, datos: VehiculoNuevo, empleado_id: int
) -> Vehiculo:
    niv = normalizar_niv(datos.niv)

    repetido = sesion.scalar(select(Vehiculo).where(Vehiculo.niv == niv))
    if repetido is not None:
        raise ReglaDeNegocio(
            f"El número de serie {niv} ya está registrado "
            f"(placa {repetido.placa}). Si cambió de placa, usa el cambio "
            "de placa en lugar de dar de alta otro vehículo."
        )

    placa_norm = _normalizar_placa_sql(datos.placa)
    misma_placa = sesion.scalar(
        select(Vehiculo).where(Vehiculo.placa_normalizada == placa_norm)
    )
    if misma_placa is not None:
        raise ReglaDeNegocio(
            f"La placa {datos.placa} ya está asignada a otro vehículo "
            f"(NIV {misma_placa.niv})."
        )

    vehiculo = Vehiculo(
        cliente_id=cliente_id,
        niv=niv,
        placa=datos.placa,
        folio_tarjeta=datos.folio_tarjeta,
        marca=datos.marca,
        linea=datos.linea,
        modelo_anio=datos.modelo_anio,
        color=datos.color,
        combustible=datos.combustible,
        clase=datos.clase,
        tipo=datos.tipo,
        uso=datos.uso,
        numero_motor=datos.numero_motor,
        capacidad_pasajeros=datos.capacidad_pasajeros,
        entidad_placa=datos.entidad_placa,
        en_programa_estatal=(datos.entidad_placa == "VER"),
        registrado_por=empleado_id,
    )
    sesion.add(vehiculo)
    sesion.flush()

    sesion.add(
        VehiculoPlaca(
            vehiculo_id=vehiculo.id,
            placa=datos.placa,
            vigente_desde=date.today(),
            motivo=MotivoPlaca.ALTA,
            registrado_por=empleado_id,
        )
    )
    sesion.flush()
    sesion.refresh(vehiculo)   # trae placa_normalizada y ultimo_digito
    return vehiculo


def cambiar_placa(
    sesion: Session, vehiculo: Vehiculo, datos: CambioDePlaca, empleado_id: int
) -> Vehiculo:
    """Registra el reemplazo conservando la placa anterior.

    Al cambiar la placa puede cambiar el periodo que le toca: el sistema
    debe recalcular sus recordatorios pendientes.
    """
    if _normalizar_placa_sql(datos.placa_nueva) == vehiculo.placa_normalizada:
        raise ReglaDeNegocio("La placa nueva es igual a la actual.")

    ocupada = sesion.scalar(
        select(Vehiculo).where(
            Vehiculo.placa_normalizada == _normalizar_placa_sql(datos.placa_nueva),
            Vehiculo.id != vehiculo.id,
        )
    )
    if ocupada is not None:
        raise ReglaDeNegocio(
            f"La placa {datos.placa_nueva} ya está asignada al NIV {ocupada.niv}."
        )

    vigente = sesion.scalar(
        select(VehiculoPlaca).where(
            VehiculoPlaca.vehiculo_id == vehiculo.id,
            VehiculoPlaca.vigente_hasta.is_(None),
        )
    )
    if vigente is not None:
        vigente.vigente_hasta = datos.vigente_desde

    sesion.add(
        VehiculoPlaca(
            vehiculo_id=vehiculo.id,
            placa=datos.placa_nueva,
            vigente_desde=datos.vigente_desde,
            motivo=datos.motivo,
            registrado_por=empleado_id,
        )
    )

    vehiculo.placa = datos.placa_nueva
    if datos.entidad_placa is not None:
        vehiculo.entidad_placa = datos.entidad_placa
        vehiculo.en_programa_estatal = datos.entidad_placa == "VER"

    sesion.commit()
    sesion.refresh(vehiculo)
    return vehiculo


# --------------------------------------------------------------- búsqueda --

def buscar_clientes(
    sesion: Session,
    texto: str | None = None,
    limite: int = 50,
    desplazamiento: int = 0,
) -> list[Cliente]:
    """Búsqueda unificada: nombre, teléfono, correo, placa o NIV.

    En el mostrador la gente llega diciendo la placa, no su nombre. Que un
    solo campo acepte todo evita tener dos pantallas separadas.
    """
    consulta = select(Cliente)

    if texto and texto.strip():
        t = texto.strip()
        como = f"%{t}%"
        placa = f"%{_normalizar_placa_sql(t)}%"
        solo_digitos = "".join(c for c in t if c.isdigit())

        condiciones = [
            Cliente.nombre.like(como),
            Cliente.correo.like(como),
            Cliente.id.in_(
                select(Vehiculo.cliente_id).where(
                    or_(
                        Vehiculo.placa_normalizada.like(placa),
                        Vehiculo.niv.like(f"%{t.upper()}%"),
                    )
                )
            ),
        ]
        if solo_digitos:
            condiciones.append(Cliente.telefono_e164.like(f"%{solo_digitos}%"))

        consulta = consulta.where(or_(*condiciones))

    consulta = consulta.order_by(Cliente.nombre).limit(limite).offset(desplazamiento)
    return list(sesion.scalars(consulta))


# ---------------------------------------------------- estado del vehículo --

def describir_vehiculo(vehiculo: Vehiculo, hoy: date | None = None) -> VehiculoPublico:
    """Arma la vista pública agregando el estado calculado.

    El cálculo vive en `dominio/calendario.py`; aquí solo se traduce.
    """
    salida = VehiculoPublico.model_validate(vehiculo)
    hoy = hoy or date.today()

    if not vehiculo.genera_recordatorios:
        return salida

    estado, ventana = estado_de_cumplimiento(
        vehiculo.ultimo_digito, hoy, vehiculo.fechas_aprobadas
    )
    salida.estado = estado
    if ventana is not None:
        salida.ventana = PeriodoResumen(
            etiqueta=ventana.etiqueta, inicio=ventana.inicio, fin=ventana.fin
        )
        salida.dias_restantes = ventana.dias_restantes(hoy)
    return salida


def dar_de_baja_contacto(sesion: Session, cliente: Cliente) -> Cliente:
    """El cliente pidió no recibir más mensajes.

    No se borran sus datos: se necesitan para la bitácora de verificaciones.
    Lo que se apaga es la generación de recordatorios.
    """
    cliente.estado_contacto = EstadoContacto.BAJA
    cliente.consent_whatsapp = False
    cliente.consent_correo = False
    sesion.commit()
    sesion.refresh(cliente)
    return cliente
