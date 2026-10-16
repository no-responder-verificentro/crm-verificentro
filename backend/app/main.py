"""Punto de entrada del backend.

    uvicorn app.main:aplicacion --reload

Documentación interactiva en http://localhost:8000/docs
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    auth, calendario, chatbot, citas, clientes, empleados, enlaces, panel,
    recordatorios, reportes, verificaciones,
)
from app.config import obtener_config
from app.webhooks import whatsapp as webhook_whatsapp

config = obtener_config()

aplicacion = FastAPI(
    title=config.nombre_app,
    version="0.1.0",
    description="Sistema de seguimiento y recordatorios de verificación vehicular.",
    docs_url="/docs" if not config.es_produccion else None,
    redoc_url=None,
)

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


@aplicacion.get("/salud", tags=["Sistema"])
def salud() -> dict:
    """Para el monitoreo del servidor.

    Render la consulta para saber si el servicio está vivo. También sirve para
    despertarlo: el plan gratuito lo duerme tras 15 minutos sin uso.
    """
    return {"estado": "ok", "entorno": config.entorno}
