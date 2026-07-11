"""In-process WebSocket connection manager for pushing live updates to the frontend.

Connections are keyed by user id so a notification (e.g. a new Gmail message)
can be routed only to the user who owns the affected account.
"""
import logging
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger("rdl_sales_logger")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(str(user_id), set()).add(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        conns = self._connections.get(str(user_id))
        if conns:
            conns.discard(websocket)
            if not conns:
                self._connections.pop(str(user_id), None)

    async def notify_user(self, user_id: UUID, message: dict) -> None:
        for ws in list(self._connections.get(str(user_id), ())):
            try:
                await ws.send_json(message)
            except Exception:
                logger.debug(f"[SOCKET] Dropping dead connection for user {user_id}")
                self.disconnect(user_id, ws)


manager = ConnectionManager()
