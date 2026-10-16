"""Adaptador que imprime en pantalla en lugar de enviar.

Es el que permite construir y probar todo el flujo de recordatorios sin
depender de Meta ni de un servidor de correo. Se activa con
PROVEEDOR_WHATSAPP=consola en el archivo .env.
"""

from __future__ import annotations

import uuid

from app.mensajeria.base import Adaptador, Mensaje, Resultado


class AdaptadorConsola(Adaptador):
    nombre = "consola"

    def __init__(self, canal: str = "mensaje", silencioso: bool = False):
        self.canal = canal
        self.silencioso = silencioso
        self.enviados: list[Mensaje] = []

    def enviar(self, mensaje: Mensaje) -> Resultado:
        self.enviados.append(mensaje)
        if not self.silencioso:
            print()
            print("  " + "─" * 62)
            print(f"  {self.canal.upper()}  →  {mensaje.destino}")
            if mensaje.asunto:
                print(f"  Asunto: {mensaje.asunto}")
            print("  " + "─" * 62)
            for linea in mensaje.cuerpo.splitlines():
                print(f"  {linea}")
            print("  " + "─" * 62)
        return Resultado(exito=True, id_externo=f"consola-{uuid.uuid4().hex[:12]}")
