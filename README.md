# NexoTime Backend

API para el sistema de productividad NexoTime.

## Qué hace
- Registro/login de usuarios con JWT
- Configuración de hábitos personalizados
- Rutinas de mañana y noche
- Recordatorios por Telegram
- Tracking diario de hábitos con estadísticas

## Estructura
```
main.py          → API (endpoints)
database.py      → Base de datos (tablas)
models.py        → Esquemas de datos (validación)
bot.py           → Bot de Telegram (próximo paso)
```

## Despliegue en Railway
1. Sube este repo a GitHub
2. Conecta Railway a tu repo
3. Añade la variable de entorno: `SECRET_KEY=tu-clave-secreta-larga`
4. Railway detecta el Procfile y arranca automáticamente

## Probar en local
```bash
pip install -r requirements.txt
python main.py
# Abre http://localhost:8000/docs para ver la documentación
```
