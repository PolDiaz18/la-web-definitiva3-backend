"""
=============================================================================
DATABASE.PY — La base de datos
=============================================================================
Este archivo hace DOS cosas:
1. Crea la conexión con SQLite (la base de datos)
2. Define las 5 tablas con SQLAlchemy (un ORM)

¿Qué es un ORM?
En vez de escribir SQL a mano ("CREATE TABLE users ..."), defines las tablas
como clases de Python. SQLAlchemy las convierte a SQL por ti.
Ventaja: es más legible, más seguro, y no dependes de un tipo de base de datos.

¿Por qué SQLite?
Es una base de datos que vive en UN SOLO ARCHIVO (nexotime.db).
No necesitas instalar nada. Para un proyecto que empieza, es perfecta.
Si algún día necesitas algo más potente (PostgreSQL), el cambio es mínimo
porque usamos SQLAlchemy como intermediario.
=============================================================================
"""

from sqlalchemy import (
    create_engine,       # Crea la conexión con la base de datos
    Column,              # Define una columna en una tabla
    Integer,             # Tipo: número entero (1, 2, 3...)
    String,              # Tipo: texto ("María", "Leer"...)
    Boolean,             # Tipo: verdadero/falso
    Date,                # Tipo: fecha (2025-02-19)
    DateTime,            # Tipo: fecha + hora
    ForeignKey,          # Relación entre tablas ("este hábito pertenece a este usuario")
)
from sqlalchemy.orm import (
    DeclarativeBase,     # Clase base para definir tablas
    sessionmaker,        # Crea sesiones para hablar con la BD
    relationship,        # Define relaciones entre tablas en Python
)
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# CONEXIÓN
# ─────────────────────────────────────────────────────────────────────────────
# "sqlite:///nexotime.db" significa:
#   - sqlite    → tipo de base de datos
#   - ///       → ruta relativa (en la misma carpeta)
#   - nexotime.db → nombre del archivo
#
# check_same_thread=False → SQLite por defecto solo permite un hilo.
# FastAPI usa múltiples hilos, así que necesitamos desactivar esa restricción.

engine = create_engine(
    "sqlite:///nexotime.db",
    connect_args={"check_same_thread": False},
    echo=False,  # Cambiar a True para ver las queries SQL en la terminal (útil para debug)
)

# SessionLocal es una "fábrica de sesiones".
# Cada vez que la API necesita hablar con la BD, crea una sesión,
# hace su trabajo, y la cierra. Como abrir y cerrar un grifo.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ─────────────────────────────────────────────────────────────────────────────
# CLASE BASE
# ─────────────────────────────────────────────────────────────────────────────
# Todas las tablas heredan de esta clase. Es el "molde" común.

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# TABLA 1: USERS (Usuarios)
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"  # Nombre de la tabla en la BD

    id = Column(Integer, primary_key=True, autoincrement=True)
    # primary_key → identificador único. Nunca se repite.
    # autoincrement → se genera solo: 1, 2, 3...

    email = Column(String, unique=True, nullable=False)
    # unique → no puede haber dos usuarios con el mismo email
    # nullable=False → obligatorio (no puede estar vacío)

    password_hash = Column(String, nullable=False)
    # Guardamos el HASH, nunca la contraseña en texto plano.
    # Un hash es como una huella dactilar: puedes verificar que coincide,
    # pero no puedes reconstruir la contraseña original a partir del hash.

    name = Column(String, nullable=False)

    telegram_id = Column(String, unique=True, nullable=True)
    # Se rellena cuando el usuario vincula su cuenta de Telegram.
    # nullable=True → puede estar vacío (aún no ha vinculado).

    telegram_link_code = Column(String, unique=True, nullable=True)
    # Código temporal (ej: "A7X9K2") que el usuario mete en el bot
    # para vincular su cuenta. Se borra después de usarlo.

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ─── Relaciones ───
    # Esto NO crea columnas en la BD. Solo le dice a Python:
    # "cuando tenga un usuario, puedo acceder a user.habits para ver sus hábitos"
    habits = relationship("Habit", back_populates="user", cascade="all, delete-orphan")
    routines = relationship("Routine", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    habit_logs = relationship("HabitLog", back_populates="user", cascade="all, delete-orphan")
    # cascade="all, delete-orphan" → si borras un usuario, se borran sus hábitos, rutinas, etc.


# ─────────────────────────────────────────────────────────────────────────────
# TABLA 2: HABITS (Hábitos configurados por el usuario)
# ─────────────────────────────────────────────────────────────────────────────

class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # ForeignKey → "este hábito pertenece al usuario con este id"
    # Es el pegamento entre tablas.

    name = Column(String, nullable=False)       # "Leer", "Meditar", "Ejercicio"
    icon = Column(String, default="✅")          # Emoji opcional
    active = Column(Boolean, default=True)       # Para desactivar sin borrar

    user = relationship("User", back_populates="habits")


# ─────────────────────────────────────────────────────────────────────────────
# TABLA 3: ROUTINES (Pasos de rutinas mañana/noche)
# ─────────────────────────────────────────────────────────────────────────────

class Routine(Base):
    __tablename__ = "routines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)        # "morning" o "night"
    step_order = Column(Integer, nullable=False)  # 1, 2, 3... (el orden del paso)
    description = Column(String, nullable=False)  # "Ducha fría", "Meditar"...

    user = relationship("User", back_populates="routines")


# ─────────────────────────────────────────────────────────────────────────────
# TABLA 4: REMINDERS (Horarios de notificación)
# ─────────────────────────────────────────────────────────────────────────────

class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)        # "morning", "habits", "night", "summary"
    time = Column(String, nullable=False)         # "07:00", "22:00"
    active = Column(Boolean, default=True)

    user = relationship("User", back_populates="reminders")


# ─────────────────────────────────────────────────────────────────────────────
# TABLA 5: HABIT_LOGS (Registro diario: ¿hizo el hábito o no?)
# ─────────────────────────────────────────────────────────────────────────────

class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False)

    date = Column(Date, nullable=False)           # 2025-02-19
    completed = Column(Boolean, default=False)

    user = relationship("User", back_populates="habit_logs")
    habit = relationship("Habit")


# ─────────────────────────────────────────────────────────────────────────────
# CREAR TABLAS
# ─────────────────────────────────────────────────────────────────────────────
# Esta función mira todas las clases que heredan de Base y crea las tablas
# en la BD si no existen. Si ya existen, no las toca.

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada (5 tablas creadas)")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Obtener sesión de BD
# ─────────────────────────────────────────────────────────────────────────────
# FastAPI usa esto como "dependencia". Cada petición HTTP abre una sesión,
# hace su trabajo, y la cierra automáticamente con el finally.

def get_db():
    db = SessionLocal()
    try:
        yield db  # yield = "devuelve la sesión y espera a que terminen de usarla"
    finally:
        db.close()  # Siempre cierra la conexión, pase lo que pase
