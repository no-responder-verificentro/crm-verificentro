"""Llena la cola de recordatorios. NO envía nada.

    python -m jobs.generar_recordatorios                # solo hoy
    python -m jobs.generar_recordatorios 2026-09-25     # una fecha concreta
    python -m jobs.generar_recordatorios --dias 90      # hoy y los 89 siguientes

En operación normal se programa para correr UNA VEZ AL DÍA, sin argumentos.
La mayoría de los días no genera nada, y eso es correcto: solo crea filas
cuando a alguien le toca un aviso exactamente ese día.

`--dias` sirve para dos cosas: ver la pantalla con contenido mientras se
desarrolla, y ponerse al corriente si el servidor estuvo apagado varios días.
Adelantar la generación es seguro porque cada fila lleva su fecha de salida y
el job de envío respeta esa fecha.
"""

import sys
from datetime import date, timedelta

from app.database import SesionLocal
from app.servicios import recordatorios as servicio


def _argumentos() -> tuple[date, int]:
    dias = 1
    dia = date.today()
    args = sys.argv[1:]

    if "--dias" in args:
        i = args.index("--dias")
        try:
            dias = int(args[i + 1])
        except (IndexError, ValueError):
            print("Uso: --dias N   (por ejemplo, --dias 90)")
            raise SystemExit(1) from None
        args = args[:i] + args[i + 2:]

    if args:
        try:
            dia = date.fromisoformat(args[0])
        except ValueError:
            print(f"'{args[0]}' no es una fecha. Usa el formato 2026-09-25.")
            raise SystemExit(1) from None

    return dia, max(dias, 1)


def main() -> int:
    inicio, dias = _argumentos()
    creados = duplicados = cancelados = sin_contacto = 0
    detalle: list[tuple[date, list[str]]] = []

    with SesionLocal() as sesion:
        for n in range(dias):
            dia = inicio + timedelta(days=n)
            r = servicio.generar_del_dia(sesion, dia)
            creados += r.creados
            duplicados += r.duplicados
            cancelados += r.cancelados
            sin_contacto += r.sin_consentimiento
            if r.detalle:
                detalle.append((dia, r.detalle))

    if dias == 1:
        print(f"Recordatorios generados para el {inicio}")
    else:
        print(f"Recordatorios generados del {inicio} al "
              f"{inicio + timedelta(days=dias - 1)}")

    print(f"  Nuevos en la cola           : {creados}")
    print(f"  Ya existían                 : {duplicados}")
    print(f"  Cancelados (ya verificaron) : {cancelados}")
    print(f"  Sin forma de contactar      : {sin_contacto}")

    if detalle:
        print("\n  Detalle por día:")
        for dia, lineas in detalle[:15]:
            print(f"    {dia}  ({len(lineas)})")
            for linea in lineas[:3]:
                print(f"       {linea}")
            if len(lineas) > 3:
                print(f"       … y {len(lineas) - 3} más")
        if len(detalle) > 15:
            print(f"    … y {len(detalle) - 15} días más")
    elif creados == 0:
        print(
            "\n  No le tocaba aviso a nadie en ese rango. Es normal: el job\n"
            "  solo genera cuando la fecha coincide con uno de los cinco\n"
            "  avisos. Prueba con --dias 90 para ver lo que viene."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
