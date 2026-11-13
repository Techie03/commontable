"""WebSocket connection manager (contract section 4).

Channels:
  order:{order_id}       order customer + restaurant staff of it
  driver:{driver_id}     that driver
  dispatch               dispatcher + admin
  restaurant:{id}        staff of it

Event envelope: {"type": "...", "data": {...}, "at": "<UTC ISO>"}.
"""

import asyncio
from datetime import datetime, timezone

from fastapi import WebSocket


def _envelope(event_type: str, data: dict) -> dict:
    return {
        "type": event_type,
        "data": data,
        "at": datetime.now(timezone.utc).isoformat(),
    }


class ConnectionManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._channels.setdefault(channel, set()).add(websocket)

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._channels.get(channel)
            if sockets is not None:
                sockets.discard(websocket)
                if not sockets:
                    del self._channels[channel]

    async def broadcast(self, channel: str, event_type: str, data: dict) -> None:
        async with self._lock:
            sockets = list(self._channels.get(channel, set()))
        if not sockets:
            return
        message = _envelope(event_type, data)
        dead: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_json(message)
            except Exception:
                dead.append(socket)
        if dead:
            async with self._lock:
                for socket in dead:
                    self._channels.get(channel, set()).discard(socket)

    # -- channel helpers -------------------------------------------------
    @staticmethod
    def order_channel(order_id: int) -> str:
        return f"order:{order_id}"

    @staticmethod
    def driver_channel(driver_id: int) -> str:
        return f"driver:{driver_id}"

    @staticmethod
    def restaurant_channel(restaurant_id: int) -> str:
        return f"restaurant:{restaurant_id}"

    DISPATCH_CHANNEL = "dispatch"


manager = ConnectionManager()
