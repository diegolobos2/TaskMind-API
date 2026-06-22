import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from google import genai
from pydantic import BaseModel, Field

from app.database.firebase import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

_bearer_scheme = HTTPBearer()

# Conjunto de valores de prioridad aceptados desde Gemini.
_VALID_PRIORITIES = {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Schemas  (capa de presentación — Arquitectura Limpia)
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    owner_uid: str
    created_at: str


# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------


async def get_current_user_uid(
    http_credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> str:
    """Verifica el Firebase ID Token del header Authorization y retorna el UID.

    auth.verify_id_token es bloqueante; se ejecuta en un thread pool para
    no bloquear el event loop de asyncio.
    """
    token = http_credentials.credentials
    try:
        decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        return decoded_token["uid"]
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha expirado. Por favor, inicia sesión nuevamente.",
        )
    except (auth.InvalidIdTokenError, auth.CertificateFetchError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado.",
        )


async def get_genai_client() -> genai.Client:
    """Instancia y provee el cliente de Google GenAI.

    Consume directamente la variable de entorno GEMINI_API_KEY, cargada
    previamente por load_dotenv() en main.py.
    Las llamadas asíncronas se realizan a través del atributo .aio del cliente.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de IA no está disponible.",
        )
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una tarea con priorización automática por IA",
)
async def create_task(
    payload: TaskCreateRequest,
    owner_uid: Annotated[str, Depends(get_current_user_uid)],
    genai_client: Annotated[genai.Client, Depends(get_genai_client)],
) -> TaskResponse:
    """Crea una tarea, invoca a Gemini para asignar prioridad y persiste en Firestore.

    Flujo:
        1. Autenticación — resuelta por la dependencia get_current_user_uid.
        2. Priorización — Gemini analiza título y descripción.
        3. Persistencia — el documento se almacena en la colección "tasks".
        4. Respuesta — retorna el objeto creado con su ID generado por Firestore.
    """
    # --- Paso 2: Priorización por Gemini ---
    prompt = (
        "Eres un asistente de gestión de tareas. Analiza la siguiente tarea y responde "
        "ÚNICAMENTE con una de estas tres palabras en minúsculas: 'low', 'medium' o 'high'.\n\n"
        f"Título: {payload.title}\n"
        f"Descripción: {payload.description}"
    )
    try:
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        priority = response.text.strip().lower()
        if priority not in _VALID_PRIORITIES:
            logger.warning(
                "Gemini retornó un valor inesperado '%s'. Se asigna 'medium'.", priority
            )
            priority = "medium"
    except Exception as exc:
        logger.error("Error al invocar la API de Gemini: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de IA no está disponible en este momento.",
        )

    # --- Paso 3: Persistir en Firestore ---
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    task_data = {
        "title": payload.title,
        "description": payload.description,
        "priority": priority,
        "owner_uid": owner_uid,
        "created_at": now,
    }

    doc_ref = db.collection("tasks").document()
    await doc_ref.set(task_data)

    return TaskResponse(id=doc_ref.id, **task_data)


@router.get(
    "/",
    response_model=list[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar tareas del usuario autenticado, con filtro opcional por prioridad",
)
async def list_tasks(
    owner_uid: Annotated[str, Depends(get_current_user_uid)],
    priority: Annotated[
        Literal["low", "medium", "high"] | None,
        Query(description="Filtra las tareas por nivel de prioridad. Valores aceptados: low, medium, high."),
    ] = None,
) -> list[TaskResponse]:
    """Retorna las tareas del usuario autenticado almacenadas en Firestore.

    Si se provee el parámetro `priority`, la consulta aplica un filtro
    `.where('priority', '==', priority)` antes de ejecutar el stream.
    Si se omite, retorna todas las tareas del usuario.
    """
    db = get_db()
    query = db.collection("tasks").where("owner_uid", "==", owner_uid)

    if priority is not None:
        query = query.where("priority", "==", priority)

    snapshots = query.stream()

    tasks: list[TaskResponse] = []
    async for doc in snapshots:
        data = doc.to_dict()
        tasks.append(TaskResponse(id=doc.id, **data))

    return tasks


@router.post(
    "/test-notification",
    status_code=status.HTTP_200_OK,
    summary="Enviar una notificación de prueba al servicio notification-service",
)
async def test_notification() -> dict[str, str]:
    """Envía una petición educativa al microservicio de notificaciones."""
    payload = {
        "recipient": "alumno@test.com",
        "message": "Nueva tarea creada desde TaskMind",
    }
    url = "http://notification-service:9000/notify"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.RequestError as exc:
        logger.error("Error de conexión con notification-service: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo contactar al servicio de notificaciones.",
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Notification-service respondió con estado %s: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El servicio de notificaciones respondió con error.",
        )

    return response.json()
