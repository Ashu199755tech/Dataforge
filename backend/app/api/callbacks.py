from fastapi import APIRouter, Request, HTTPException
from backend.app.execution.callbacks import callback_store

router = APIRouter(prefix="/callbacks", tags=["Callbacks"])


@router.post("/{callback_id}")
async def handle_callback(callback_id: str, request: Request):
    """
    Receives asynchronous webhooks/callbacks from external systems and resolves
    waiting Webhook activities.
    """
    try:
        payload = await request.json()
    except Exception:
        body_bytes = await request.body()
        payload = {"raw_body": body_bytes.decode("utf-8", errors="replace")}

    received = callback_store.receive(callback_id, payload)
    if not received:
        # Callback might have expired or does not exist
        return {
            "status": "warning",
            "message": f"Callback ID '{callback_id}' was not found or has already expired.",
            "callback_id": callback_id
        }

    return {
        "status": "success",
        "message": f"Callback '{callback_id}' delivered successfully.",
        "callback_id": callback_id
    }
