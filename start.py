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
import asyncio
import os
import uvicorn


def start_bot():
    """Arranca el bot de Telegram en un hilo separado con su propio event loop"""
    # Crear un event loop nuevo para este hilo
    # (Python solo crea event loop automáticamente en el hilo principal)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from bot import run_bot
    run_bot()


if __name__ == "__main__":
    # Lanzar bot en un hilo secundario
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    print("🤖 Bot arrancado")

    # Lanzar API en el hilo principal
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 API arrancando en puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
