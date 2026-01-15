"""
Session Manager for On-Demand Simulation

Controls when the factory simulation runs to prevent 24/7 API costs.
Allows judges to start sessions on-demand that run for fixed durations.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from app.utils.logging import get_agent_logger

logger = get_agent_logger("SessionManager")


class SessionManager:
    """
    Manages on-demand simulation sessions.
    
    Features:
    - Start/stop simulation sessions
    - Auto-stop after session duration
    - Track active sessions
    """
    
    def __init__(self):
        self.active_session: Optional[str] = None
        self.session_start: Optional[datetime] = None
        self.session_duration_minutes: int = 10  # Default 10-minute sessions
        self._stop_timer: Optional[asyncio.Task] = None
    
    async def start_session(self, duration_minutes: int = None) -> dict:
        """
        Start a new simulation session.
        
        Args:
            duration_minutes: Session duration (defaults to 10 minutes)
            
        Returns:
            Session info dict
        """
        if self.is_active():
            # Extend existing session
            logger.info("🔄 Extending active session")
            return self.get_session_info()
        
        duration = duration_minutes or self.session_duration_minutes
        self.active_session = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_start = datetime.now()
        
        # Import here to avoid circular dependency
        from app.services.simulation import simulation
        
        # Resume simulation if paused
        if hasattr(simulation, 'paused'):
            simulation.paused = False
        
        logger.info(f"▶️ Started session: {self.active_session} (duration: {duration}min)")
        
        # Schedule auto-stop
        self._stop_timer = asyncio.create_task(self._auto_stop_after(duration))
        
        return self.get_session_info()
    
    async def stop_session(self) -> dict:
        """Stop the active session."""
        if not self.is_active():
            return {"status": "no_active_session"}
        
        # Cancel auto-stop timer
        if self._stop_timer and not self._stop_timer.done():
            self._stop_timer.cancel()
        
        session_id = self.active_session
        duration = (datetime.now() - self.session_start).total_seconds() / 60
        
        # Import here to avoid circular dependency
        from app.services.simulation import simulation
        
        # Pause simulation (don't stop completely)
        if hasattr(simulation, 'paused'):
            simulation.paused = True
        
        logger.info(f"⏸️ Stopped session: {session_id} (ran for {duration:.1f}min)")
        
        self.active_session = None
        self.session_start = None
        
        return {
            "status": "stopped",
            "session_id": session_id,
            "duration_minutes": round(duration, 1)
        }
    
    async def _auto_stop_after(self, minutes: int):
        """Auto-stop session after duration."""
        try:
            await asyncio.sleep(minutes * 60)
            logger.info(f"⏰ Session duration reached, auto-stopping")
            await self.stop_session()
        except asyncio.CancelledError:
            pass
    
    def is_active(self) -> bool:
        """Check if a session is currently active."""
        return self.active_session is not None
    
    def get_session_info(self) -> dict:
        """Get current session information."""
        if not self.is_active():
            return {
                "active": False,
                "session_id": None,
                "elapsed_minutes": 0,
                "remaining_minutes": 0
            }
        
        elapsed = (datetime.now() - self.session_start).total_seconds() / 60
        remaining = max(0, self.session_duration_minutes - elapsed)
        
        return {
            "active": True,
            "session_id": self.active_session,
            "started_at": self.session_start.isoformat(),
            "duration_minutes": self.session_duration_minutes,
            "elapsed_minutes": round(elapsed, 1),
            "remaining_minutes": round(remaining, 1)
        }


# Global singleton
session_manager = SessionManager()
