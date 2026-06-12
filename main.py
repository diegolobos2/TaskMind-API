from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Carga las variables de entorno desde .env antes de cualquier inicialización.
# Esto garantiza que GOOGLE_APPLICATION_CREDENTIALS y GEMINI_API_KEY estén
# disponibles cuando los módulos dependientes las lean al importarse.
load_dotenv()

from fastapi import FastAPI  # noqa: E402

from app.database.firebase import init_firebase  # noqa: E402
from app.routers import tasks  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación.

    Al arrancar: inicializa la conexión con Firebase.
    Al cerrar: libera recursos (extensible).
    """
    await init_firebase()
    yield


app = FastAPI(
    title="TaskMind-API",
    description=(
        "Backend asíncrono con FastAPI, Firebase y Gemini "
        "para gestión inteligente de tareas."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
