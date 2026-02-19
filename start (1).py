"""
=============================================================================
START.PY — Arranca la API y el Bot a la vez
=============================================================================
Railway solo permite UN proceso por servicio (un Procfile).
Este script lanza ambos en paralelo:
- La API (FastAPI con uvicorn) en un hilo
- El bot (polling de Telegram) en otro hilo

¿Por qué hilos y no procesos?
Porque comparten la misma base de datos SQLite. Con procesos separados
podrían chocar al escribir. Con hilos, Python gestiona el acceso.
=============================================================================
"""

import threading
import os
import uvicorn


def start_bot():
    """Arranca el bot de Telegram en un hilo separado"""
    from bot import run_bot
    run_bot()


if __name__ == "__main__":
    # Lanzar bot en un hilo secundario
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    print("🤖 Bot arrancado en hilo secundario")

    # Lanzar API en el hilo principal
    # Railway necesita que el puerto responda rápido, por eso la API va aquí
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 API arrancando en puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
