"""Tests del router de tareas: POST /api/v1/tasks/ y GET /api/v1/tasks/."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from tests.conftest import unauthenticated_client  # noqa: F401  (fixture re-export)


@pytest.mark.asyncio
async def test_create_task_retorna_201_y_estructura_correcta(client: AsyncClient):
    """Una petición válida debe crear la tarea y retornar HTTP 201
    con todos los campos esperados en el cuerpo de la respuesta."""
    payload = {
        "title": "Preparar informe mensual",
        "description": "Redactar el resumen ejecutivo de ventas del trimestre.",
    }

    response = await client.post(
        "/api/v1/tasks/",
        json=payload,
        headers={"Authorization": "Bearer fake-token-para-test"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "test-task-id-abc123"
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["priority"] == "medium"
    assert data["owner_uid"] == "test-user-uid-001"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_task_sin_titulo_retorna_422(client: AsyncClient):
    """Una petición sin campo `title` debe ser rechazada con HTTP 422
    por la validación de Pydantic antes de llegar a la lógica de negocio."""
    payload = {"description": "Descripción sin título"}

    response = await client.post(
        "/api/v1/tasks/",
        json=payload,
        headers={"Authorization": "Bearer fake-token-para-test"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_titulo_vacio_retorna_422(client: AsyncClient):
    """Un `title` vacío debe fallar la validación de longitud mínima (min_length=1)."""
    payload = {"title": "", "description": "Descripción válida"}

    response = await client.post(
        "/api/v1/tasks/",
        json=payload,
        headers={"Authorization": "Bearer fake-token-para-test"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_sin_header_auth_retorna_401(
    unauthenticated_client: AsyncClient,
):
    """Una petición sin header Authorization debe ser rechazada con HTTP 401
    por el esquema HTTPBearer antes de evaluar el token.

    Usa `unauthenticated_client` que NO sobreescribe `get_current_user_uid`,
    permitiendo que FastAPI ejecute la validación real del header.
    """
    payload = {
        "title": "Tarea sin auth",
        "description": "No debería procesarse.",
    }

    response = await unauthenticated_client.post("/api/v1/tasks/", json=payload)

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/ — Filtrado por prioridad
# ---------------------------------------------------------------------------

# Tareas sintéticas que el mock de Firestore devolverá en la consulta filtrada.
_HIGH_PRIORITY_TASKS = [
    {
        "id": "task-high-001",
        "title": "Resolver bug crítico en producción",
        "description": "El servicio de pagos falla intermitentemente.",
        "priority": "high",
        "owner_uid": "test-user-uid-001",
        "created_at": "2026-06-12T10:00:00+00:00",
    },
    {
        "id": "task-high-002",
        "title": "Desplegar hotfix en staging",
        "description": "Aplicar el parche de seguridad antes del cierre.",
        "priority": "high",
        "owner_uid": "test-user-uid-001",
        "created_at": "2026-06-12T11:00:00+00:00",
    },
]


@pytest.mark.asyncio
async def test_get_tasks_filtradas_por_prioridad_high(client: AsyncClient):
    """GET /api/v1/tasks/?priority=high debe retornar HTTP 200 con la lista
    de tareas cuyo campo 'priority' es 'high'.

    NOTE: Este test falla intencionalmente porque el endpoint GET /api/v1/tasks/
    aún no está implementado. Refleja el criterio de aceptación del Escenario 1
    de HU-03 y sirve como guía TDD para la próxima iteración.
    """
    # Construimos los DocumentSnapshot sintéticos que Firestore devolvería
    # al iterar sobre los resultados de la query filtrada.
    mock_snapshots = []
    for task in _HIGH_PRIORITY_TASKS:
        snap = MagicMock()
        snap.id = task["id"]
        snap.to_dict.return_value = {k: v for k, v in task.items() if k != "id"}
        mock_snapshots.append(snap)

    # stream() en la API real de Firestore retorna un async generator, no una
    # corutina. Definimos uno sintético para que `async for doc in query.stream()`
    # funcione correctamente en el endpoint.
    async def _mock_stream():
        for snapshot in mock_snapshots:
            yield snapshot

    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.stream = _mock_stream

    mock_collection = MagicMock()
    mock_collection.where.return_value = mock_query

    with patch("app.routers.tasks.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.collection.return_value = mock_collection
        mock_get_db.return_value = mock_db

        response = await client.get(
            "/api/v1/tasks/",
            params={"priority": "high"},
            headers={"Authorization": "Bearer fake-token-para-test"},
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert all(task["priority"] == "high" for task in data)
    assert all(task["owner_uid"] == "test-user-uid-001" for task in data)
    task_ids = {task["id"] for task in data}
    assert task_ids == {"task-high-001", "task-high-002"}
