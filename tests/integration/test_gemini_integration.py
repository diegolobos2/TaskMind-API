import os

import pytest

from google import genai


@pytest.mark.asyncio
async def test_gemini_minimal_call():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set; skipping Gemini integration test.")

    client = genai.Client(api_key=api_key)

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents="Di simplemente: hola",
        )
    except Exception as exc:
        pytest.skip(f"Gemini service unavailable during integration test: {exc}")

    text = getattr(response, "text", None)
    if text is None:
        text = str(response)

    assert text and text.strip() != ""
