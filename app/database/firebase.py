import asyncio
import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore_async

logger = logging.getLogger(__name__)

# Singleton: cliente Firestore asíncrono compartido por toda la app.
_db: firestore_async.AsyncClient | None = None


async def init_firebase() -> None:
    """Inicializa Firebase Admin SDK usando la ruta de credenciales definida
    en la variable de entorno GOOGLE_APPLICATION_CREDENTIALS.

    La variable debe apuntar al archivo firebase-credentials.json y es
    cargada por load_dotenv() en main.py antes de que esta función sea
    invocada desde el lifespan de FastAPI.

    La llamada a firebase_admin.initialize_app es bloqueante (CPU/I/O);
    se delega a un thread pool con asyncio.to_thread para no bloquear
    el event loop principal.
    """
    global _db

    if firebase_admin._apps:
        logger.info("Firebase ya inicializado. Omitiendo re-inicialización.")
        _db = firestore_async.client()
        return

    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        raise EnvironmentError(
            "La variable de entorno GOOGLE_APPLICATION_CREDENTIALS no está definida. "
            "Verifica que el archivo .env contiene la ruta al archivo de credenciales."
        )

    cred = credentials.Certificate(credentials_path)
    await asyncio.to_thread(firebase_admin.initialize_app, cred)

    _db = firestore_async.client()
    logger.info("Firebase inicializado correctamente.")


def get_db() -> firestore_async.AsyncClient:
    """Retorna el cliente Firestore asíncrono (singleton).

    Úsalo como dependencia o llamada directa desde los servicios.

    Raises:
        RuntimeError: Si se invoca antes de que init_firebase() haya
            sido ejecutado en el lifespan de la aplicación.
    """
    if _db is None:
        raise RuntimeError(
            "El cliente de Firestore no está disponible. "
            "Verifica que init_firebase() se ejecutó en el lifespan de la app."
        )
    return _db
