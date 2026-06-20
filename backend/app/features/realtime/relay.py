"""Bidirectional relay between the browser and the OpenAI Realtime API.

The browser speaks the OpenAI Realtime JSON protocol directly; this module
is a transparent pass-through that hides the OpenAI API key from the client.
"""
import asyncio

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import Config

OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"


async def _pump_client_to_openai(client_ws: WebSocket, openai_ws):
    try:
        while True:
            data = await client_ws.receive_text()
            await openai_ws.send(data)
    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        print(f"Error receiving from client: {e}")


async def _pump_openai_to_client(openai_ws, client_ws: WebSocket):
    try:
        async for message in openai_ws:
            await client_ws.send_text(message)
    except Exception as e:
        print(f"Error receiving from OpenAI: {e}")


async def relay(client_ws: WebSocket) -> None:
    """Connect to OpenAI Realtime and pump messages both ways until either side closes."""
    headers = {
        "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(OPENAI_WS_URL, additional_headers=headers) as openai_ws:
            print("Connected to OpenAI Realtime API.")

            task1 = asyncio.create_task(_pump_client_to_openai(client_ws, openai_ws))
            task2 = asyncio.create_task(_pump_openai_to_client(openai_ws, client_ws))

            done, pending = await asyncio.wait(
                [task1, task2],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as e:
        print(f"Error connecting to OpenAI Realtime API: {e}")
