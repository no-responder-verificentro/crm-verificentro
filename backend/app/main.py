"""Punto de entrada del backend.

    uvicorn app.main:aplicacion --reload

Documentación interactiva en http://localhost:8000/docs
"""

import logging
import traceback

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    auth, calendario, chatbot, citas, clientes, empleados, enlaces, panel,
    recordatorios, reportes, verificaciones,
)
from app.config import obtener_config
from app.webhooks import mailjet as webhook_mailjet
from app.webhooks import whatsapp as webhook_whatsapp

config = obtener_config()
registro = logging.getLogger("verificentro")

aplicacion = FastAPI(
    title=config.nombre_app,
    version="0.1.0",
    description="Sistema de seguimiento y recordatorios de verificación vehicular.",
    docs_url="/docs" if not config.es_produccion else None,
    redoc_url=None,
)


# OJO CON EL ORDEN. Las capas se aplican al revés de como se agregan: la
# última que se agrega queda por fuera. Este middleware va PRIMERO para que
# CORS quede por fuera de él y alcance a ponerle sus cabeceras a la respuesta.
#
# Es lo que arregla el error más engañoso de todo el despliegue: si el
# servidor truena con un error no capturado, la respuesta 500 la arma Starlette
# por encima de CORS, sale SIN la cabecera Access-Control-Allow-Origin, y el
# navegador lo reporta como si fuera un problema de CORS. Uno se pasa la tarde
# revisando ORIGENES_PERMITIDOS cuando lo que falla es la base de datos.
#
# Capturándolo aquí adentro, la respuesta sí pasa por CORS y el navegador
# muestra el error de verdad.
@aplicacion.middleware("http")
async def errores_con_cors(request: Request, siguiente):
    try:
        return await siguiente(request)
    except Exception:
        # El rastro completo va a la bitácora del servidor —en Render, a Logs—
        # porque es donde hay que leerlo; al navegador no se le manda.
        registro.exception("Error no capturado en %s %s",
                           request.method, request.url.path)
        detalle = "El servidor tuvo un problema. Revisa la bitácora."
        if not config.es_produccion:
            detalle = traceback.format_exc().strip().splitlines()[-1]
        return JSONResponse(status_code=500, content={"detail": detalle})


aplicacion.add_middleware(
    CORSMiddleware,
    allow_origins=config.origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

v1 = APIRouter(prefix="/api/v1")
v1.include_router(auth.router)
v1.include_router(empleados.router)
v1.include_router(calendario.router)
v1.include_router(clientes.router)
v1.include_router(clientes.vehiculos)
v1.include_router(verificaciones.router)
v1.include_router(citas.router)
v1.include_router(recordatorios.router)
v1.include_router(panel.router)
v1.include_router(reportes.router)
v1.include_router(chatbot.router)

aplicacion.include_router(v1)
# Fuera de /api: son URLs que abre la gente desde su correo.
aplicacion.include_router(enlaces.router)
# Webhooks: los llama Meta, no la aplicación.
aplicacion.include_router(webhook_whatsapp.router)
# Mailjet avisa aquí qué pasó con cada correo después de aceptarlo.
aplicacion.include_router(webhook_mailjet.router)


@aplicacion.get("/salud", tags=["Sistema"])
def salud() -> dict:
    """Para el monitoreo del servidor.

    Render la consulta para saber si el servicio está vivo. También sirve para
    despertarlo: el plan gratuito lo duerme tras 15 minutos sin uso.
    """
    return {"estado": "ok", "entorno": config.entorno}
