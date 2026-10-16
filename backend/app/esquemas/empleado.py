"""Esquemas de entrada y salida.

La regla: el hash de la contraseña NUNCA aparece en un esquema de salida.
Como los endpoints declaran `response_model`, aunque alguien devuelva el
objeto completo por error, FastAPI solo serializa estos campos.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modelos.empleado import Perfil


class Credenciales(BaseModel):
    correo: EmailStr
    contrasena: str = Field(min_length=8, max_length=72)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil: Perfil
    nombre: str


class EmpleadoNuevo(BaseModel):
    nombre: str = Field(min_length=3, max_length=160)
    correo: EmailStr
    contrasena: str = Field(min_length=8, max_length=72)
    perfil: Perfil


class EmpleadoEditado(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=160)
    perfil: Perfil | None = None
    activo: bool | None = None


class EmpleadoPublico(BaseModel):
    """Lo único que sale hacia el frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    correo: EmailStr
    perfil: Perfil
    activo: bool
    ultimo_acceso: datetime | None
