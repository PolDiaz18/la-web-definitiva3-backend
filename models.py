"""
=============================================================================
MODELS.PY — Los esquemas de datos (Pydantic)
=============================================================================
¿Qué es esto?
Cuando alguien manda datos a la API (ej: "quiero registrarme con email X"),
necesitamos VALIDAR esos datos antes de hacer nada:
- ¿Tiene email? ¿Es un email válido?
- ¿Tiene contraseña? ¿Es lo bastante larga?

Pydantic hace esa validación automáticamente. Defines la "forma" que deben
tener los datos, y si no cumplen, Pydantic rechaza la petición con un error
claro antes de que llegue a la base de datos.

¿Por qué separar esto de database.py?
- database.py define cómo se GUARDAN los datos (tablas SQL)
- models.py define cómo ENTRAN y SALEN los datos (JSON de la API)
Son dos cosas distintas. A veces no quieres exponer todos los campos
(ej: nunca devuelves el password_hash al usuario).
=============================================================================
"""

from pydantic import BaseModel, EmailStr
from datetime import date
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# AUTH (Registro y Login)
# ─────────────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """Lo que el usuario manda para registrarse"""
    email: EmailStr        # Pydantic valida que sea un email real
    password: str          # Mínimo lo validamos en el endpoint
    name: str

class UserLogin(BaseModel):
    """Lo que el usuario manda para hacer login"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Lo que la API devuelve sobre un usuario (NUNCA el password)"""
    id: int
    email: str
    name: str
    telegram_linked: bool  # true si tiene telegram_id

    # Esto le dice a Pydantic que puede leer datos de objetos SQLAlchemy
    # (por defecto solo lee diccionarios)
    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    """Lo que la API devuelve después de un login exitoso"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─────────────────────────────────────────────────────────────────────────────
# HABITS (Configuración de hábitos)
# ─────────────────────────────────────────────────────────────────────────────

class HabitCreate(BaseModel):
    """Para crear un hábito nuevo"""
    name: str
    icon: str = "✅"

class HabitResponse(BaseModel):
    """Un hábito como lo devuelve la API"""
    id: int
    name: str
    icon: str
    active: bool
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTINES (Pasos de rutinas)
# ─────────────────────────────────────────────────────────────────────────────

class RoutineStepCreate(BaseModel):
    """Para crear un paso de rutina"""
    type: str           # "morning" o "night"
    step_order: int     # 1, 2, 3...
    description: str    # "Ducha fría"

class RoutineStepResponse(BaseModel):
    id: int
    type: str
    step_order: int
    description: str
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# REMINDERS (Horarios de notificación)
# ─────────────────────────────────────────────────────────────────────────────

class ReminderCreate(BaseModel):
    type: str           # "morning", "habits", "night", "summary"
    time: str           # "07:00"

class ReminderResponse(BaseModel):
    id: int
    type: str
    time: str
    active: bool
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# HABIT LOGS (Registro diario)
# ─────────────────────────────────────────────────────────────────────────────

class HabitLogCreate(BaseModel):
    """Marcar un hábito como hecho/no hecho"""
    habit_id: int
    date: date
    completed: bool

class HabitLogResponse(BaseModel):
    id: int
    habit_id: int
    date: date
    completed: bool
    model_config = {"from_attributes": True}

class DaySummary(BaseModel):
    """Resumen de un día: qué hábitos se completaron"""
    date: date
    total_habits: int
    completed: int
    percentage: float
    habits: list[HabitLogResponse]


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM LINKING
# ─────────────────────────────────────────────────────────────────────────────

class TelegramLinkCode(BaseModel):
    """Código para vincular Telegram"""
    link_code: str
