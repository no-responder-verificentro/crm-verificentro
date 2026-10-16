"""Conversación del chatbot.

Une el motor de intención con lo que hay en la base: el catálogo de
respuestas, el calendario y los horarios de cita.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.modelos  # noqa: F401
from app.dominio.agenda import AgendaNoDisponible
from app.dominio.calendario import PlacaSinDigito, ultimo_digito, ventanas_del_anio
from app.dominio.chatbot import (
    elegir_respuesta,
    es_cortesia,
    menciona_placa,
    normalizar,
)
from app.modelos.chatbot import ChatbotPendiente, ChatbotRespuesta, TipoRespuesta
from app.servicios import citas as servicio_citas

#: Ventana de WhatsApp. Se guarda aunque el canal sea web, para que el día que
#: se conecte Meta la pantalla ya sepa si todavía se puede contestar.
HORAS_VENTANA = 24


@dataclass
class Respuesta:
    texto: str
    tipo: str = "texto_fijo"
    sugerencias: list[str] = field(default_factory=list)
    entendida: bool = True


def _ahora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _catalogo(sesion: Session) -> list[ChatbotRespuesta]:
    return list(
        sesion.scalars(
            select(ChatbotRespuesta)
            .where(ChatbotRespuesta.activa.is_(True))
            .order_by(ChatbotRespuesta.orden)
        )
    )


def sugerencias(sesion: Session, cuantas: int = 4) -> list[str]:
    """Las preguntas que se ofrecen como botones."""
    return [r.pregunta for r in _catalogo(sesion)[:cuantas]]


def _responder_placa(sesion: Session, placa: str) -> Respuesta:
    try:
        digito = ultimo_digito(placa)
    except PlacaSinDigito:
        return Respuesta(
            texto=(
                f"La placa {placa} no tiene ningún número, y el calendario se "
                "rige por el último dígito. ¿Puedes revisarla en tu tarjeta de "
                "circulación?"
            )
        )

    hoy = date.today()
    ventanas = ventanas_del_anio(digito, hoy.year)
    vigente = next((v for v in ventanas if v.contiene(hoy)), None)
    etiquetas = " y ".join(v.etiqueta for v in ventanas)

    if vigente is not None:
        dias = vigente.dias_restantes(hoy)
        texto = (
            f"Tu placa {placa} termina en {digito}, así que te toca verificar "
            f"en {etiquetas}.\n\n"
            f"Ahorita estás dentro del periodo de {vigente.etiqueta}: te quedan "
            f"{dias} día{'s' if dias != 1 else ''}, hasta el "
            f"{vigente.fin.day}/{vigente.fin.month}."
        )
    else:
        texto = (
            f"Tu placa {placa} termina en {digito}, así que te toca verificar "
            f"en {etiquetas}."
        )
        proxima = min((v for v in ventanas if v.inicio > hoy),
                      key=lambda v: v.inicio, default=None)
        if proxima is not None:
            texto += (
                f"\n\nTu siguiente periodo abre en {(proxima.inicio - hoy).days} "
                "días."
            )

    return Respuesta(
        texto=texto, tipo="automatica",
        sugerencias=["¿Qué documentos debo llevar?", "Quiero agendar una cita"],
    )


def _responder_cita(sesion: Session) -> Respuesta:
    """Ofrece los horarios libres del próximo día hábil con lugar."""
    dia = date.today() + timedelta(days=1)
    for _ in range(14):
        try:
            libres = servicio_citas.disponibilidad(sesion, dia)
        except AgendaNoDisponible:
            dia += timedelta(days=1)
            continue
        if libres:
            horas = "   ".join(f"{h:%H:%M}" for h, _ in libres[:6])
            return Respuesta(
                texto=(
                    f"Para el {dia.day}/{dia.month} tenemos estos horarios "
                    f"libres:\n\n{horas}\n\n"
                    "Llámanos o pásate al mostrador para apartarlo. También "
                    "atendemos sin cita, por orden de llegada."
                ),
                tipo="con_enlace",
            )
        dia += timedelta(days=1)

    return Respuesta(
        texto=(
            "No tengo horarios libres en los próximos días. Puedes pasar sin "
            "cita: atendemos de lunes a sábado de 9:00 a 16:00."
        )
    )


def _registrar_pendiente(sesion: Session, texto: str, canal, contacto: str) -> None:
    """Guarda lo que no se supo contestar.

    Es lo que hace que el bot mejore: esas preguntas se revisan y se
    convierten en respuestas del catálogo.
    """
    normalizado = normalizar(texto)[:500]
    existente = sesion.scalar(
        select(ChatbotPendiente).where(
            ChatbotPendiente.pregunta == normalizado,
            ChatbotPendiente.resuelta.is_(False),
        )
    )
    ahora = _ahora()
    if existente is not None:
        existente.veces += 1
        existente.ultima_vez = ahora
        existente.ventana_expira_en = ahora + timedelta(hours=HORAS_VENTANA)
    else:
        sesion.add(
            ChatbotPendiente(
                canal=canal, contacto_externo=contacto[:120],
                pregunta=normalizado, ultima_vez=ahora,
                ventana_expira_en=ahora + timedelta(hours=HORAS_VENTANA),
            )
        )
    sesion.commit()


def conversar(sesion: Session, texto: str, canal, contacto: str = "web") -> Respuesta:
    """Recibe lo que escribió la persona y devuelve qué contestarle."""
    texto = (texto or "").strip()
    if not texto:
        return Respuesta(
            texto="Escríbeme tu duda o la placa de tu vehículo.",
            sugerencias=sugerencias(sesion),
        )

    cortesia = es_cortesia(texto)
    if cortesia == "saludo":
        return Respuesta(
            texto=(
                "¡Hola! Puedo decirte cuándo te toca verificar, qué documentos "
                "llevar, nuestro horario y los espacios libres para cita.\n\n"
                "Escríbeme tu duda o la placa de tu vehículo."
            ),
            sugerencias=sugerencias(sesion),
        )
    if cortesia == "gracias":
        return Respuesta(
            texto="Con gusto. Aquí estoy si necesitas algo más.",
            sugerencias=sugerencias(sesion, 3),
        )

    catalogo = _catalogo(sesion)
    intencion = elegir_respuesta(texto, [(r.id, r.palabras_clave) for r in catalogo])
    elegida = next((r for r in catalogo if r.id == intencion.respuesta_id), None)

    # Si trae placa y la respuesta que ganó es la automática —o no ganó
    # ninguna— se contesta con el calendario, que es lo que de verdad quería.
    pide_periodo = elegida is not None and elegida.tipo is TipoRespuesta.AUTOMATICA
    if intencion.placa and (pide_periodo or elegida is None):
        return _responder_placa(sesion, intencion.placa)

    # Habló de su placa pero no se pudo leer: casi siempre es que no trae
    # números, y el calendario se rige justo por el último número.
    if intencion.placa is None and menciona_placa(texto):
        return Respuesta(
            texto=(
                "No pude leer esa placa. El calendario se rige por el último "
                "número de la placa, así que necesito que traiga al menos uno.\n\n"
                "Escríbela como viene en tu tarjeta de circulación, por ejemplo "
                "YUN-047-A."
            ),
            tipo="automatica",
        )

    if elegida is None:
        _registrar_pendiente(sesion, texto, canal, contacto)
        return Respuesta(
            texto=(
                "Esa no me la sé todavía. Ya la anoté para que alguien del "
                "verificentro la revise.\n\nMientras tanto, puedo ayudarte con "
                "esto:"
            ),
            entendida=False,
            sugerencias=sugerencias(sesion),
        )

    if elegida.tipo is TipoRespuesta.AUTOMATICA:
        return Respuesta(
            texto=(
                "Con gusto. Escríbeme la placa de tu vehículo, como YUN-047-A, "
                "y te digo los dos periodos que te tocan este año."
            ),
            tipo="automatica",
        )

    if "cita" in normalizar(elegida.pregunta or ""):
        return _responder_cita(sesion)

    return Respuesta(
        texto=elegida.respuesta,
        tipo=elegida.tipo.value,
        sugerencias=sugerencias(sesion, 3),
    )
