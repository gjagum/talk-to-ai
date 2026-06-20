import os
import json
import asyncio
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import Config

router = APIRouter()

OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

async def receive_from_client(client_ws: WebSocket, openai_ws):
    try:
        while True:
            data = await client_ws.receive_text()
            # Forward everything from client directly to OpenAI
            await openai_ws.send(data)
    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        print(f"Error receiving from client: {e}")

async def receive_from_openai(openai_ws, client_ws: WebSocket):
    try:
        async for message in openai_ws:
            # Forward everything from OpenAI directly to client
            await client_ws.send_text(message)
    except Exception as e:
        print(f"Error receiving from OpenAI: {e}")

@router.websocket("/ws")
async def realtime_voice(websocket: WebSocket):
    await websocket.accept()
    
    headers = {
        "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }
    
    try:
        async with websockets.connect(OPENAI_WS_URL, additional_headers=headers) as openai_ws:
            print("Connected to OpenAI Realtime API.")
            
            # Start relaying messages
            task1 = asyncio.create_task(receive_from_client(websocket, openai_ws))
            task2 = asyncio.create_task(receive_from_openai(openai_ws, websocket))
            
            done, pending = await asyncio.wait(
                [task1, task2],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                
    except Exception as e:
        print(f"Error connecting to OpenAI Realtime API: {e}")
    finally:
        await websocket.close()
