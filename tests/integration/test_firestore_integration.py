import os
import uuid

import pytest

from app.database.firebase import init_firebase, get_db


@pytest.mark.asyncio
async def test_firestore_roundtrip():
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        pytest.skip(
            "GOOGLE_APPLICATION_CREDENTIALS not set or file missing; skipping Firestore integration test."
        )

    # Initialize Firebase (uses the same init path as the application)
    await init_firebase()
    db = get_db()

    collection = "integration_tests"
    doc_id = str(uuid.uuid4())
    doc_ref = db.collection(collection).document(doc_id)

    data = {"test_id": doc_id, "value": "integration_integration_test"}

    try:
        # Create
        await doc_ref.set(data)

        # Read
        snapshot = await doc_ref.get()
        assert snapshot.exists
        fetched = snapshot.to_dict()

        # Verify
        assert fetched == data
    finally:
        # Ensure cleanup even on failure
        try:
            await doc_ref.delete()
        except Exception:
            # Best-effort cleanup: do not raise from cleanup failure
            pass
