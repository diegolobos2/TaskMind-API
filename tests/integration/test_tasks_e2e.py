import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import firebase_admin
import pytest
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from httpx import ASGITransport, AsyncClient

from app.routers.tasks import get_current_user_uid, get_genai_client
from main import app


@pytest.mark.asyncio
async def test_tasks_e2e_create_and_query():
    load_dotenv()

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not cred_path or not os.path.exists(cred_path) or not api_key:
        pytest.skip(
            "GOOGLE_APPLICATION_CREDENTIALS/GEMINI_API_KEY not configured; skipping E2E tasks test."
        )

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))

    test_uid = "test-e2e-user-uid"

    async def _override_user_uid():
        return test_uid

    mock_genai_response = MagicMock()
    mock_genai_response.text = "medium"

    mock_genai_client = MagicMock()
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_genai_response)

    async def _override_genai_client():
        return mock_genai_client

    app.dependency_overrides[get_current_user_uid] = _override_user_uid
    app.dependency_overrides[get_genai_client] = _override_genai_client

    title = f"e2e-title-{uuid.uuid4()}"
    description = "E2E test task description"
    payload = {"title": title, "description": description}

    class _SyncDocSnapshot:
        def __init__(self, doc):
            self._doc = doc
            self.id = doc.id

        @property
        def exists(self):
            return self._doc.exists

        def to_dict(self):
            return self._doc.to_dict()

    class _SyncDocRef:
        def __init__(self, doc_ref):
            self._doc_ref = doc_ref
            self.id = doc_ref.id

        async def set(self, data):
            self._doc_ref.set(data)

        async def get(self):
            return _SyncDocSnapshot(self._doc_ref.get())

        async def delete(self):
            self._doc_ref.delete()

    class _SyncQuery:
        def __init__(self, query):
            self._query = query
            self._docs = []
            self._index = 0

        def where(self, field, operator, value):
            return _SyncQuery(self._query.where(field, operator, value))

        def stream(self):
            self._docs = list(self._query.stream())
            self._index = 0
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._index >= len(self._docs):
                raise StopAsyncIteration
            doc = self._docs[self._index]
            self._index += 1
            return _SyncDocSnapshot(doc)

    class _SyncCollection:
        def __init__(self, collection):
            self._collection = collection

        def document(self, doc_id=None):
            if doc_id is None:
                return _SyncDocRef(self._collection.document())
            return _SyncDocRef(self._collection.document(doc_id))

        def where(self, field, operator, value):
            return _SyncQuery(self._collection.where(field, operator, value))

    class _SyncDB:
        def __init__(self, db):
            self._db = db

        def collection(self, name):
            return _SyncCollection(self._db.collection(name))

    created_doc_id = None
    sync_db = firestore.client()
    fake_db = _SyncDB(sync_db)

    try:
        with patch("app.routers.tasks.get_db", return_value=fake_db):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/tasks/", json=payload)
                assert resp.status_code == 201, resp.text
                body = resp.json()
                created_doc_id = body.get("id")
                assert created_doc_id is not None

                doc_ref = sync_db.collection("tasks").document(created_doc_id)
                snapshot = doc_ref.get()
                assert snapshot.exists
                data = snapshot.to_dict()
                assert data.get("title") == title
                assert data.get("description") == description

                list_resp = await client.get("/api/v1/tasks/", params={"priority": "medium"})
                assert list_resp.status_code == 200
                items = list_resp.json()
                ids = {item["id"] for item in items}
                assert created_doc_id in ids
    finally:
        app.dependency_overrides.clear()
        if created_doc_id:
            try:
                sync_db.collection("tasks").document(created_doc_id).delete()
            except Exception:
                pass
