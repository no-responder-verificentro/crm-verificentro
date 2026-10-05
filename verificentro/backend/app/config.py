"""Configuración de la aplicación, leída de variables de entorno.

Nada de credenciales en el código. En desarrollo se leen del archivo .env;
en el servidor, de las variables del sistema.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Por debajo de esto, la firma de los tokens es más débil de lo que recomienda
# el estándar para SHA-256 (RFC 7518).
LARGO_MINIMO_SECRETO = 32


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Aplicación ---
    nombre_app: str = "CRM Verificentro"
    entorno: Literal["desarrollo", "pruebas", "produccion"] = "desarrollo"
    zona_horaria: str = "America/Mexico_City"

    # --- Base de datos ---
    # charset=utf8mb4 no es opcional: los nombres traen acentos.
    db_url: str = "mysql+pymysql://root:@localhost/verificentro?charset=utf8mb4"
    # Imprime cada consulta SQL. Útil para depurar, pero inunda la consola de
    # los jobs, así que va apagado por omisión.
    db_echo: bool = False

    # Cuántas conexiones simultáneas se mantienen abiertas. Los planes
    # gratuitos de base de datos dan muy pocas (Aiven, unas 20 en total), y
    # entre el servidor web y los jobs se agotan rápido. Con 3 + 2 sobra para
    # un verificentro y deja margen.
    db_pool: int = 3
    db_pool_extra: int = 2

    # --- Seguridad ---
    # Generar con:  python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secreto: str = "solo-para-desarrollo-cambiar-esto-antes-de-produccion"
    jwt_algoritmo: str = "HS256"
    jwt_minutos_vigencia: int = 60 * 8      # una jornada de trabajo

    # --- Mensajería ---
    # Por qué canales se generan recordatorios. Un canal apagado aquí no
    # produce filas en la cola, aunque el cliente lo haya autorizado: así no
    # se acumulan mensajes que nunca se van a poder enviar.
    #
    # Mientras no esté el trámite con Meta, esto va solo en correo.
    canales_activos: list[str] = ["correo"]
    # 'consola' imprime los mensajes en pantalla en lugar de enviarlos.
    # Permite construir y probar todo el flujo sin depender de Meta.
    proveedor_whatsapp: Literal["consola", "meta"] = "consola"
    proveedor_correo: Literal["consola", "smtp"] = "consola"

    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = ""
    # Idioma con que se dieron de alta las plantillas en Meta. Tiene que
    # coincidir exactamente o el envío falla con error 132001.
    whatsapp_idioma: str = "es_MX"
    # Secreto de la app, para comprobar la firma de los webhooks.
    whatsapp_app_secret: str = ""

    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_contrasena: str = ""
    correo_remitente: str = "no-responder@verificentro.mx"
    nombre_remitente: str = "Verificentro"

    # Dónde vive el backend de cara al mundo. Es lo que se pone en los enlaces
    # de los correos, así que en producción tiene que ser una dirección
    # alcanzable desde fuera, no localhost.
    url_publica: str = "http://localhost:8000"
    # A dónde llega el cliente al dar clic. Por omisión, la consulta pública.
    url_consulta: str = "http://localhost:5173/consulta"

    # --- Reglas de negocio ---
    dias_por_vencer: int = 15
    hora_envio_recordatorios: int = 9       # 9:00 am
    max_fallos_antes_de_marcar: int = 3

    # --- CORS ---
    origenes_permitidos: list[str] = ["http://localhost:5173"]

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @model_validator(mode="after")
    def _revisar_secreto(self) -> Self:
        """En producción, un secreto corto o el de ejemplo es inaceptable.

        Falla al arrancar y no en silencio: más vale que el servidor no
        levante a que levante con los tokens firmados con una llave pública.
        """
        if not self.es_produccion:
            return self
        if len(self.jwt_secreto) < LARGO_MINIMO_SECRETO or "cambiar" in self.jwt_secreto:
            raise ValueError(
                "JWT_SECRETO es demasiado corto o sigue siendo el de ejemplo. "
                "Genera uno con:\n"
                '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return self


@lru_cache
def obtener_config() -> Config:
    """Se cachea para no releer el .env en cada petición."""
    return Config()
