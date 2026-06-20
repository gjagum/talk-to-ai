from fastapi import APIRouter, WebSocket

from app.features.agent.relay import relay

router = APIRouter()


@router.websocket("/ws")
async def agent_voice(websocket: WebSocket):
    """Relay a single browser session to Deepgram's Voice Agent WebSocket."""
    await websocket.accept()
    try:
        await relay(websocket)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
