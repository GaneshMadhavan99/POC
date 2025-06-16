from typing import Dict
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Store WebSocket connections by connection ID
        self.connections: Dict[str, WebSocket] = {}
        # Store WebSocket connections by correlation ID for message routing
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        self.connections[connection_id] = websocket
        logger.info(f"WebSocket connected: {connection_id}")
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.connections:
            del self.connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")
        
        # Clean up any correlation ID mappings for this connection
        to_remove = []
        for correlation_id, ws in self.active_connections.items():
            if connection_id in str(ws):  # Simple way to match websocket
                to_remove.append(correlation_id)
        
        for correlation_id in to_remove:
            del self.active_connections[correlation_id]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send message to WebSocket: {e}")
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSockets"""
        disconnected = []
        for connection_id, websocket in self.connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected WebSockets
        for connection_id in disconnected:
            self.disconnect(connection_id)