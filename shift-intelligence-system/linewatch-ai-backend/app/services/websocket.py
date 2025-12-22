"""
WebSocket connection manager for real-time frontend streaming.
"""
from typing import List, Dict, Any
from fastapi import WebSocket
from app.utils.logging import get_agent_logger

logger = get_agent_logger("WebSocket")

class ConnectionManager:
    """
    Manages active WebSocket connections and broadcasts messages.
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        """Accept a new connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"🔌 Frontend connected. Total active: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"🔌 Frontend disconnected. Total active: {len(self.active_connections)}")
            
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast JSON message to all connected clients.
        
        Args:
            message: Dictionary containing event type and payload
        """
        # Basic validation
        if not isinstance(message, dict):
            logger.error(f"Cannot broadcast non-dict message: {message}")
            return
            
        # Logging for traceability
        # logger.debug(f"📡 Broadcasting: {message.get('type', 'unknown')}")
        
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                to_remove.append(connection)
                
        # Cleanup dead connections
        for dead in to_remove:
            self.disconnect(dead)

# Global manager instance
manager = ConnectionManager()
