"""Configuración global de fixtures para la suite de tests de TaskMind-API.

Estrategia de aislamiento:
- `mock_firestore`: parchea `get_db` en el módulo del router y bloquea
  `init_firebase` en el lifespan para que los tests nunca toquen Firebase.
- `client`: construye un `httpx.AsyncClient` asíncrono con transporte ASGI
  apuntando directamente a la app. Sobreescribe las dependencias de
  autenticación y GenAI para aislar los tests de servicios externos.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.routers.tasks import get_current_user_uid, get_genai_client
from main import app

# UID sintético que se inyecta como usuario autenticado en cada test.
_TEST_UID = "test-user-uid-001"


@pytest_asyncio.fixture
async def mock_firestore():
    """Mockea globalmente las llamadas a Firebase para aislar los tests.

    Acciones:
    - Parchea `app.routers.tasks.get_db` para devolver un cliente Firestore
      simulado con una cadena de mocks que replica la API de Firestore.
    - Parchea `main.init_firebase` con un `AsyncMock` para impedir que el
      lifespan de FastAPI intente conectarse a Firebase durante los tests.

    Yields:
        MagicMock: El cliente Firestore simulado, listo para hacer asserts
        sobre las llamadas realizadas (e.g. `mock_db.collection.assert_called_with`).
    """
    # --- Cadena de mocks que replica la API de Firestore ---
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "test-task-id-abc123"
    mock_doc_ref.set = AsyncMock()
    mock_doc_ref.get = AsyncMock()
    mock_doc_ref.update = AsyncMock()
    mock_doc_ref.delete = AsyncMock()

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    mock_collection.add = AsyncMock(return_value=(None, mock_doc_ref))

    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection

    with (
        patch("app.routers.tasks.get_db", return_value=mock_db),
        patch("main.init_firebase", new_callable=AsyncMock),
    ):
        yield mock_db


@pytest_asyncio.fixture
async def client(mock_firestore: MagicMock):
    """Provee un `httpx.AsyncClient` asíncrono apuntando a la app FastAPI.

    Sobreescribe las dependencias de FastAPI para aislar la lógica HTTP pura:
    - `get_current_user_uid`: devuelve un UID de prueba sin validar ningún token.
    - `get_genai_client`: devuelve un cliente GenAI simulado que responde
      con `'medium'` como prioridad por defecto.

    Args:
        mock_firestore: Fixture que garantiza que Firebase está mockeado
            antes de que el lifespan de la app arranque.

    Yields:
        AsyncClient: Cliente HTTP listo para realizar peticiones a los endpoints.
    """
    mock_genai_response = MagicMock()
    mock_genai_response.text = "medium"

    mock_genai_client = MagicMock()
    mock_genai_client.aio.models.generate_content = AsyncMock(
        return_value=mock_genai_response
    )

    app.dependency_overrides[get_current_user_uid] = lambda: _TEST_UID
    app.dependency_overrides[get_genai_client] = lambda: mock_genai_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthenticated_client(mock_firestore: MagicMock):
    """Cliente HTTP sin sobreescritura de autenticación.

    Útil para tests que validan el rechazo de peticiones no autenticadas.
    A diferencia de `client`, NO sobreescribe `get_current_user_uid`, por lo
    que `HTTPBearer` rechaza las peticiones sin el header Authorization.

    Args:
        mock_firestore: Fixture que garantiza que Firebase está mockeado
            antes de que el lifespan de la app arranque.

    Yields:
        AsyncClient: Cliente HTTP sin credenciales de autenticación inyectadas.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
