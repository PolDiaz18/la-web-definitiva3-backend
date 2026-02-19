"""
=============================================================================
BOT.PY — El Bot de Telegram de NexoTime
=============================================================================
Este bot NO guarda datos. Todo lo pide y envía al backend (la API en Railway).
Es solo un "mensajero" entre el usuario y el sistema.

Flujo:
1. Usuario escribe comando en Telegram
2. Bot recibe el mensaje
3. Bot llama a la API del backend
4. Backend responde con los datos
5. Bot formatea los datos y se los muestra al usuario

Concepto clave: WEBHOOK vs POLLING
- Polling: el bot pregunta a Telegram "¿hay mensajes nuevos?" cada X segundos
- Webhook: Telegram AVISA al bot cuando hay un mensaje nuevo (más eficiente)
Aquí usamos POLLING porque es más simple. Para producción seria, usarías webhook.
=============================================================================
"""

import os
import logging
from datetime import datetime, time, date

import httpx  # Cliente HTTP asíncrono (para llamar a la API)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Token del bot (se lee de variable de entorno en producción)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8523928264:AAFMPSIoiCbFz-sR7-y8srpP9j7wDCLUchc")

# URL del backend. El bot habla con la API a través de esta URL.
API_URL = os.environ.get("API_URL", "https://web-production-7c012.up.railway.app")

# Configurar logging (para ver qué hace el bot en la terminal)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Llamar a la API
# ─────────────────────────────────────────────────────────────────────────────
# Todas las funciones del bot necesitan hablar con el backend.
# Este helper centraliza las llamadas HTTP para no repetir código.

async def api_call(method: str, endpoint: str, token: str = None, json: dict = None, params: dict = None):
    """
    Hace una petición HTTP al backend.
    
    method   → "GET", "POST", "PUT", "DELETE"
    endpoint → "/habits", "/auth/me", etc.
    token    → JWT del usuario (para endpoints protegidos)
    json     → Datos a enviar en el body (para POST/PUT)
    params   → Parámetros en la URL (para GET con filtros)
    
    Devuelve: (status_code, response_json)
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{API_URL}{endpoint}",
            headers=headers,
            json=json,
            params=params,
            timeout=10.0,
        )
        
        try:
            data = response.json()
        except Exception:
            data = None
        
        return response.status_code, data


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Obtener token del usuario por telegram_id
# ─────────────────────────────────────────────────────────────────────────────
# El backend usa JWT para autenticar. Pero el bot solo conoce el telegram_id.
# Necesitamos un endpoint especial en el backend para esto.
# Por ahora, el bot llama a /telegram/link para vincular, y luego usa
# un endpoint interno para obtener datos del usuario por telegram_id.
#
# NOTA: Vamos a añadir un endpoint al backend para esto.

async def get_user_data(telegram_id: str, endpoint: str):
    """
    Llama al backend con el telegram_id como parámetro.
    El backend buscará al usuario por su telegram_id.
    """
    status, data = await api_call("GET", f"{endpoint}", params={"telegram_id": telegram_id})
    return status, data


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /start
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saluda al usuario y explica cómo vincular su cuenta"""
    
    telegram_id = str(update.effective_user.id)
    
    # Comprobar si ya está vinculado
    status, data = await api_call("GET", f"/telegram/user/{telegram_id}")
    
    if status == 200:
        name = data.get("name", "")
        await update.message.reply_text(
            f"👋 ¡Hola {name}! Tu cuenta está vinculada.\n\n"
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


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /vincular
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_vincular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vincula la cuenta de Telegram con la cuenta web usando un código"""
    
    # context.args contiene las palabras después del comando
    # Si el usuario escribe "/vincular A7X9K2", context.args = ["A7X9K2"]
    if not context.args:
        await update.message.reply_text(
            "❌ Falta el código.\n\n"
            "Uso: /vincular CODIGO\n"
            "Ejemplo: /vincular A7X9K2\n\n"
            "Genera el código desde la web."
        )
        return
    
    code = context.args[0].upper()
    telegram_id = str(update.effective_user.id)
    
    # Llamar al backend para vincular
    status, data = await api_call(
        "POST", "/telegram/link",
        params={"telegram_id": telegram_id, "link_code": code}
    )
    
    if status == 200:
        await update.message.reply_text(
            f"✅ ¡Cuenta vinculada correctamente!\n\n"
            f"Ya puedes usar todos los comandos:\n"
            f"📋 /habitos — Ver tus hábitos del día\n"
            f"🌅 /morning — Rutina de mañana\n"
            f"🌙 /night — Rutina de noche\n"
            f"📊 /resumen — Resumen del día"
        )
    elif status == 404:
        await update.message.reply_text(
            "❌ Código inválido o expirado.\n\n"
            "Genera uno nuevo desde la web e inténtalo de nuevo."
        )
    else:
        await update.message.reply_text("❌ Error al vincular. Inténtalo de nuevo.")


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /habitos
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_habitos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los hábitos del día con botones para marcar/desmarcar"""
    
    telegram_id = str(update.effective_user.id)
    
    # Pedir hábitos al backend
    status, habits = await api_call("GET", f"/telegram/habits/{telegram_id}")
    
    if status == 404:
        await update.message.reply_text("❌ Cuenta no vinculada. Usa /start para ver cómo hacerlo.")
        return
    
    if status != 200 or not habits:
        await update.message.reply_text("No tienes hábitos configurados. Añádelos desde la web.")
        return
    
    # Pedir el estado de hoy
    today = date.today().isoformat()
    _, logs = await api_call("GET", f"/telegram/logs/{telegram_id}/{today}")
    
    # Crear un diccionario {habit_id: completed} para saber cuáles están hechos
    completed_map = {}
    if logs:
        for log in logs:
            completed_map[log["habit_id"]] = log["completed"]
    
    # Construir botones inline
    # Cada botón tiene un callback_data con formato "habit:ID:ACCION"
    # Ejemplo: "habit:3:toggle" → togglear el hábito con id 3
    keyboard = []
    text_lines = ["📋 *Tus hábitos de hoy:*\n"]
    
    for habit in habits:
        is_done = completed_map.get(habit["id"], False)
        emoji = "✅" if is_done else "⬜"
        text_lines.append(f"{emoji} {habit['icon']} {habit['name']}")
        
        # Botón para togglear
        btn_text = "✅ Hecho" if not is_done else "↩️ Deshacer"
        keyboard.append([
            InlineKeyboardButton(
                f"{btn_text} — {habit['name']}",
                callback_data=f"habit:{habit['id']}:{'undo' if is_done else 'done'}"
            )
        ])
    
    # Calcular progreso
    total = len(habits)
    done = sum(1 for h in habits if completed_map.get(h["id"], False))
    text_lines.append(f"\n📊 Progreso: {done}/{total}")
    
    await update.message.reply_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK: Botones de hábitos
# ─────────────────────────────────────────────────────────────────────────────

async def callback_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa los clics en los botones de hábitos"""
    
    query = update.callback_query
    await query.answer()  # Obligatorio: confirma a Telegram que recibimos el clic
    
    # Parsear callback_data: "habit:ID:ACCION"
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "habit":
        return
    
    habit_id = int(parts[1])
    action = parts[2]  # "done" o "undo"
    completed = action == "done"
    
    telegram_id = str(update.effective_user.id)
    today = date.today().isoformat()
    
    # Enviar al backend
    status, _ = await api_call(
        "POST", f"/telegram/log-habit/{telegram_id}",
        json={"habit_id": habit_id, "date": today, "completed": completed}
    )
    
    if status != 200:
        await query.edit_message_text("❌ Error al actualizar. Inténtalo de nuevo.")
        return
    
    # Recargar los hábitos y actualizar el mensaje
    _, habits = await api_call("GET", f"/telegram/habits/{telegram_id}")
    _, logs = await api_call("GET", f"/telegram/logs/{telegram_id}/{today}")
    
    completed_map = {}
    if logs:
        for log in logs:
            completed_map[log["habit_id"]] = log["completed"]
    
    keyboard = []
    text_lines = ["📋 *Tus hábitos de hoy:*\n"]
    
    for habit in habits:
        is_done = completed_map.get(habit["id"], False)
        emoji = "✅" if is_done else "⬜"
        text_lines.append(f"{emoji} {habit['icon']} {habit['name']}")
        
        btn_text = "✅ Hecho" if not is_done else "↩️ Deshacer"
        keyboard.append([
            InlineKeyboardButton(
                f"{btn_text} — {habit['name']}",
                callback_data=f"habit:{habit['id']}:{'undo' if is_done else 'done'}"
            )
        ])
    
    total = len(habits)
    done = sum(1 for h in habits if completed_map.get(h["id"], False))
    text_lines.append(f"\n📊 Progreso: {done}/{total}")
    
    # Mensaje especial si completa todos
    if done == total and total > 0:
        text_lines.append("\n🎉 *¡Has completado todos los hábitos!*")
    
    await query.edit_message_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /manana
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_manana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la rutina de mañana del usuario"""
    
    telegram_id = str(update.effective_user.id)
    status, steps = await api_call("GET", f"/telegram/routine/{telegram_id}/morning")
    
    if status == 404:
        await update.message.reply_text("❌ Cuenta no vinculada. Usa /start")
        return
    
    if not steps:
        await update.message.reply_text("No tienes rutina de mañana configurada. Añádela desde la web.")
        return
    
    text = "🌅 *Tu rutina de mañana:*\n\n"
    for step in steps:
        text += f"  {step['step_order']}. {step['description']}\n"
    text += "\n¡A por el día! 💪"
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /noche
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_noche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la rutina de noche del usuario"""
    
    telegram_id = str(update.effective_user.id)
    status, steps = await api_call("GET", f"/telegram/routine/{telegram_id}/night")
    
    if status == 404:
        await update.message.reply_text("❌ Cuenta no vinculada. Usa /start")
        return
    
    if not steps:
        await update.message.reply_text("No tienes rutina de noche configurada. Añádela desde la web.")
        return
    
    text = "🌙 *Tu rutina de noche:*\n\n"
    for step in steps:
        text += f"  {step['step_order']}. {step['description']}\n"
    text += "\n¡Descansa bien! 😴"
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────────────────
# COMANDO: /resumen
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el resumen del día"""
    
    telegram_id = str(update.effective_user.id)
    today = date.today().isoformat()
    
    status, summary = await api_call("GET", f"/telegram/summary/{telegram_id}/{today}")
    
    if status == 404:
        await update.message.reply_text("❌ Cuenta no vinculada. Usa /start")
        return
    
    if status != 200 or not summary:
        await update.message.reply_text("No hay datos para hoy todavía.")
        return
    
    pct = summary.get("percentage", 0)
    done = summary.get("completed", 0)
    total = summary.get("total_habits", 0)
    
    # Elegir emoji según progreso
    if pct == 100:
        mood = "🏆"
    elif pct >= 75:
        mood = "😊"
    elif pct >= 50:
        mood = "💪"
    elif pct >= 25:
        mood = "🌱"
    else:
        mood = "😶"
    
    text = f"📊 *Resumen de hoy:*\n\n"
    text += f"{mood} Progreso: {done}/{total} ({pct:.0f}%)\n\n"
    
    # Detallar cada hábito
    habits_detail = summary.get("habits_detail", [])
    for h in habits_detail:
        emoji = "✅" if h["completed"] else "❌"
        text += f"{emoji} {h['name']}\n"
    
    if pct == 100:
        text += "\n🎉 *¡Día perfecto!*"
    elif pct >= 50:
        text += "\n👏 *¡Buen trabajo! Sigue así.*"
    else:
        text += "\n💡 *Aún estás a tiempo. ¡Tú puedes!*"
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────────────────
# ARRANCAR EL BOT
# ─────────────────────────────────────────────────────────────────────────────

def run_bot():
    """Configura y arranca el bot"""
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("vincular", cmd_vincular))
    app.add_handler(CommandHandler("habitos", cmd_habitos))
    app.add_handler(CommandHandler("morning", cmd_manana))
    app.add_handler(CommandHandler("night", cmd_noche))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    
    # Registrar handler de callbacks (botones inline)
    app.add_handler(CallbackQueryHandler(callback_habit))
    
    logger.info("🤖 Bot de NexoTime iniciado")
    
    # Arrancar polling
    app.run_polling(drop_pending_updates=True)


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_bot()
