from fastapi import APIRouter, WebSocket

from app.features.realtime.relay import relay

router = APIRouter()


@router.websocket("/ws")
async def realtime_voice(websocket: WebSocket):
    await websocket.accept()
    try:
        await relay(websocket)
    finally:
        await websocket.close()
