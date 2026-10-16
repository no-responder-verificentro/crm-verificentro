"""Chatbot: conversación pública y administración del catálogo."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.dependencias import Sesion, Usuario, chatbot as permiso_chatbot, consulta
from app.esquemas.chatbot import (
    MensajeEntrante,
    MensajeSaliente,
    PendientePublico,
    RespuestaEditada,
    RespuestaNueva,
    RespuestaPublica,
)
from app.modelos.chatbot import ChatbotPendiente, ChatbotRespuesta
from app.servicios import chatbot as servicio

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


# ------------------------------------------------------------- público ---

@router.post("/mensaje", response_model=MensajeSaliente)
def conversar(datos: MensajeEntrante, sesion: Sesion) -> MensajeSaliente:
    """PÚBLICO: es el chat que ve el cliente en la página.

    No pide token ni expone datos personales: solo aplica el calendario a una
    placa que quien pregunta ya conoce, y contesta del catálogo.
    """
    r = servicio.conversar(sesion, datos.texto, datos.canal)
    return MensajeSaliente(texto=r.texto, tipo=r.tipo,
                           entendida=r.entendida, sugerencias=r.sugerencias)


@router.get("/sugerencias", response_model=list[str])
def sugerencias(sesion: Sesion) -> list[str]:
    """Las preguntas que se ofrecen como botones al abrir el chat."""
    return servicio.sugerencias(sesion)


# ------------------------------------------------------ administración ---

@router.get("/respuestas", response_model=list[RespuestaPublica],
            dependencies=[Depends(consulta)])
def listar(sesion: Sesion, incluir_inactivas: bool = False):
    consulta_sql = select(ChatbotRespuesta)
    if not incluir_inactivas:
        consulta_sql = consulta_sql.where(ChatbotRespuesta.activa.is_(True))
    return list(sesion.scalars(consulta_sql.order_by(ChatbotRespuesta.orden)))


@router.post("/respuestas", response_model=RespuestaPublica,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(permiso_chatbot)])
def crear(datos: RespuestaNueva, sesion: Sesion, usuario: Usuario):
    """Editar el catálogo es inmediato y NO pasa por revisión de Meta."""
    respuesta = ChatbotRespuesta(**datos.model_dump(), actualizado_por=usuario.id)
    sesion.add(respuesta)
    sesion.commit()
    sesion.refresh(respuesta)
    return respuesta


def _obtener(sesion, respuesta_id: int) -> ChatbotRespuesta:
    respuesta = sesion.get(ChatbotRespuesta, respuesta_id)
    if respuesta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Respuesta no encontrada.")
    return respuesta


@router.patch("/respuestas/{respuesta_id}", response_model=RespuestaPublica,
              dependencies=[Depends(permiso_chatbot)])
def editar(respuesta_id: int, datos: RespuestaEditada, sesion: Sesion,
           usuario: Usuario):
    respuesta = _obtener(sesion, respuesta_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(respuesta, campo, valor)
    respuesta.actualizado_por = usuario.id
    sesion.commit()
    sesion.refresh(respuesta)
    return respuesta


@router.delete("/respuestas/{respuesta_id}", response_model=RespuestaPublica,
               dependencies=[Depends(permiso_chatbot)])
def desactivar(respuesta_id: int, sesion: Sesion):
    """Se desactiva, no se borra: las preguntas pendientes pueden apuntarle."""
    respuesta = _obtener(sesion, respuesta_id)
    respuesta.activa = False
    sesion.commit()
    sesion.refresh(respuesta)
    return respuesta


@router.get("/pendientes", response_model=list[PendientePublico],
            dependencies=[Depends(consulta)])
def pendientes(sesion: Sesion, limite: int = Query(default=50, ge=1, le=200)):
    """Lo que el bot no supo contestar, lo más preguntado primero."""
    return list(
        sesion.scalars(
            select(ChatbotPendiente)
            .where(ChatbotPendiente.resuelta.is_(False))
            .order_by(ChatbotPendiente.veces.desc(),
                      ChatbotPendiente.ultima_vez.desc())
            .limit(limite)
        )
    )


@router.post("/pendientes/{pendiente_id}/resolver",
             response_model=PendientePublico,
             dependencies=[Depends(permiso_chatbot)])
def resolver(pendiente_id: int, sesion: Sesion,
             respuesta_id: int | None = Query(default=None)):
    """Marca una pregunta como atendida, opcionalmente ligándola a la
    respuesta del catálogo que se creó para ella."""
    pendiente = sesion.get(ChatbotPendiente, pendiente_id)
    if pendiente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pendiente.resuelta = True
    pendiente.respuesta_id = respuesta_id
    sesion.commit()
    sesion.refresh(pendiente)
    return pendiente
