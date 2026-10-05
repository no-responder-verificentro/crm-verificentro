"""Generación y envío de recordatorios.

Son dos procesos separados a propósito:

1. **Generar** llena la cola. Corre una vez al día, calcula a quién le toca un
   aviso hoy y escribe las filas con estado `programado`. No manda nada.
2. **Enviar** toma lo que ya está en la cola y lo entrega al proveedor.

Separarlos permite ver la cola llenarse correctamente durante días antes de
conectar un solo mensaje real, y evita que un reinicio a media mañana deje
mensajes a medio enviar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.modelos  # noqa: F401  registra todos los modelos
from app.config import obtener_config
from app.dominio.calendario import fechas_de_aviso, ventanas_del_anio
from app.mensajeria import Mensaje, obtener_adaptador
from app.mensajeria.enlaces import enlace_de_seguimiento
from app.mensajeria.plantillas import construir
from app.modelos.cliente import Cliente, EstadoContacto
from app.modelos.recordatorio import (
    ENTREGA_FALLIDA,
    ORDEN_ENTREGA,
    Canal,
    EstadoEntrega,
    EstadoRecordatorio,
    Recordatorio,
    RecordatorioEvento,
    TipoRecordatorio,
)
from app.modelos.vehiculo import Resultado, Vehiculo


def _ahora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class ResumenGeneracion:
    dia: date
    creados: int = 0
    duplicados: int = 0
    cancelados: int = 0
    sin_consentimiento: int = 0
    detalle: list[str] = field(default_factory=list)


@dataclass
class ResumenEnvio:
    enviados: int = 0
    fallidos: int = 0
    contactos_marcados: int = 0


# ===========================================================================
#  1. Generar la cola
# ===========================================================================

def _canales_disponibles(cliente: Cliente) -> list[tuple[Canal, str]]:
    """Por dónde se le puede escribir.

    Tienen que coincidir tres cosas: que el cliente siga siendo contactable,
    que haya autorizado ese canal, y que el canal esté encendido en la
    configuración. Lo último importa: si WhatsApp está apagado porque falta el
    trámite con Meta, no tiene sentido llenar la cola de mensajes que nunca se
    van a poder enviar.
    """
    if cliente.estado_contacto is not EstadoContacto.CONTACTABLE:
        return []

    activos = {c.strip().lower() for c in obtener_config().canales_activos}
    canales = []
    if (Canal.WHATSAPP.value in activos
            and cliente.consent_whatsapp and cliente.telefono_e164):
        canales.append((Canal.WHATSAPP, cliente.telefono_e164))
    if (Canal.CORREO.value in activos
            and cliente.consent_correo and cliente.correo):
        canales.append((Canal.CORREO, cliente.correo))
    return canales


def _ya_cumplio(vehiculo: Vehiculo, ventana) -> bool:
    """Si tiene una verificación APROBADA dentro de esa ventana.

    Las rechazadas no cuentan: obligan a volver dentro del mismo periodo.
    """
    return any(
        v.resultado is Resultado.APROBADO and ventana.contiene(v.fecha)
        for v in vehiculo.verificaciones
    )


def _avisos_de_hoy(digito: int, dia: date):
    """Qué avisos, de qué ventanas, caen exactamente en ese día.

    Se revisan las ventanas del año pasado, este y el próximo: el primer aviso
    sale 15 días antes de que abra —que puede caer en diciembre del año
    anterior— y el de seguimiento, un día después del cierre.
    """
    encontrados = []
    for anio in (dia.year - 1, dia.year, dia.year + 1):
        for ventana in ventanas_del_anio(digito, anio):
            for aviso in fechas_de_aviso(ventana):
                if aviso.fecha == dia:
                    encontrados.append((aviso, ventana))
    return encontrados


def cancelar_los_que_ya_verificaron(sesion: Session, dia: date) -> int:
    """Apaga los recordatorios pendientes de quien ya cumplió.

    Es la regla más importante del sistema: nadie recibe avisos después de
    haber verificado.
    """
    pendientes = sesion.scalars(
        select(Recordatorio).where(
            Recordatorio.estado.in_(
                [EstadoRecordatorio.PROGRAMADO, EstadoRecordatorio.PAUSADO]
            ),
            Recordatorio.tipo == TipoRecordatorio.VENTANA,
        )
    )

    cancelados = 0
    for recordatorio in pendientes:
        vehiculo = sesion.get(Vehiculo, recordatorio.vehiculo_id)
        if vehiculo is None or vehiculo.ultimo_digito is None:
            continue
        ventanas = ventanas_del_anio(vehiculo.ultimo_digito, recordatorio.ventana_anio)
        ventana = ventanas[(recordatorio.ventana_periodo or 1) - 1]
        if _ya_cumplio(vehiculo, ventana):
            recordatorio.estado = EstadoRecordatorio.CANCELADO
            recordatorio.motivo_error = None
            cancelados += 1

    if cancelados:
        sesion.commit()
    return cancelados


def generar_del_dia(
    sesion: Session, dia: date | None = None, hora_envio: int | None = None
) -> ResumenGeneracion:
    """Escribe en la cola los avisos que toca mandar ese día."""
    config = obtener_config()
    dia = dia or date.today()
    hora_envio = hora_envio if hora_envio is not None else config.hora_envio_recordatorios
    salida = ResumenGeneracion(dia=dia)

    salida.cancelados = cancelar_los_que_ya_verificaron(sesion, dia)

    vehiculos = sesion.scalars(
        select(Vehiculo).where(
            Vehiculo.activo.is_(True),
            Vehiculo.en_programa_estatal.is_(True),
            Vehiculo.ultimo_digito.is_not(None),
        )
    ).all()

    momento = datetime.combine(dia, time(hour=hora_envio))

    for vehiculo in vehiculos:
        avisos = _avisos_de_hoy(vehiculo.ultimo_digito, dia)
        if not avisos:
            continue

        cliente = sesion.get(Cliente, vehiculo.cliente_id)
        canales = _canales_disponibles(cliente)

        for aviso, ventana in avisos:
            if _ya_cumplio(vehiculo, ventana):
                continue

            if not canales:
                salida.sin_consentimiento += 1
                continue

            for canal, destino in canales:
                recordatorio = Recordatorio(
                    vehiculo_id=vehiculo.id,
                    cliente_id=cliente.id,
                    tipo=TipoRecordatorio.VENTANA,
                    aviso_clave=aviso.clave,
                    ventana_anio=ventana.anio,
                    ventana_periodo=ventana.periodo,
                    canal=canal,
                    destino=destino,
                    programado_para=momento,
                )
                sesion.add(recordatorio)
                try:
                    # El índice único sobre la clave de idempotencia rechaza el
                    # duplicado si el job ya corrió hoy.
                    sesion.commit()
                except IntegrityError:
                    sesion.rollback()
                    salida.duplicados += 1
                    continue

                salida.creados += 1
                salida.detalle.append(
                    f"{vehiculo.placa} · {canal.value} · {aviso.clave} · "
                    f"{ventana.etiqueta}"
                )

    return salida


# ===========================================================================
#  2. Enviar lo que está en la cola
# ===========================================================================

def _armar_mensaje(sesion: Session, recordatorio: Recordatorio) -> Mensaje:
    vehiculo = sesion.get(Vehiculo, recordatorio.vehiculo_id)
    cliente = sesion.get(Cliente, recordatorio.cliente_id)
    ventanas = ventanas_del_anio(vehiculo.ultimo_digito, recordatorio.ventana_anio)
    ventana = ventanas[(recordatorio.ventana_periodo or 1) - 1]

    # Solo el correo lleva enlace de seguimiento: en WhatsApp el acuse de
    # entrega y lectura lo reporta Meta, no hace falta.
    enlace = (
        enlace_de_seguimiento(recordatorio.id)
        if recordatorio.canal is Canal.CORREO
        else None
    )

    contenido = construir(
        recordatorio.aviso_clave,
        recordatorio.canal,
        nombre=cliente.nombre,
        placa=vehiculo.placa,
        ventana=ventana,
        dias_restantes=max(ventana.dias_restantes(date.today()), 0),
        enlace=enlace,
    )
    return Mensaje(
        destino=recordatorio.destino,
        asunto=contenido.asunto,
        cuerpo=contenido.cuerpo,
        clave_plantilla=recordatorio.aviso_clave,
        enlace=enlace,
        parrafos=contenido.parrafos,
        pie=contenido.pie,
        plantilla_meta=contenido.plantilla_meta,
        parametros=contenido.parametros,
    )


def _registrar_evento(
    sesion: Session, recordatorio: Recordatorio, evento: str,
    codigo: str | None = None
) -> None:
    sesion.add(
        RecordatorioEvento(
            recordatorio_id=recordatorio.id,
            evento=evento,
            ocurrido_en=_ahora(),
            codigo_error=codigo,
        )
    )


def _marcar_no_localizable(sesion: Session, cliente_id: int) -> bool:
    """Tras varios fallos seguidos, se deja de gastar mensajes en ese contacto.

    Meta no informa quién bloqueó el número, así que esto es lo más cerca que
    se puede estar de saberlo: si nunca llega nada, se deja de intentar.
    """
    config = obtener_config()
    ultimos = sesion.scalars(
        select(Recordatorio)
        .where(Recordatorio.cliente_id == cliente_id)
        .order_by(Recordatorio.id.desc())
        .limit(config.max_fallos_antes_de_marcar)
    ).all()

    if len(ultimos) < config.max_fallos_antes_de_marcar:
        return False
    if not all(r.estado_entrega in ENTREGA_FALLIDA for r in ultimos):
        return False

    cliente = sesion.get(Cliente, cliente_id)
    if cliente.estado_contacto is EstadoContacto.CONTACTABLE:
        cliente.estado_contacto = EstadoContacto.NO_LOCALIZABLE
        return True
    return False


def enviar_pendientes(
    sesion: Session, ahora: datetime | None = None, silencioso: bool = False
) -> ResumenEnvio:
    """Toma la cola y la entrega al proveedor."""
    ahora = ahora or _ahora()
    salida = ResumenEnvio()

    pendientes = sesion.scalars(
        select(Recordatorio)
        .where(
            Recordatorio.estado == EstadoRecordatorio.PROGRAMADO,
            Recordatorio.programado_para <= ahora,
        )
        .order_by(Recordatorio.programado_para)
    ).all()

    adaptadores = {}

    for recordatorio in pendientes:
        # Se marca antes de salir: si el proceso muere a medio envío, la fila
        # no queda como 'programado' y no se manda dos veces.
        recordatorio.estado = EstadoRecordatorio.EN_PROCESO
        sesion.commit()

        if recordatorio.canal not in adaptadores:
            adaptadores[recordatorio.canal] = obtener_adaptador(
                recordatorio.canal, silencioso
            )
        adaptador = adaptadores[recordatorio.canal]

        try:
            resultado = adaptador.enviar(_armar_mensaje(sesion, recordatorio))
        except Exception as exc:
            resultado = type(
                "R", (), {"exito": False, "error": f"{type(exc).__name__}: {exc}",
                          "id_externo": None, "codigo": None}
            )()

        if resultado.exito:
            recordatorio.estado = EstadoRecordatorio.ENVIADO
            recordatorio.estado_entrega = EstadoEntrega.ENVIADO
            recordatorio.id_externo = resultado.id_externo
            recordatorio.enviado_en = ahora
            _registrar_evento(sesion, recordatorio, "enviado")
            salida.enviados += 1
        else:
            recordatorio.estado = EstadoRecordatorio.ERROR
            # Si el proveedor dijo por qué falló, se conserva el matiz: un
            # rebote duro es permanente y uno suave se puede reintentar.
            try:
                entrega = EstadoEntrega(resultado.codigo)
            except ValueError:
                entrega = EstadoEntrega.FALLIDO
            recordatorio.estado_entrega = entrega
            recordatorio.motivo_error = (resultado.error or "")[:255]
            _registrar_evento(sesion, recordatorio, "fallido", resultado.codigo)
            salida.fallidos += 1

        sesion.commit()

        if not resultado.exito and _marcar_no_localizable(
            sesion, recordatorio.cliente_id
        ):
            salida.contactos_marcados += 1
            sesion.commit()

    return salida


# ===========================================================================
#  3. Acuses de entrega
# ===========================================================================

def registrar_entrega(
    sesion: Session,
    recordatorio: Recordatorio,
    nuevo: EstadoEntrega,
    ocurrido_en: datetime | None = None,
    codigo: str | None = None,
) -> bool:
    """Aplica un acuse. Devuelve si el estado avanzó.

    Los acuses llegan desordenados con más frecuencia de la que uno espera:
    puede llegar "entregado" después de "leído". Por eso el estado SOLO
    avanza; un evento atrasado se guarda en la bitácora pero no retrocede
    lo que ya se sabía.
    """
    actual = ORDEN_ENTREGA.get(recordatorio.estado_entrega, 0)
    entrante = ORDEN_ENTREGA.get(nuevo, 0)

    _registrar_evento(sesion, recordatorio, nuevo.value, codigo)

    if entrante <= actual:
        sesion.commit()
        return False

    recordatorio.estado_entrega = nuevo
    sesion.commit()
    return True


# ===========================================================================
#  4. Consulta
# ===========================================================================

def cola(sesion: Session, horas: int = 48) -> list[Recordatorio]:
    """Lo que está por salir en las próximas horas."""
    limite = _ahora() + timedelta(hours=horas)
    return list(
        sesion.scalars(
            select(Recordatorio)
            .where(
                Recordatorio.estado.in_(
                    [EstadoRecordatorio.PROGRAMADO, EstadoRecordatorio.PAUSADO]
                ),
                Recordatorio.programado_para <= limite,
            )
            .order_by(Recordatorio.programado_para)
        )
    )


def historial(sesion: Session, limite: int = 100) -> list[Recordatorio]:
    return list(
        sesion.scalars(
            select(Recordatorio)
            .where(
                Recordatorio.estado.in_(
                    [EstadoRecordatorio.ENVIADO, EstadoRecordatorio.ERROR]
                )
            )
            .order_by(Recordatorio.enviado_en.desc(), Recordatorio.id.desc())
            .limit(limite)
        )
    )
