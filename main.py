"""
=============================================================================
MAIN.PY — La API (FastAPI)
=============================================================================
Este es el archivo principal. Define todos los ENDPOINTS de la API.

¿Qué es un endpoint?
Es una URL que hace algo. Ejemplo:
  POST /auth/register → registra un usuario nuevo
  GET  /habits        → devuelve los hábitos del usuario

¿Qué es FastAPI?
Un framework de Python para crear APIs. Es rápido, moderno, y genera
documentación automática (Swagger UI) que puedes ver en /docs.

¿Qué es un token JWT?
Cuando haces login, la API te da un "token" (una cadena larga de texto).
Es como un pase VIP: lo incluyes en cada petición para demostrar que
estás autenticado. El token expira después de un tiempo (aquí: 7 días).
=============================================================================
"""

import os
import secrets
import string
from datetime import datetime, date, timedelta, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

import jwt  # PyJWT — para crear y verificar tokens
from passlib.context import CryptContext  # Para hashear contraseñas

from database import init_db, get_db, User, Habit, Routine, Reminder, HabitLog
from models import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    HabitCreate, HabitResponse,
    RoutineStepCreate, RoutineStepResponse,
    ReminderCreate, ReminderResponse,
    HabitLogCreate, HabitLogResponse, DaySummary,
    TelegramLinkCode,
)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

# SECRET_KEY: se usa para firmar los tokens JWT.
# En producción DEBE ser una variable de entorno, nunca hardcodeada.
# os.environ.get() intenta leerla del entorno; si no existe, usa el fallback.
SECRET_KEY = os.environ.get("SECRET_KEY", "nexotime-dev-secret-change-me")

JWT_ALGORITHM = "HS256"          # Algoritmo de encriptación del token
JWT_EXPIRATION_DAYS = 7          # El token expira en 7 días

# Hasher de contraseñas: bcrypt es el estándar de la industria.
# Convierte "mipassword123" en algo como "$2b$12$LJ3m5..." irreversible.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de seguridad: le dice a FastAPI que los endpoints protegidos
# necesitan un header "Authorization: Bearer <token>"
security = HTTPBearer()


# ─────────────────────────────────────────────────────────────────────────────
# ARRANQUE DE LA APP
# ─────────────────────────────────────────────────────────────────────────────
# lifespan = lo que pasa cuando la app arranca y cuando se apaga.
# Aquí inicializamos la base de datos al arrancar.

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Crea las tablas si no existen
    print("🚀 NexoTime API arrancada")
    yield      # La app corre aquí
    print("👋 NexoTime API apagada")

app = FastAPI(
    title="NexoTime API",
    description="Backend para el sistema de productividad NexoTime",
    version="2.0.0",
    lifespan=lifespan,
)

# ─── CORS ───
# CORS = Cross-Origin Resource Sharing
# Sin esto, tu web (en Vercel) NO puede hablar con la API (en Railway)
# porque están en dominios distintos. El navegador lo bloquea por seguridad.
# allow_origins=["*"] permite CUALQUIER dominio. En producción lo limitarías.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES (Auth)
# ─────────────────────────────────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    """Crea un token JWT con el id del usuario y fecha de expiración"""
    payload = {
        "sub": str(user_id),  # "sub" = subject (quién es)
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Extrae el usuario del token JWT.
    FastAPI llama a esta función automáticamente en los endpoints que la usan.
    Si el token es inválido o el usuario no existe, lanza un error 401.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado. Haz login de nuevo.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


def user_to_response(user: User) -> UserResponse:
    """Convierte un objeto User de la BD a la respuesta de la API"""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        telegram_linked=user.telegram_id is not None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: AUTH (Registro y Login)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Registra un usuario nuevo y devuelve un token"""

    # Verificar que el email no existe ya
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Ese email ya está registrado")

    # Validar contraseña mínima
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    # Crear usuario con contraseña hasheada
    user = User(
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        name=data.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)  # Recarga para obtener el id autogenerado

    # Devolver token + datos del usuario
    return TokenResponse(
        access_token=create_token(user.id),
        user=user_to_response(user),
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Login: verifica credenciales y devuelve un token"""

    user = db.query(User).filter(User.email == data.email).first()

    # Verificamos email Y contraseña. Si alguno falla, mismo mensaje genérico.
    # ¿Por qué? Para no revelar si el email existe o no (seguridad).
    if not user or not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    return TokenResponse(
        access_token=create_token(user.id),
        user=user_to_response(user),
    )


@app.get("/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Devuelve los datos del usuario autenticado"""
    return user_to_response(user)


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: HABITS (Configurar hábitos)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/habits", response_model=list[HabitResponse])
def list_habits(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Devuelve todos los hábitos del usuario"""
    return db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()


@app.post("/habits", response_model=HabitResponse)
def create_habit(data: HabitCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Crea un hábito nuevo"""
    habit = Habit(user_id=user.id, name=data.name, icon=data.icon)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


@app.delete("/habits/{habit_id}")
def delete_habit(habit_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Desactiva un hábito (soft delete)"""
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Hábito no encontrado")
    habit.active = False
    db.commit()
    return {"message": "Hábito eliminado"}


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: ROUTINES (Configurar rutinas)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/routines/{routine_type}", response_model=list[RoutineStepResponse])
def list_routine(routine_type: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Devuelve los pasos de una rutina (morning o night)"""
    if routine_type not in ("morning", "night"):
        raise HTTPException(status_code=400, detail="Tipo debe ser 'morning' o 'night'")
    return (
        db.query(Routine)
        .filter(Routine.user_id == user.id, Routine.type == routine_type)
        .order_by(Routine.step_order)
        .all()
    )


@app.post("/routines", response_model=RoutineStepResponse)
def create_routine_step(data: RoutineStepCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Añade un paso a una rutina"""
    if data.type not in ("morning", "night"):
        raise HTTPException(status_code=400, detail="Tipo debe ser 'morning' o 'night'")
    step = Routine(user_id=user.id, type=data.type, step_order=data.step_order, description=data.description)
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@app.put("/routines/bulk/{routine_type}", response_model=list[RoutineStepResponse])
def replace_routine(routine_type: str, steps: list[RoutineStepCreate], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reemplaza TODOS los pasos de una rutina de golpe"""
    if routine_type not in ("morning", "night"):
        raise HTTPException(status_code=400, detail="Tipo debe ser 'morning' o 'night'")

    # Borrar pasos actuales
    db.query(Routine).filter(Routine.user_id == user.id, Routine.type == routine_type).delete()

    # Crear los nuevos
    new_steps = []
    for i, s in enumerate(steps, 1):
        step = Routine(user_id=user.id, type=routine_type, step_order=i, description=s.description)
        db.add(step)
        new_steps.append(step)

    db.commit()
    for s in new_steps:
        db.refresh(s)
    return new_steps


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: REMINDERS (Horarios de notificación)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/reminders", response_model=list[ReminderResponse])
def list_reminders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Reminder).filter(Reminder.user_id == user.id).all()


@app.post("/reminders", response_model=ReminderResponse)
def create_reminder(data: ReminderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.type not in ("morning", "habits", "night", "summary"):
        raise HTTPException(status_code=400, detail="Tipo inválido")
    reminder = Reminder(user_id=user.id, type=data.type, time=data.time)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@app.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user.id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado")
    db.delete(reminder)
    db.commit()
    return {"message": "Recordatorio eliminado"}


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: HABIT LOGS (Registro diario)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/logs", response_model=HabitLogResponse)
def log_habit(data: HabitLogCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Marca un hábito como completado/no completado en una fecha"""

    # Verificar que el hábito existe y pertenece al usuario
    habit = db.query(Habit).filter(Habit.id == data.habit_id, Habit.user_id == user.id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Hábito no encontrado")

    # Buscar si ya hay un registro para este hábito en esta fecha
    existing = db.query(HabitLog).filter(
        HabitLog.user_id == user.id,
        HabitLog.habit_id == data.habit_id,
        HabitLog.date == data.date,
    ).first()

    if existing:
        # Si ya existe, actualizar
        existing.completed = data.completed
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Si no existe, crear
        log = HabitLog(user_id=user.id, habit_id=data.habit_id, date=data.date, completed=data.completed)
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


@app.get("/logs/{log_date}", response_model=DaySummary)
def get_day_summary(log_date: date, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Devuelve el resumen de un día"""
    habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()
    logs = db.query(HabitLog).filter(
        HabitLog.user_id == user.id,
        HabitLog.date == log_date,
    ).all()

    completed = sum(1 for l in logs if l.completed)
    total = len(habits)

    return DaySummary(
        date=log_date,
        total_habits=total,
        completed=completed,
        percentage=round((completed / total * 100) if total > 0 else 0, 1),
        habits=logs,
    )


@app.get("/logs/week/{log_date}", response_model=list[DaySummary])
def get_week_summary(log_date: date, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Devuelve el resumen de los últimos 7 días"""
    summaries = []
    for i in range(7):
        day = log_date - timedelta(days=i)
        summary = get_day_summary(day, user, db)
        summaries.append(summary)
    return summaries


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: TELEGRAM LINKING
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/telegram/generate-code", response_model=TelegramLinkCode)
def generate_telegram_link_code(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Genera un código de 6 caracteres para vincular Telegram.
    El usuario copia este código y lo envía al bot con /vincular CODIGO
    """
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    user.telegram_link_code = code
    db.commit()
    return TelegramLinkCode(link_code=code)


@app.post("/telegram/link")
def link_telegram(telegram_id: str, link_code: str, db: Session = Depends(get_db)):
    """
    El bot llama a este endpoint cuando un usuario envía /vincular CODIGO.
    Busca el usuario con ese código y le asigna el telegram_id.
    """
    user = db.query(User).filter(User.telegram_link_code == link_code).first()
    if not user:
        raise HTTPException(status_code=404, detail="Código inválido o expirado")

    user.telegram_id = telegram_id
    user.telegram_link_code = None  # Limpiar el código usado
    db.commit()
    return {"message": f"Telegram vinculado correctamente para {user.name}"}


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: TELEGRAM BOT (El bot usa estos para obtener datos por telegram_id)
# ─────────────────────────────────────────────────────────────────────────────
# Estos endpoints NO usan JWT. Usan el telegram_id directamente.
# Son "internos" — solo el bot los llama.

def _get_user_by_telegram(telegram_id: str, db: Session) -> User:
    """Busca un usuario por su telegram_id. Lanza 404 si no existe."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Cuenta no vinculada")
    return user


@app.get("/telegram/user/{telegram_id}")
def get_telegram_user(telegram_id: str, db: Session = Depends(get_db)):
    """El bot consulta si un telegram_id tiene cuenta vinculada"""
    user = _get_user_by_telegram(telegram_id, db)
    return {"id": user.id, "name": user.name, "email": user.email}


@app.get("/telegram/habits/{telegram_id}")
def get_telegram_habits(telegram_id: str, db: Session = Depends(get_db)):
    """El bot pide los hábitos de un usuario por su telegram_id"""
    user = _get_user_by_telegram(telegram_id, db)
    habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()
    return [{"id": h.id, "name": h.name, "icon": h.icon} for h in habits]


@app.get("/telegram/logs/{telegram_id}/{log_date}")
def get_telegram_logs(telegram_id: str, log_date: date, db: Session = Depends(get_db)):
    """El bot pide los logs de un día por telegram_id"""
    user = _get_user_by_telegram(telegram_id, db)
    logs = db.query(HabitLog).filter(
        HabitLog.user_id == user.id,
        HabitLog.date == log_date,
    ).all()
    return [{"id": l.id, "habit_id": l.habit_id, "completed": l.completed} for l in logs]


@app.post("/telegram/log-habit/{telegram_id}")
def telegram_log_habit(telegram_id: str, data: HabitLogCreate, db: Session = Depends(get_db)):
    """El bot marca un hábito como completado/no completado"""
    user = _get_user_by_telegram(telegram_id, db)

    # Verificar que el hábito pertenece al usuario
    habit = db.query(Habit).filter(Habit.id == data.habit_id, Habit.user_id == user.id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Hábito no encontrado")

    # Buscar log existente o crear nuevo
    existing = db.query(HabitLog).filter(
        HabitLog.user_id == user.id,
        HabitLog.habit_id == data.habit_id,
        HabitLog.date == data.date,
    ).first()

    if existing:
        existing.completed = data.completed
    else:
        log = HabitLog(user_id=user.id, habit_id=data.habit_id, date=data.date, completed=data.completed)
        db.add(log)

    db.commit()
    return {"message": "ok"}


@app.get("/telegram/routine/{telegram_id}/{routine_type}")
def get_telegram_routine(telegram_id: str, routine_type: str, db: Session = Depends(get_db)):
    """El bot pide la rutina de mañana o noche por telegram_id"""
    user = _get_user_by_telegram(telegram_id, db)
    steps = (
        db.query(Routine)
        .filter(Routine.user_id == user.id, Routine.type == routine_type)
        .order_by(Routine.step_order)
        .all()
    )
    return [{"step_order": s.step_order, "description": s.description} for s in steps]


@app.get("/telegram/summary/{telegram_id}/{log_date}")
def get_telegram_summary(telegram_id: str, log_date: date, db: Session = Depends(get_db)):
    """El bot pide el resumen del día por telegram_id"""
    user = _get_user_by_telegram(telegram_id, db)

    habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()
    logs = db.query(HabitLog).filter(
        HabitLog.user_id == user.id,
        HabitLog.date == log_date,
    ).all()

    logs_map = {l.habit_id: l.completed for l in logs}
    total = len(habits)
    completed = sum(1 for h in habits if logs_map.get(h.id, False))

    habits_detail = [
        {"name": h.name, "completed": logs_map.get(h.id, False)}
        for h in habits
    ]

    return {
        "date": log_date.isoformat(),
        "total_habits": total,
        "completed": completed,
        "percentage": round((completed / total * 100) if total > 0 else 0, 1),
        "habits_detail": habits_detail,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
# Un endpoint simple que devuelve "ok". Útil para:
# - Railway sepa que la app está viva
# - Tú puedas verificar que la API funciona

@app.get("/")
def health_check():
    return {"status": "ok", "app": "NexoTime API", "version": "2.0.0"}


# ─────────────────────────────────────────────────────────────────────────────
# ARRANCAR
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
