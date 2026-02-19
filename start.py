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


def start_api():
    """Arranca la API de FastAPI"""
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


def start_bot():
    """Arranca el bot de Telegram"""
    from bot import run_bot
    run_bot()


if __name__ == "__main__":
    # Lanzar API en un hilo
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    print("🚀 API arrancada")

    # Lanzar bot en el hilo principal
    # (el bot usa asyncio, es mejor que corra en el main thread)
    print("🤖 Arrancando bot...")
    start_bot()
