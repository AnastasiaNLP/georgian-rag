"""
WebSocket handler for real-time chat
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        """Accept new connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        """Remove connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def send_message(self, client_id: str, message: dict):
        """Send message to specific client"""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all clients"""
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, client_id: str, rag_system: Optional[object]):
    """Handle WebSocket connection"""
    await manager.connect(client_id, websocket)

    try:
        while True:
            # receive message
            data = await websocket.receive_json()

            message_type = data.get("type")

            if message_type == "ping":
                # respond to ping
                await manager.send_message(client_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

            elif message_type == "chat":
                # handle chat message
                query = data.get("query")
                target_language = data.get("target_language", "en")
                conversation_id = data.get("conversation_id")

                # send status
                await manager.send_message(client_id, {
                    "type": "status",
                    "status": "processing"
                })

                # placeholder response
                response = {
                    "type": "response",
                    "data": {
                        "response": f"WebSocket query received: {query}",
                        "language": target_language,
                        "sources": [],
                        "conversation_id": conversation_id
                    }
                }

                await manager.send_message(client_id, response)

            else:
                # unknown message type
                await manager.send_message(client_id, {
                    "type": "error",
                    "error": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)