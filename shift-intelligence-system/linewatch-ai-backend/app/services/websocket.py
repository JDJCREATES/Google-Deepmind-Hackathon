"""
WebSocket connection manager for real-time frontend streaming.
"""
from typing import List, Dict, Any
from collections import deque
from datetime import datetime
from fastapi import WebSocket
from app.utils.logging import get_agent_logger

logger = get_agent_logger("WebSocket")

# Maximum log entries to keep in memory
MAX_LOG_ENTRIES = 500

class ConnectionManager:
    """
    Manages active WebSocket connections and broadcasts messages.
    Also maintains an event log for persistence across clients.
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Event log buffer - stores last N events for new clients
        self.event_log: deque = deque(maxlen=MAX_LOG_ENTRIES)
        
    async def connect(self, websocket: WebSocket):
        """Accept a new connection and send historical logs."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"🔌 Frontend connected. Total active: {len(self.active_connections)}")
        
        # Send historical logs to new client
        if self.event_log:
            try:
                await websocket.send_json({
                    "type": "log_history",
                    "data": {
                        "logs": list(self.event_log),
                        "count": len(self.event_log)
                    }
                })
                logger.info(f"📜 Sent {len(self.event_log)} historical logs to new client")
            except Exception as e:
                logger.warning(f"Failed to send log history: {e}")
        
    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"🔌 Frontend disconnected. Total active: {len(self.active_connections)}")
            
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast JSON message to all connected clients.
        Also stores loggable events in the event log.
        
        Args:
            message: Dictionary containing event type and payload
        """
        # Basic validation
        if not isinstance(message, dict):
            logger.error(f"Cannot broadcast non-dict message: {message}")
            return
        
        # Store loggable events (exclude high-frequency updates)
        msg_type = message.get('type', '')
        excluded_types = {
            'visibility_sync', 'operator_data_update', 'supervisor_update',
            'maintenance_crew_update', 'shift_status', 'machine_production_update',
            'conveyor_box_update', 'warehouse_update', 'batch_update'
        }
        
        if msg_type and msg_type not in excluded_types:
            log_entry = {
                "id": f"log-{datetime.now().timestamp()}",
                "type": msg_type,
                "data": message.get('data', {}),
                "timestamp": datetime.now().isoformat()
            }
            self.event_log.append(log_entry)
        
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
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs from the event log buffer."""
        logs = list(self.event_log)
        return logs[-limit:] if limit < len(logs) else logs
    
    def clear_logs(self):
        """Clear the event log buffer."""
        self.event_log.clear()
        logger.info("🗑️ Event log cleared")

# Global manager instance
manager = ConnectionManager()

