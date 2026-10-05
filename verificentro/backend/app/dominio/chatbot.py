"""Motor del chatbot, sin depender del canal.

Está separado a propósito: hoy responde en la página web, y el día que se
conecte WhatsApp o Facebook Messenger es el mismo motor con otro adaptador.
Igual que la mensajería.

No usa inteligencia artificial y es una decisión, no una limitación. Las
preguntas de un verificentro son cinco o seis y se repiten; una coincidencia
por palabras clave las resuelve, es instantánea, no cuesta nada y —lo más
importante— es predecible: nunca va a inventar una fecha de verificación.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

__all__ = [
    "Intencion",
    "normalizar",
    "buscar_placa",
    "puntuar",
    "elegir_respuesta",
]

# Formato de placa mexicana, ya sin guiones ni espacios:
#   AAA-000-A  ->  YUN047A     (particulares de Veracruz)
#   AAA-0000   ->  YJX7045     (formato anterior)
#   00-AAA     ->  12ABC       (algunas motos)
#
# Exigir esta forma —y no solo "algo con letras y números"— es lo que evita
# que "cuesta 500 pesos" se interprete como una placa.
FORMATO_PLACA = re.compile(r"^(?:[A-Z]{2,4}\d{2,5}[A-Z]{0,2}|\d{2,5}[A-Z]{2,4})$")

#: Palabras tan comunes que no ayudan a distinguir una pregunta de otra.
VACIAS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "a", "en", "que",
    "qué", "es", "mi", "me", "se", "para", "por", "con", "del", "al", "lo",
    "su", "tu", "hola", "buenas", "buenos", "dias", "días", "tardes", "gracias",
    "cuanto", "cuánto", "cual", "cuál", "como", "cómo", "donde", "dónde",
    "puedo", "hay", "si", "no", "necesito", "quiero", "saber",
}


@dataclass
class Intencion:
    """Lo que se entendió del mensaje."""

    placa: str | None = None
    respuesta_id: int | None = None
    puntaje: int = 0
    palabras: list[str] = field(default_factory=list)

    @property
    def entendida(self) -> bool:
        return self.placa is not None or self.respuesta_id is not None


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que 'Cuándo' y 'cuando' coincidan."""
    if not texto:
        return ""
    sin_acentos = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_acentos if not unicodedata.combining(c))


def _palabras(texto: str) -> list[str]:
    limpio = re.sub(r"[^\w\s]", " ", normalizar(texto))
    return [p for p in limpio.split() if len(p) > 2 and p not in VACIAS]


def buscar_placa(texto: str) -> str | None:
    """Encuentra algo que parezca placa dentro del mensaje.

    Acepta 'YUN-047-A', 'yun047a' y 'mi placa es YUN 047 A': la gente la
    escribe de las tres formas.

    Se prueban grupos de hasta tres pedazos seguidos, empezando por los más
    largos, porque 'YUN 047 A' son tres pedazos que juntos forman una placa
    pero por separado no parecen nada.
    """
    if not texto:
        return None

    pedazos = [p for p in re.split(r"[^A-Z0-9]+", texto.upper()) if p]

    for cuantos in (3, 2, 1):
        for inicio in range(len(pedazos) - cuantos + 1):
            grupo = pedazos[inicio : inicio + cuantos]
            # Si son varios pedazos, cada uno tiene que ser corto: una placa
            # se parte en trozos de 3 o 4, no en palabras completas.
            if cuantos > 1 and any(len(p) > 4 for p in grupo):
                continue
            candidato = "".join(grupo)
            if 5 <= len(candidato) <= 10 and FORMATO_PLACA.match(candidato):
                return candidato
    return None


SALUDOS = {
    "hola", "buenas", "buenos dias", "buenos días", "buenas tardes",
    "buenas noches", "que tal", "qué tal", "hey", "holi", "saludos",
    "buen dia", "buen día",
}

GRACIAS = {"gracias", "muchas gracias", "ok gracias", "listo gracias",
           "perfecto gracias", "muy amable"}


def es_cortesia(texto: str) -> str | None:
    """Distingue un saludo o un agradecimiento de una pregunta de verdad.

    Sin esto, cada 'hola' acabaría en la lista de preguntas sin resolver y el
    panel se llenaría de ruido que nadie puede convertir en respuesta.
    """
    limpio = re.sub(r"[^\w\s]", "", normalizar(texto)).strip()
    if not limpio:
        return None
    if limpio in SALUDOS or (len(limpio.split()) <= 3
                             and any(s in limpio for s in SALUDOS)):
        return "saludo"
    if limpio in GRACIAS or (len(limpio.split()) <= 3 and "gracias" in limpio):
        return "gracias"
    return None


def menciona_placa(texto: str) -> bool:
    """Si la persona habló de su placa, aunque no se haya podido leer."""
    return "placa" in normalizar(texto)


def puntuar(texto: str, palabras_clave: str | None) -> int:
    """Cuántas palabras clave de una respuesta aparecen en el mensaje."""
    if not palabras_clave:
        return 0
    del_mensaje = set(_palabras(texto))
    claves = {normalizar(p).strip() for p in palabras_clave.split(",")}
    claves.discard("")
    return sum(
        1 for clave in claves
        if clave in del_mensaje or any(clave in p for p in del_mensaje)
    )


def elegir_respuesta(texto: str, catalogo: list[tuple[int, str | None]]) -> Intencion:
    """Elige la respuesta del catálogo que mejor coincide.

    `catalogo` es una lista de (id, palabras_clave). Se devuelve la de mayor
    puntaje; si ninguna coincide, la intención queda sin entender y el
    llamador la registra como pregunta pendiente.
    """
    intencion = Intencion(placa=buscar_placa(texto), palabras=_palabras(texto))

    mejor_id, mejor_puntaje = None, 0
    for identificador, claves in catalogo:
        puntaje = puntuar(texto, claves)
        if puntaje > mejor_puntaje:
            mejor_id, mejor_puntaje = identificador, puntaje

    intencion.respuesta_id = mejor_id
    intencion.puntaje = mejor_puntaje
    return intencion
