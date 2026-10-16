"""
Pruebas del calendario de verificación.

Estos casos son el contrato del sistema: si algún día cambia el Artículo 9 o
alguien "optimiza" la función, estas pruebas avisan antes de que 5,000
clientes reciban el recordatorio en el mes equivocado.
"""

from datetime import date

import pytest

from app.dominio.calendario import (
    DigitoInvalido,
    Estado,
    PlacaSinDigito,
    estado_de_cumplimiento,
    fechas_de_aviso,
    normalizar_placa,
    proxima_ventana,
    ultima_ventana_cerrada,
    ultimo_digito,
    ventana_vigente,
    ventanas_del_anio,
)


# ---------------------------------------------------------------- placas ---

class TestUltimoDigito:
    @pytest.mark.parametrize("placa, esperado", [
        ("YUN-047-A", 7),        # formato real de Veracruz: termina en letra
        ("YUN047A", 7),
        ("yun047a", 7),          # minúsculas
        ("YUN 047 A", 7),        # con espacios
        ("VZM-317-C", 7),
        ("2019/YUN047A", 7),     # como viene impreso en la tarjeta
        ("ABC-123-D", 3),
        ("XYZ-450-B", 0),        # termina en 0, no debe confundirse con vacío
        ("A1", 1),
    ])
    def test_extrae_el_ultimo_numero_ignorando_letras(self, placa, esperado):
        assert ultimo_digito(placa) == esperado

    @pytest.mark.parametrize("placa", ["ABC-DEF", "", "   ", "-----"])
    def test_placa_sin_numeros_truena_en_lugar_de_asumir_cero(self, placa):
        # Asumir 0 mandaría el vehículo al grupo 9-0 en silencio.
        with pytest.raises(PlacaSinDigito):
            ultimo_digito(placa)

    def test_normalizar_quita_separadores(self):
        assert normalizar_placa("yun-047 a") == "YUN047A"


# --------------------------------------------------------------- ventanas ---

class TestVentanas:
    def test_digito_7_cae_en_feb_mar_y_ago_sep(self):
        v1, v2 = ventanas_del_anio(7, 2026)
        assert (v1.inicio, v1.fin) == (date(2026, 2, 1), date(2026, 3, 31))
        assert (v2.inicio, v2.fin) == (date(2026, 8, 1), date(2026, 9, 30))

    def test_digito_0_comparte_periodo_con_el_9(self):
        assert ventanas_del_anio(0, 2026) == ventanas_del_anio(9, 2026)

    def test_pares_de_digitos_comparten_calendario(self):
        for a, b in [(5, 6), (7, 8), (3, 4), (1, 2), (9, 0)]:
            assert ventanas_del_anio(a, 2026) == ventanas_del_anio(b, 2026)

    def test_los_diez_digitos_estan_cubiertos(self):
        for d in range(10):
            assert len(ventanas_del_anio(d, 2026)) == 2

    def test_febrero_en_anio_bisiesto_cierra_el_29(self):
        v1, _ = ventanas_del_anio(5, 2028)   # 2028 es bisiesto
        assert v1.fin == date(2028, 2, 29)

    def test_febrero_en_anio_normal_cierra_el_28(self):
        v1, _ = ventanas_del_anio(5, 2026)
        assert v1.fin == date(2026, 2, 28)

    def test_diciembre_cierra_el_31(self):
        _, v2 = ventanas_del_anio(9, 2026)
        assert v2.fin == date(2026, 12, 31)

    @pytest.mark.parametrize("digito", [10, -1, 99, "7", None, True])
    def test_digito_invalido_truena(self, digito):
        with pytest.raises(DigitoInvalido):
            ventanas_del_anio(digito, 2026)

    def test_etiqueta_legible_para_pantalla(self):
        _, v2 = ventanas_del_anio(7, 2026)
        assert v2.etiqueta == "Agosto – Septiembre"


class TestVentanaVigente:
    def test_dentro_de_la_ventana(self):
        v = ventana_vigente(7, date(2026, 8, 23))
        assert v is not None and v.periodo == 2

    def test_primer_dia_cuenta_como_dentro(self):
        assert ventana_vigente(7, date(2026, 8, 1)) is not None

    def test_ultimo_dia_cuenta_como_dentro(self):
        assert ventana_vigente(7, date(2026, 9, 30)) is not None

    def test_un_dia_despues_ya_esta_fuera(self):
        assert ventana_vigente(7, date(2026, 10, 1)) is None

    def test_fuera_de_ambas_ventanas(self):
        assert ventana_vigente(7, date(2026, 6, 15)) is None


class TestNavegacionEntreVentanas:
    def test_proxima_ventana_cruza_al_anio_siguiente(self):
        # Dígito 9: su última ventana del año cierra el 31 de diciembre.
        v = proxima_ventana(9, date(2026, 12, 15))
        assert v.inicio == date(2027, 5, 1)

    def test_proxima_ventana_no_devuelve_la_actual(self):
        v = proxima_ventana(7, date(2026, 8, 23))
        assert v.inicio == date(2027, 2, 1)

    def test_ultima_cerrada_puede_ser_del_anio_pasado(self):
        v = ultima_ventana_cerrada(7, date(2027, 1, 10))
        assert v is not None and v.fin == date(2026, 9, 30)


# ------------------------------------------------------------ cumplimiento --

HOY = date(2026, 8, 23)


class TestEstadoDeCumplimiento:
    def test_por_vencer_cuando_quedan_pocos_dias(self):
        # Dígito 6: ventana jul-ago, cierra el 31 de agosto -> 8 días.
        estado, v = estado_de_cumplimiento(6, HOY)
        assert estado is Estado.POR_VENCER
        assert v.fin == date(2026, 8, 31)

    def test_periodo_abierto_cuando_todavia_hay_tiempo(self):
        # Dígito 7: ventana ago-sep, cierra el 30 de septiembre -> 38 días.
        estado, _ = estado_de_cumplimiento(7, HOY)
        assert estado is Estado.PERIODO_ABIERTO

    def test_al_corriente_si_ya_verifico_dentro_de_la_ventana(self):
        estado, _ = estado_de_cumplimiento(7, HOY, [date(2026, 8, 5)])
        assert estado is Estado.AL_CORRIENTE

    def test_verificacion_de_otra_ventana_no_cuenta(self):
        # Verificó en su primer periodo (feb-mar), pero le toca de nuevo.
        estado, _ = estado_de_cumplimiento(7, HOY, [date(2026, 2, 10)])
        assert estado is Estado.PERIODO_ABIERTO

    def test_vencido_si_se_le_paso_la_ventana_anterior(self):
        # Dígito 2: ventana abr-may cerró y no verificó.
        estado, v = estado_de_cumplimiento(2, HOY)
        assert estado is Estado.VENCIDO
        assert v.fin == date(2026, 5, 31)

    def test_programado_si_cumplio_y_su_proxima_ventana_no_abre(self):
        # Dígito 3: ventana mar-abr cumplida, la de sep-oct no ha abierto.
        estado, v = estado_de_cumplimiento(3, HOY, [date(2026, 4, 12)])
        assert estado is Estado.PROGRAMADO
        assert v.inicio == date(2026, 9, 1)

    def test_una_verificacion_rechazada_no_se_pasa_en_la_lista(self):
        # El llamador solo manda aprobadas; con lista vacía sigue debiendo.
        estado, _ = estado_de_cumplimiento(7, HOY, [])
        assert estado is Estado.PERIODO_ABIERTO

    def test_el_umbral_de_por_vencer_es_configurable(self):
        estado, _ = estado_de_cumplimiento(7, HOY, dias_por_vencer=40)
        assert estado is Estado.POR_VENCER

    def test_verificar_el_ultimo_dia_cuenta(self):
        estado, _ = estado_de_cumplimiento(6, date(2026, 8, 31),
                                           [date(2026, 8, 31)])
        assert estado is Estado.AL_CORRIENTE


# ---------------------------------------------------------------- avisos ---

class TestFechasDeAviso:
    def test_genera_cinco_avisos_en_orden(self):
        _, v = ventanas_del_anio(7, 2026)
        avisos = fechas_de_aviso(v)
        assert [a.clave for a in avisos] == [
            "aviso_1", "aviso_2", "aviso_3", "aviso_4", "seguimiento"
        ]
        fechas = [a.fecha for a in avisos]
        assert fechas == sorted(fechas)

    def test_el_primer_aviso_sale_antes_de_que_abra(self):
        _, v = ventanas_del_anio(7, 2026)
        assert fechas_de_aviso(v)[0].fecha == date(2026, 7, 17)

    def test_el_seguimiento_sale_despues_del_cierre(self):
        _, v = ventanas_del_anio(7, 2026)
        assert fechas_de_aviso(v)[-1].fecha == date(2026, 10, 1)

    def test_el_aviso_de_cierre_sale_cinco_dias_antes(self):
        _, v = ventanas_del_anio(7, 2026)
        assert fechas_de_aviso(v)[3].fecha == date(2026, 9, 25)
