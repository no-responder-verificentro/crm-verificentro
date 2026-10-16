"""Llena la base con datos de demostración.

    python -m jobs.datos_prueba

Sirve para dos cosas: ver las pantallas con contenido mientras se programa, y
tener algo que enseñar en una junta sin capturar veinte clientes a mano.

Los datos se generan **relativos al día de hoy**, eligiendo los dígitos de
placa que producen cada estado del calendario. Así la demostración se ve bien
sin importar en qué mes se corra: siempre hay alguien al corriente, alguien
con el periodo abierto, alguien por vencer y alguien vencido.

Para borrarlos:

    python -m jobs.datos_prueba --borrar
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta

from app.config import obtener_config
from app.database import SesionLocal
from app.dominio.calendario import Estado, estado_de_cumplimiento, ventanas_del_anio
from app.modelos import (
    Cita,
    Cliente,
    EstadoContacto,
    OrigenCita,
    OrigenConsentimiento,
    Resultado,
    Vehiculo,
    VehiculoPlaca,
    Verificacion,
)

HOY = date.today()

LETRAS = ["VZM", "XAL", "GHT", "JLM", "KDW", "PQR", "TYU", "BNM", "LKJ", "ZXC"]

NOMBRES = [
    ("Ana Karen Domínguez Ruiz", "228 100 9584", "akdominguez@correo.com"),
    ("Jorge Ramírez Cruz", "228 145 7712", "jorge.ramirez@correo.com"),
    ("Transportes del Golfo S.A. de C.V.", "229 940 2210", "flotilla@tgolfo.mx"),
    ("Sandra Ortiz Vega", "228 305 7781", None),
    ("Miguel Ángel Tejeda Luna", "228 220 6634", "matejeda@correo.com"),
    ("Guadalupe Ferrer Lima", "228 411 0925", "lupe.ferrer@correo.com"),
    ("Roberto Cárdenas Mota", "228 778 3310", "rcardenas@correo.com"),
    ("Elena Pacheco Rivas", "228 660 1147", "elena.pacheco@correo.com"),
]

AUTOS = [
    ("Nissan", "Sentra Sedán", 2002, "Rojo intenso", "gasolina"),
    ("Volkswagen", "Jetta", 2014, "Gris plata", "gasolina"),
    ("Chevrolet", "Aveo", 2016, "Blanco", "gasolina"),
    ("Toyota", "Yaris", 2021, "Azul", "gasolina"),
    ("Honda", "City", 2017, "Negro", "gasolina"),
    ("Kia", "Rio", 2018, "Rojo", "gasolina"),
    ("Nissan", "NP300", 2019, "Blanco", "diesel"),
    ("Mazda", "Mazda 3", 2020, "Gris", "gasolina"),
    ("Ford", "Figo", 2015, "Plata", "gasolina"),
]


def digitos_para(estado_buscado: Estado, verificado: bool) -> list[int]:
    """Qué últimos dígitos producen ese estado hoy.

    No todos los estados son alcanzables cualquier día del año: si hoy ninguna
    ventana está por cerrar, no hay dígito que dé "por vencer". Por eso se
    devuelve la lista completa y el llamador decide.
    """
    encontrados = []
    for digito in range(10):
        fechas = []
        if verificado:
            for ventana in ventanas_del_anio(digito, HOY.year):
                if ventana.contiene(HOY):
                    fechas = [ventana.inicio + timedelta(days=2)]
        estado, _ = estado_de_cumplimiento(digito, HOY, fechas)
        if estado is estado_buscado:
            encontrados.append(digito)
    return encontrados


def elegir_digito(estado_buscado: Estado, verificado: bool, usados: dict) -> int:
    """El dígito menos repetido de entre los que sirven, para que la
    demostración no salga con ocho autos del mismo grupo."""
    candidatos = digitos_para(estado_buscado, verificado) or list(range(10))
    elegido = min(candidatos, key=lambda d: usados.get(d, 0))
    usados[elegido] = usados.get(elegido, 0) + 1
    return elegido


def placa_con_digito(digito: int, indice: int) -> str:
    """Placa con formato de Veracruz —tres letras, tres números, una letra—
    cuyo último NÚMERO es el que se pide."""
    letras = LETRAS[indice % len(LETRAS)]
    medio = f"{random.randint(0, 9)}{random.randint(0, 9)}{digito}"
    final = chr(ord("A") + (indice % 26))
    return f"{letras}-{medio}-{final}"


def niv(indice: int) -> str:
    """NIV de 17 caracteres, sin I, O ni Q."""
    permitidas = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    random.seed(1000 + indice)
    return "".join(random.choice(permitidas) for _ in range(17))


def borrar(sesion) -> None:
    for modelo in (Cita, Verificacion, VehiculoPlaca, Vehiculo, Cliente):
        borradas = sesion.query(modelo).delete()
        print(f"  {modelo.__tablename__}: {borradas} registros borrados")
    sesion.commit()


def sembrar(sesion) -> None:
    random.seed(42)

    # Un caso por cada estado, para que las pantallas muestren todos los
    # colores del semáforo.
    casos = [
        (Estado.AL_CORRIENTE, True),
        (Estado.POR_VENCER, False),
        (Estado.PERIODO_ABIERTO, False),
        (Estado.VENCIDO, False),
        (Estado.PROGRAMADO, False),
    ]

    creados = 0
    usados: dict[int, int] = {}
    for indice, (nombre, telefono, correo) in enumerate(NOMBRES):
        cliente = Cliente(
            nombre=nombre,
            telefono_e164="+52" + telefono.replace(" ", ""),
            correo=correo,
            consent_whatsapp=True,
            consent_correo=correo is not None,
            consent_fecha=HOY - timedelta(days=random.randint(30, 400)),
            consent_origen=OrigenConsentimiento.MOSTRADOR,
            aviso_privacidad_ver="v1",
        )
        # Uno dado de baja, para ver cómo se ve en pantalla.
        if nombre.startswith("Sandra"):
            cliente.estado_contacto = EstadoContacto.BAJA
            cliente.consent_whatsapp = False
            cliente.consent_correo = False

        sesion.add(cliente)
        sesion.flush()

        # La empresa tiene tres unidades; los demás, una.
        cuantos = 3 if "Transportes" in nombre else 1

        for n in range(cuantos):
            estado_objetivo, ya_verifico = casos[(indice + n) % len(casos)]
            digito = elegir_digito(estado_objetivo, ya_verifico, usados)

            marca, linea, anio, color, combustible = AUTOS[creados % len(AUTOS)]
            vehiculo = Vehiculo(
                cliente_id=cliente.id,
                niv=niv(creados),
                placa=placa_con_digito(digito, creados),
                marca=marca,
                linea=linea,
                modelo_anio=anio,
                color=color,
                combustible=combustible,
                folio_tarjeta=f"E-{3400000 + creados * 137}",
            )
            sesion.add(vehiculo)
            sesion.flush()
            sesion.add(
                VehiculoPlaca(
                    vehiculo_id=vehiculo.id,
                    placa=vehiculo.placa,
                    vigente_desde=HOY - timedelta(days=random.randint(200, 900)),
                )
            )

            # Historial: una verificación del año pasado para todos, y una de
            # este año solo para los que deben aparecer al corriente.
            anterior = ventanas_del_anio(digito, HOY.year - 1)[1]
            sesion.add(
                Verificacion(
                    vehiculo_id=vehiculo.id,
                    fecha=anterior.inicio + timedelta(days=5),
                    periodo=2,
                    resultado=Resultado.APROBADO,
                    holograma="2",
                    folio_certificado=f"VC-{HOY.year - 1}-{creados:05d}",
                    placa_al_verificar=vehiculo.placa,
                )
            )

            if ya_verifico:
                for ventana in ventanas_del_anio(digito, HOY.year):
                    if ventana.contiene(HOY):
                        sesion.add(
                            Verificacion(
                                vehiculo_id=vehiculo.id,
                                fecha=ventana.inicio + timedelta(days=2),
                                periodo=ventana.periodo,
                                resultado=Resultado.APROBADO,
                                holograma="2",
                                folio_certificado=f"VC-{HOY.year}-{creados:05d}",
                                placa_al_verificar=vehiculo.placa,
                            )
                        )

            creados += 1

    # Un rechazo reciente, para ver el índice de rechazo distinto de cero.
    alguno = sesion.query(Vehiculo).first()
    sesion.add(
        Verificacion(
            vehiculo_id=alguno.id,
            fecha=HOY - timedelta(days=2),
            resultado=Resultado.RECHAZADO,
            folio_certificado=f"VC-{HOY.year}-99001",
            placa_al_verificar=alguno.placa,
            observaciones="Fuga en el sistema de escape",
        )
    )

    # Un par de citas para los próximos días hábiles.
    dia = HOY + timedelta(days=2)
    while dia.isoweekday() == 7:
        dia += timedelta(days=1)
    for n, vehiculo in enumerate(sesion.query(Vehiculo).limit(2)):
        sesion.add(
            Cita(
                vehiculo_id=vehiculo.id,
                cliente_id=vehiculo.cliente_id,
                placa_capturada="".join(
                    c for c in vehiculo.placa if c.isalnum()
                ),
                nombre_contacto=vehiculo.cliente.nombre,
                telefono_contacto=vehiculo.cliente.telefono_e164,
                fecha=dia,
                hora_inicio=[__import__("datetime").time(10, 0),
                             __import__("datetime").time(12, 0)][n],
                cupo=1,
                origen=OrigenCita.CHATBOT_WHATSAPP,
            )
        )

    sesion.commit()
    print(f"\n  {len(NOMBRES)} clientes y {creados} vehículos creados.")


def main() -> int:
    config = obtener_config()
    if config.es_produccion:
        print(
            "ENTORNO=produccion. Este script es solo para desarrollo.\n"
            "Si de verdad quieres correrlo, cambia ENTORNO en el archivo .env."
        )
        return 1

    borrar_solo = "--borrar" in sys.argv

    with SesionLocal() as sesion:
        if sesion.query(Cliente).count() and not borrar_solo:
            print(
                "Ya hay clientes en la base. Para reemplazarlos:\n"
                "    python -m jobs.datos_prueba --borrar\n"
                "    python -m jobs.datos_prueba"
            )
            return 1

        print("Borrando datos anteriores…")
        borrar(sesion)

        if borrar_solo:
            print("\nListo. La base quedó sin clientes ni vehículos.")
            print("Tu usuario administrador NO se borró.")
            return 0

        print("\nCreando datos de demostración…")
        sembrar(sesion)

    print("  Entra al sistema y ve a Clientes para verlos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
