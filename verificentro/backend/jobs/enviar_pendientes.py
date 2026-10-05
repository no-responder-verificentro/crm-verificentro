"""Envía los recordatorios que ya tocan.

    python -m jobs.enviar_pendientes

Con PROVEEDOR_WHATSAPP=consola en el .env, los imprime en pantalla en lugar
de mandarlos. Así se puede ver el flujo completo antes de tener nada de Meta.
"""

from app.config import obtener_config
from app.database import SesionLocal
from app.servicios import recordatorios as servicio


def main() -> int:
    config = obtener_config()
    modo = config.proveedor_whatsapp

    if modo == "consola":
        print("MODO CONSOLA: los mensajes se imprimen, no se envían.\n")

    with SesionLocal() as sesion:
        r = servicio.enviar_pendientes(sesion)

    print(f"\n  Enviados: {r.enviados}   Fallidos: {r.fallidos}")
    if r.contactos_marcados:
        print(f"  {r.contactos_marcados} contacto(s) marcados como no localizables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
