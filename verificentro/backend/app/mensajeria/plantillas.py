"""Los textos de cada aviso.

Están aquí y no en la base porque son el borrador: cuando se dé de alta la
cuenta de WhatsApp Business, estos mismos textos se registran en Meta como
plantillas y quedan en `plantillas_mensaje` con su nombre y su versión.

Reglas que sigue la redacción, y conviene no romperlas:

- Son mensajes de UTILIDAD, no de publicidad. Avisan de un trámite obligatorio
  con fecha límite. Si se les mete promoción, Meta los reclasifica como
  marketing: sube el costo, baja la entregabilidad y aparece el botón de
  "dejar de recibir promociones".
- Nada de urgencia falsa ni de mayúsculas gritando. El aviso vale porque es
  útil; si molesta, la gente bloquea el número y se pierde el canal.
- Siempre dicen quién escribe, para qué auto, hasta cuándo y dónde.
- Siempre traen la forma de darse de baja. Además de ser lo correcto, es lo
  que evita que reporten los mensajes como spam.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.dominio.calendario import Ventana
from app.modelos.recordatorio import Canal

FIRMA = "Verificentro · Av. Ruíz Cortines 256, Col. Centro · Lun a sáb 9:00–16:00"
BAJA = "Si no quieres recibir estos avisos, responde BAJA."

#: Nombre con que cada aviso queda registrado en Meta, y el orden de sus
#: variables ({{1}}, {{2}}, {{3}} dentro de la plantilla aprobada).
#:
#: El nombre TIENE que coincidir con el que se dio de alta en el Administrador
#: de WhatsApp, y el orden de los parámetros con el de la plantilla aprobada.
#: Si no coinciden, Meta rechaza el envío con error 132000 o 132001.
PLANTILLAS_META = {
    "aviso_1":     "verificentro_aviso_previo",
    "aviso_2":     "verificentro_periodo_abierto",
    "aviso_3":     "verificentro_mitad_periodo",
    "aviso_4":     "verificentro_ultimos_dias",
    "seguimiento": "verificentro_periodo_vencido",
}


@dataclass(frozen=True)
class Contenido:
    asunto: str | None
    cuerpo: str                      # texto plano, completo
    parrafos: tuple[str, ...] = ()   # solo el mensaje, para armar el HTML
    pie: tuple[str, ...] = ()        # firma y baja, en letra chica
    # Para WhatsApp: el nombre de la plantilla aprobada y sus variables. El
    # cuerpo de arriba solo sirve para la bitácora, porque Meta no acepta
    # texto libre cuando nosotros iniciamos la conversación.
    plantilla_meta: str | None = None
    parametros: tuple[str, ...] = ()


def _fecha(dia) -> str:
    MESES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    return f"{dia.day} de {MESES[dia.month]}"


def construir(
    aviso: str,
    canal: Canal,
    *,
    nombre: str,
    placa: str,
    ventana: Ventana,
    dias_restantes: int,
    enlace: str | None = None,
) -> Contenido:
    """Arma el texto de un aviso concreto."""
    primer_nombre = nombre.split()[0].title()
    cierre = _fecha(ventana.fin)

    textos = {
        "aviso_1": (
            f"Hola {primer_nombre}. Te recordamos que tu vehículo con placa "
            f"{placa} debe verificar en el periodo de {ventana.etiqueta}, que "
            f"abre pronto. Puedes venir desde el primer día para evitar filas.",
            f"Tu verificación de {ventana.etiqueta} está por abrir",
        ),
        "aviso_2": (
            f"Hola {primer_nombre}. Hoy abre el periodo para verificar tu "
            f"vehículo con placa {placa}. Tienes hasta el {cierre}. "
            f"Te atendemos de lunes a sábado de 9:00 a 16:00.",
            f"Ya puedes verificar tu vehículo {placa}",
        ),
        "aviso_3": (
            f"Hola {primer_nombre}. Va a la mitad el periodo para verificar tu "
            f"vehículo con placa {placa}. La fecha límite es el {cierre}. "
            f"Si quieres, puedes apartar una cita y evitar la espera.",
            f"Te quedan {dias_restantes} días para verificar",
        ),
        "aviso_4": (
            f"Hola {primer_nombre}. Quedan pocos días para verificar tu "
            f"vehículo con placa {placa}: el periodo cierra el {cierre}. "
            f"Después de esa fecha aplica multa.",
            f"Últimos días para verificar tu vehículo {placa}",
        ),
        "seguimiento": (
            f"Hola {primer_nombre}. El periodo para verificar tu vehículo con "
            f"placa {placa} cerró el {cierre}. Puedes verificar de todos modos: "
            f"acércate y te decimos cómo regularizarte.",
            f"Tu verificación quedó pendiente",
        ),
    }

    cuerpo, asunto = textos.get(
        aviso,
        (
            f"Hola {primer_nombre}. Te recordamos verificar tu vehículo con "
            f"placa {placa} antes del {cierre}.",
            "Recordatorio de verificación",
        ),
    )

    # Las tres variables de todas las plantillas, en este orden:
    #   {{1}} nombre de pila   {{2}} placa   {{3}} fecha de cierre
    parametros = (primer_nombre, placa, cierre)

    if canal is Canal.WHATSAPP:
        return Contenido(
            asunto=None, cuerpo=f"{cuerpo}\n\n{BAJA}",
            parrafos=(cuerpo,), pie=(BAJA,),
            plantilla_meta=PLANTILLAS_META.get(aviso),
            parametros=parametros,
        )

    # En correo se agrega un enlace: dar clic es el único acuse confiable.
    # En el texto plano va escrito; en el HTML se convierte en botón, por eso
    # se guarda aparte y no dentro de los párrafos.
    texto = f"{cuerpo}\n\nConsulta tu periodo: {enlace}" if enlace else cuerpo

    return Contenido(
        asunto=asunto,
        cuerpo=f"{texto}\n\n{FIRMA}\n{BAJA}",
        parrafos=(cuerpo,),
        pie=(FIRMA, BAJA),
    )
