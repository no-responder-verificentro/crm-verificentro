"""Pruebas del chatbot.

Lo que más importa: que reconozca una placa escrita de cualquier forma, que
NUNCA invente una fecha de verificación, y que lo que no sabe quede anotado
para poder mejorarlo.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.dominio.calendario import ventanas_del_anio
from app.dominio.chatbot import buscar_placa, elegir_respuesta, normalizar, puntuar

CHAT = "/api/v1/chatbot"
ANIO = date.today().year


# ------------------------------------------------- motor, sin base de datos -

class TestNormalizar:
    @pytest.mark.parametrize("entrada, esperado", [
        ("¿Cuándo me toca?", "¿cuando me toca?"),
        ("HORARIO", "horario"),
        ("Dirección", "direccion"),
    ])
    def test_quita_acentos_y_baja_a_minusculas(self, entrada, esperado):
        assert normalizar(entrada) == esperado


class TestBuscarPlaca:
    @pytest.mark.parametrize("texto, esperado", [
        ("YUN-047-A", "YUN047A"),
        ("mi placa es YUN-047-A", "YUN047A"),
        ("yun047a", "YUN047A"),
        ("Placa: YUN 047 A", "YUN047A"),
        ("¿cuándo me toca con ABC-123-D?", "ABC123D"),
    ])
    def test_la_encuentra_como_sea_que_la_escriban(self, texto, esperado):
        assert buscar_placa(texto) == esperado

    @pytest.mark.parametrize("texto", [
        "¿cuál es el horario?",
        "hola buenas tardes",
        "",
        "gracias",
    ])
    def test_no_inventa_placas_donde_no_hay(self, texto):
        assert buscar_placa(texto) is None

    def test_no_confunde_un_numero_solo_con_una_placa(self):
        assert buscar_placa("cuesta 500 pesos") is None


class TestPuntuar:
    def test_cuenta_las_palabras_clave_que_coinciden(self):
        assert puntuar("¿cuál es el horario?", "horario,direccion") == 1
        assert puntuar("horario y dirección", "horario,direccion") == 2

    def test_sin_palabras_clave_no_puntua(self):
        assert puntuar("lo que sea", None) == 0

    def test_ignora_acentos(self):
        assert puntuar("¿cuál es la dirección?", "direccion") == 1


class TestElegirRespuesta:
    CATALOGO = [
        (1, "cuando,toca,verificar,periodo"),
        (2, "horario,direccion,ubicacion"),
        (3, "documentos,papeles,requisitos"),
    ]

    def test_elige_la_de_mayor_puntaje(self):
        i = elegir_respuesta("¿cuál es el horario y la dirección?", self.CATALOGO)
        assert i.respuesta_id == 2

    def test_sin_coincidencia_queda_sin_entender(self):
        i = elegir_respuesta("¿venden refacciones?", self.CATALOGO)
        assert i.respuesta_id is None
        assert not i.entendida

    def test_una_placa_sola_ya_es_intencion(self):
        i = elegir_respuesta("YUN-047-A", self.CATALOGO)
        assert i.placa == "YUN047A"
        assert i.entendida


# ------------------------------------------------------ contra la base ---

class TestConversacion:
    def _decir(self, api, texto):
        return api.post(f"{CHAT}/mensaje", json={"texto": texto}).json()

    def test_es_publico(self, api):
        """El chat lo usa el cliente, que no tiene cuenta."""
        assert api.post(f"{CHAT}/mensaje",
                        json={"texto": "hola"}).status_code == 200

    def test_contesta_el_periodo_de_una_placa(self, api):
        r = self._decir(api, "YUN-047-A")
        assert "termina en 7" in r["texto"]
        _, segunda = ventanas_del_anio(7, ANIO)
        assert segunda.etiqueta in r["texto"]
        assert r["entendida"]

    def test_la_placa_dentro_de_una_frase(self, api):
        r = self._decir(api, "hola, ¿cuándo me toca verificar? mi placa es YUN-047-A")
        assert "termina en 7" in r["texto"]

    def test_pregunta_por_la_placa_si_no_la_dieron(self, api):
        r = self._decir(api, "¿cuándo me toca verificar?")
        assert "placa" in r["texto"].lower()
        assert r["tipo"] == "automatica"

    def test_contesta_el_horario_del_catalogo(self, api):
        r = self._decir(api, "¿cuál es su horario?")
        assert "9:00" in r["texto"]
        assert r["entendida"]

    def test_los_documentos(self, api):
        r = self._decir(api, "¿qué papeles necesito llevar?")
        assert "circulación" in r["texto"]

    def test_las_citas_ofrecen_horarios_reales(self, api):
        r = self._decir(api, "quiero agendar una cita")
        # Sale de la agenda de verdad, no de un texto fijo.
        assert ":" in r["texto"]
        assert r["entendida"]

    def test_lo_que_no_sabe_lo_dice_y_ofrece_opciones(self, api):
        r = self._decir(api, "¿venden llantas usadas?")
        assert not r["entendida"]
        assert "no me la sé" in r["texto"]
        assert len(r["sugerencias"]) > 0

    def test_una_placa_sin_numeros_lo_explica(self, api):
        r = self._decir(api, "mi placa es ABC-DEF-G")
        assert "número" in r["texto"] or "numero" in r["texto"]

    def test_un_mensaje_vacio_se_rechaza(self, api):
        assert api.post(f"{CHAT}/mensaje", json={"texto": ""}).status_code == 422


class TestCortesia:
    """Un saludo no es una pregunta sin resolver: si se anotara, el panel se
    llenaría de 'hola' que nadie puede convertir en respuesta."""

    @pytest.mark.parametrize("saludo", ["hola", "Hola", "buenas tardes",
                                        "¡Hola! buenos días", "qué tal"])
    def test_contesta_el_saludo(self, api, saludo, como_atencion):
        r = api.post(f"{CHAT}/mensaje", json={"texto": saludo}).json()
        assert r["entendida"]
        assert "Hola" in r["texto"]
        assert api.get(f"{CHAT}/pendientes", headers=como_atencion).json() == []

    def test_contesta_el_agradecimiento(self, api, como_atencion):
        r = api.post(f"{CHAT}/mensaje", json={"texto": "muchas gracias"}).json()
        assert r["entendida"]
        assert api.get(f"{CHAT}/pendientes", headers=como_atencion).json() == []

    def test_una_pregunta_larga_no_es_saludo(self, api):
        r = api.post(f"{CHAT}/mensaje", json={
            "texto": "hola, quisiera saber si verifican camiones de carga"
        }).json()
        assert not r["entendida"]


class TestPreguntasPendientes:
    def test_lo_que_no_supo_queda_anotado(self, api, como_atencion):
        api.post(f"{CHAT}/mensaje", json={"texto": "¿verifican motocicletas?"})
        pendientes = api.get(f"{CHAT}/pendientes", headers=como_atencion).json()
        assert len(pendientes) == 1
        assert "motocicletas" in pendientes[0]["pregunta"]

    def test_la_misma_pregunta_suma_en_vez_de_duplicarse(self, api, como_atencion):
        for _ in range(3):
            api.post(f"{CHAT}/mensaje", json={"texto": "¿verifican motos?"})
        pendientes = api.get(f"{CHAT}/pendientes", headers=como_atencion).json()
        assert len(pendientes) == 1
        assert pendientes[0]["veces"] == 3

    def test_ordena_por_las_mas_preguntadas(self, api, como_atencion):
        api.post(f"{CHAT}/mensaje", json={"texto": "¿aceptan tarjeta?"})
        for _ in range(4):
            api.post(f"{CHAT}/mensaje", json={"texto": "¿verifican motos?"})
        pendientes = api.get(f"{CHAT}/pendientes", headers=como_atencion).json()
        assert pendientes[0]["veces"] == 4

    def test_guarda_hasta_cuando_se_puede_contestar(self, api, como_atencion):
        """Para WhatsApp: pasadas 24 h ya no se puede responder libremente."""
        api.post(f"{CHAT}/mensaje", json={"texto": "¿tienen servicio a domicilio?"})
        p = api.get(f"{CHAT}/pendientes", headers=como_atencion).json()[0]
        assert p["ventana_expira_en"] is not None


class TestCatalogo:
    def test_trae_las_respuestas_iniciales(self, api, como_atencion):
        filas = api.get(f"{CHAT}/respuestas", headers=como_atencion).json()
        assert len(filas) >= 5

    def test_agregar_una_respuesta_la_hace_contestable(self, api, como_atencion):
        # Antes no la sabe.
        antes = api.post(f"{CHAT}/mensaje",
                         json={"texto": "¿verifican motocicletas?"}).json()
        assert not antes["entendida"]

        api.post(f"{CHAT}/respuestas", headers=como_atencion, json={
            "pregunta": "¿Verifican motocicletas?",
            "respuesta": "Sí, también verificamos motocicletas.",
            "palabras_clave": "motocicletas,motos,moto",
            "orden": 50,
        })

        # Después sí. Y sin pasar por revisión de nadie.
        despues = api.post(f"{CHAT}/mensaje",
                           json={"texto": "¿verifican motocicletas?"}).json()
        assert despues["entendida"]
        assert "motocicletas" in despues["texto"]

    def test_desactivar_la_saca_del_catalogo(self, api, como_atencion):
        filas = api.get(f"{CHAT}/respuestas", headers=como_atencion).json()
        horario = next(f for f in filas if "horario" in f["pregunta"].lower())
        api.delete(f"{CHAT}/respuestas/{horario['id']}", headers=como_atencion)
        activas = api.get(f"{CHAT}/respuestas", headers=como_atencion).json()
        assert horario["id"] not in [f["id"] for f in activas]

    def test_el_tecnico_no_edita_el_catalogo(self, api, como_tecnico):
        r = api.post(f"{CHAT}/respuestas", headers=como_tecnico, json={
            "pregunta": "¿Algo?", "respuesta": "Algo.",
        })
        assert r.status_code == 403

    def test_atencion_si_puede(self, api, como_atencion):
        r = api.post(f"{CHAT}/respuestas", headers=como_atencion, json={
            "pregunta": "¿Aceptan pago con tarjeta?",
            "respuesta": "Sí, aceptamos tarjeta de débito y crédito.",
            "palabras_clave": "tarjeta,pago,pagar",
        })
        assert r.status_code == 201
