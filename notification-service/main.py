from fastapi import FastAPI
from pydantic import BaseModel


class NotifyRequest(BaseModel):
    recipient: str
    message: str


class NotifyResponse(BaseModel):
    status: str
    recipient: str


app = FastAPI(title="Notification Service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/notify", response_model=NotifyResponse)
async def notify(payload: NotifyRequest):
    return {"status": "queued", "recipient": payload.recipient}
