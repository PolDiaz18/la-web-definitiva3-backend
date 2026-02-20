"""
=============================================================================
BOT.PY — El Bot de Telegram de NexoTime
=============================================================================
Este bot accede DIRECTAMENTE a la base de datos (no pasa por la API HTTP).
¿Por qué? Porque bot y API corren en el mismo servidor. Hacer llamadas
HTTP a ti mismo es innecesario y puede dar problemas de red.
=============================================================================
"""

import os
import logging
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from database import SessionLocal, User, Habit, Routine, Reminder, HabitLog

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8523928264:AAFMPSIoiCbFz-sR7-y8srpP9j7wDCLUchc")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /start
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if user:
            await update.message.reply_text(
                f"👋 ¡Hola {user.name}! Tu cuenta está vinculada.\n\n"
                f"📋 /habitos — Ver tus hábitos del día\n"
                f"🌅 /morning — Rutina de mañana\n"
                f"🌙 /night — Rutina de noche\n"
                f"📊 /resumen — Resumen del día"
            )
        else:
            await update.message.reply_text(
                "👋 ¡Hola! Soy el bot de NexoTime.\n\n"
                "Para empezar necesitas vincular tu cuenta:\n\n"
                "1️⃣ Regístrate en la web\n"
                "2️⃣ En la web, genera un código de vinculación\n"
                "3️⃣ Escríbeme aquí: /vincular CODIGO\n\n"
                "Ejemplo: /vincular A7X9K2"
            )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /vincular
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_vincular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Falta el código.\n\nUso: /vincular CODIGO\nEjemplo: /vincular A7X9K2"
        )
        return

    code = context.args[0].upper()
    telegram_id = str(update.effective_user.id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_link_code == code).first()
        if not user:
            await update.message.reply_text("❌ Código inválido o expirado. Genera uno nuevo desde la web.")
            return

        user.telegram_id = telegram_id
        user.telegram_link_code = None
        db.commit()

        await update.message.reply_text(
            f"✅ ¡Cuenta vinculada, {user.name}!\n\n"
            f"📋 /habitos — Ver tus hábitos del día\n"
            f"🌅 /morning — Rutina de mañana\n"
            f"🌙 /night — Rutina de noche\n"
            f"📊 /resumen — Resumen del día"
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /habitos
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_habitos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("❌ Cuenta no vinculada. Usa /start para ver cómo hacerlo.")
            return

        habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()
        if not habits:
            await update.message.reply_text("No tienes hábitos configurados. Añádelos desde la web.")
            return

        today = date.today()
        logs = db.query(HabitLog).filter(HabitLog.user_id == user.id, HabitLog.date == today).all()
        completed_map = {log.habit_id: log.completed for log in logs}

        keyboard = []
        text_lines = ["📋 *Tus hábitos de hoy:*\n"]

        for habit in habits:
            is_done = completed_map.get(habit.id, False)
            emoji = "✅" if is_done else "⬜"
            text_lines.append(f"{emoji} {habit.icon} {habit.name}")

            btn_text = "✅ Hecho" if not is_done else "↩️ Deshacer"
            keyboard.append([
                InlineKeyboardButton(
                    f"{btn_text} — {habit.name}",
                    callback_data=f"habit:{habit.id}:{'undo' if is_done else 'done'}"
                )
            ])

        total = len(habits)
        done = sum(1 for h in habits if completed_map.get(h.id, False))
        text_lines.append(f"\n📊 Progreso: {done}/{total}")

        await update.message.reply_text(
            "\n".join(text_lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Botones de hábitos
# ─────────────────────────────────────────────────────────────────────────────

async def callback_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "habit":
        return

    habit_id = int(parts[1])
    completed = parts[2] == "done"
    telegram_id = str(update.effective_user.id)
    today = date.today()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return

        habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
        if not habit:
            return

        existing = db.query(HabitLog).filter(
            HabitLog.user_id == user.id, HabitLog.habit_id == habit_id, HabitLog.date == today,
        ).first()

        if existing:
            existing.completed = completed
        else:
            db.add(HabitLog(user_id=user.id, habit_id=habit_id, date=today, completed=completed))
        db.commit()

        # Recargar y actualizar mensaje
        habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()
        logs = db.query(HabitLog).filter(HabitLog.user_id == user.id, HabitLog.date == today).all()
        completed_map = {log.habit_id: log.completed for log in logs}

        keyboard = []
        text_lines = ["📋 *Tus hábitos de hoy:*\n"]

        for h in habits:
            is_done = completed_map.get(h.id, False)
            emoji = "✅" if is_done else "⬜"
            text_lines.append(f"{emoji} {h.icon} {h.name}")
            btn_text = "✅ Hecho" if not is_done else "↩️ Deshacer"
            keyboard.append([
                InlineKeyboardButton(
                    f"{btn_text} — {h.name}",
                    callback_data=f"habit:{h.id}:{'undo' if is_done else 'done'}"
                )
            ])

        total = len(habits)
        done = sum(1 for h in habits if completed_map.get(h.id, False))
        text_lines.append(f"\n📊 Progreso: {done}/{total}")
        if done == total and total > 0:
            text_lines.append("\n🎉 *¡Has completado todos los hábitos!*")

        await query.edit_message_text(
            "\n".join(text_lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /morning
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("❌ Cuenta no vinculada. Usa /start")
            return

        steps = db.query(Routine).filter(
            Routine.user_id == user.id, Routine.type == "morning"
        ).order_by(Routine.step_order).all()

        if not steps:
            await update.message.reply_text("No tienes rutina de mañana configurada. Añádela desde la web.")
            return

        text = "🌅 *Tu rutina de mañana:*\n\n"
        for step in steps:
            text += f"  {step.step_order}. {step.description}\n"
        text += "\n¡A por el día! 💪"
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /night
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_night(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("❌ Cuenta no vinculada. Usa /start")
            return

        steps = db.query(Routine).filter(
            Routine.user_id == user.id, Routine.type == "night"
        ).order_by(Routine.step_order).all()

        if not steps:
            await update.message.reply_text("No tienes rutina de noche configurada. Añádela desde la web.")
            return

        text = "🌙 *Tu rutina de noche:*\n\n"
        for step in steps:
            text += f"  {step.step_order}. {step.description}\n"
        text += "\n¡Descansa bien! 😴"
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /resumen
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("❌ Cuenta no vinculada. Usa /start")
            return

        today = date.today()
        habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.active == True).all()
        logs = db.query(HabitLog).filter(HabitLog.user_id == user.id, HabitLog.date == today).all()
        logs_map = {l.habit_id: l.completed for l in logs}

        total = len(habits)
        done = sum(1 for h in habits if logs_map.get(h.id, False))
        pct = round((done / total * 100) if total > 0 else 0, 1)

        if pct == 100: mood = "🏆"
        elif pct >= 75: mood = "😊"
        elif pct >= 50: mood = "💪"
        elif pct >= 25: mood = "🌱"
        else: mood = "😶"

        text = f"📊 *Resumen de hoy:*\n\n{mood} Progreso: {done}/{total} ({pct:.0f}%)\n\n"
        for h in habits:
            emoji = "✅" if logs_map.get(h.id, False) else "❌"
            text += f"{emoji} {h.name}\n"

        if pct == 100: text += "\n🎉 *¡Día perfecto!*"
        elif pct >= 50: text += "\n👏 *¡Buen trabajo! Sigue así.*"
        else: text += "\n💡 *Aún estás a tiempo. ¡Tú puedes!*"

        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# ARRANCAR
# ─────────────────────────────────────────────────────────────────────────────

def run_bot():
    """Arranca el bot - versión compatible con hilos secundarios"""
    import asyncio

    async def _run():
        app = Application.builder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("vincular", cmd_vincular))
        app.add_handler(CommandHandler("habitos", cmd_habitos))
        app.add_handler(CommandHandler("morning", cmd_morning))
        app.add_handler(CommandHandler("night", cmd_night))
        app.add_handler(CommandHandler("resumen", cmd_resumen))
        app.add_handler(CallbackQueryHandler(callback_habit))

        # Inicializar el bot manualmente (sin run_polling que no funciona en hilos)
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("🤖 Bot de NexoTime iniciado")

        # Mantener el bot corriendo indefinidamente
        while True:
            await asyncio.sleep(3600)

    asyncio.run(_run())


if __name__ == "__main__":
    run_bot()
