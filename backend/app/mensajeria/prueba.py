"""El correo de prueba, en un solo lugar.

Lo usan dos caminos: el botón «Enviar correo de prueba» de la pantalla de
Recordatorios y el job `probar_correo` desde la terminal. Vive aquí para que
no se separen: si la prueba del sistema manda algo distinto de lo que manda
el job, dejan de servir para comprobar lo mismo.

No es un «hola mundo»: es un aviso real, con su formato, su botón y su pie.
La prueba sirve para ver lo que va a recibir el cliente.
"""

from __future__ import annotations

from datetime import date

from app.config import obtener_config
from app.mensajeria.base import Mensaje
from app.mensajeria.plantillas import construir
from app.modelos.recordatorio import Canal

#: Placa inventada para el ejemplo. Termina en 7, así que le toca el periodo
#: de agosto–septiembre: cualquiera sirve, lo que importa es que el correo
#: salga con datos coherentes.
PLACA_DE_MUESTRA = "YUN-047-A"


def armar_mensaje_de_prueba(destino: str) -> Mensaje:
    config = obtener_config()

    # El enlace va DIRECTO a la consulta pública. En un recordatorio real
    # pasa antes por /r/{id}/{firma} para registrar el clic, pero aquí no hay
    # ningún recordatorio que registrar.
    enlace = f"{config.url_consulta}?placa=YUN047A"

    from app.dominio.calendario import ventanas_del_anio

    _, ventana = ventanas_del_anio(7, date.today().year)
    contenido = construir(
        "aviso_2", Canal.CORREO,
        nombre="Prueba del sistema", placa=PLACA_DE_MUESTRA,
        ventana=ventana, dias_restantes=ventana.dias_restantes(date.today()),
        enlace=enlace,
    )

    return Mensaje(
        destino=destino,
        asunto=f"[PRUEBA] {contenido.asunto}",
        cuerpo=contenido.cuerpo,
        clave_plantilla="aviso_2",
        enlace=enlace,
        parrafos=contenido.parrafos,
        pie=contenido.pie,
    )
