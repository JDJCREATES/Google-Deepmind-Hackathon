"""
Production-grade IP-based rate limiter for demo environment.

Tracks:
- Daily simulation time per IP (5 minute limit)
- Inject event cooldown per IP (30 second minimum)
- Auto-resets at midnight UTC
- PERSISTENT across server restarts (saves to rate_limit_state.json)
"""
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path("rate_limit_state.json")

class RateLimiter:
    """
    IP-based rate limiting for simulation usage and event injection.
    
    Thread-safe for single-process deployments. Persistent to JSON file.
    """
    
    # DEV MODE: Whitelist for unlimited testing (only localhost)
    DEV_WHITELIST = {"127.0.0.1"}  # Only your local IP, no remote access
    
    def __init__(self):
        # {ip: {"daily_seconds_used": float, "last_reset": datetime, "last_inject": datetime, "session_start": datetime}}
        self.usage: Dict[str, Dict] = {}
        self.DAILY_LIMIT_SECONDS = 300  # 5 minutes per day
        self.INJECT_COOLDOWN_SECONDS = 30  # 30 seconds between injections
        
        self._load_state()
        
    def _load_state(self):
        """Load state from JSON file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    
                # Reconstruct datetime objects
                for ip, stats in data.items():
                    self.usage[ip] = {
                        "daily_seconds_used": stats.get("daily_seconds_used", 0),
                        "last_reset": datetime.fromisoformat(stats["last_reset"]) if stats.get("last_reset") else datetime.utcnow(),
                        "last_inject": datetime.fromisoformat(stats["last_inject"]) if stats.get("last_inject") else None,
                        "session_start": None
                    }
                logger.info(f"Loaded rate limit state for {len(self.usage)} IPs")
            except Exception as e:
                logger.error(f"Failed to load rate limit state: {e}")

    def _save_state(self):
        """Save state to JSON file."""
        try:
            # Convert datetime to string
            serialize_data = {}
            for ip, stats in self.usage.items():
                serialize_data[ip] = {
                    "daily_seconds_used": stats["daily_seconds_used"],
                    "last_reset": stats["last_reset"].isoformat() if stats.get("last_reset") else None,
                    "last_inject": stats["last_inject"].isoformat() if stats.get("last_inject") else None
                }
            
            with open(STATE_FILE, "w") as f:
                json.dump(serialize_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save rate limit state: {e}")

    def check_daily_limit(self, ip: str) -> Tuple[bool, int]:
        """
        Check if IP has remaining simulation time today.
        
        Returns:
            (can_run, remaining_seconds): Can this IP start/continue simulation?
        """
        # DEV MODE: Bypass for whitelisted IPs (localhost only)
        if ip in self.DEV_WHITELIST:
            logger.info(f"🔓 DEV MODE: IP {ip} has unlimited runtime")
            return (True, 999999)  # Unlimited
        
        self._reset_if_new_day(ip)
        
        used = self.usage.get(ip, {}).get("daily_seconds_used", 0)
        remaining = self.DAILY_LIMIT_SECONDS - used
        
        can_run = remaining > 0
        
        if not can_run:
            logger.warning(f"IP {ip} exceeded daily limit ({used:.1f}/{self.DAILY_LIMIT_SECONDS}s)")
        
        return (can_run, max(0, remaining))
    
    def check_inject_cooldown(self, ip: str) -> Tuple[bool, int]:
        """
        Check if IP can inject an event (30s cooldown).
        
        Returns:
            (can_inject, cooldown_remaining): Can inject? How long to wait?
        """
        # DEV MODE: Bypass for whitelisted IPs
        if ip in self.DEV_WHITELIST:
            return (True, 0)  # No cooldown
        
        if ip not in self.usage:
            return (True, 0)
        
        last_inject = self.usage[ip].get("last_inject")
        
        if not last_inject:
            return (True, 0)
        
        elapsed = (datetime.utcnow() - last_inject).total_seconds()
        cooldown_remaining = max(0, self.INJECT_COOLDOWN_SECONDS - elapsed)
        
        can_inject = cooldown_remaining == 0
        
        if not can_inject:
            logger.debug(f"IP {ip} on inject cooldown ({int(cooldown_remaining)}s remaining)")
        
        return (can_inject, int(cooldown_remaining))
    
    def record_inject(self, ip: str):
        """Mark that this IP just injected an event."""
        self._init_ip_if_needed(ip)
        self.usage[ip]["last_inject"] = datetime.utcnow()
        self._save_state()  # Verify persistence immediately
        logger.info(f"IP {ip} injected event")
    
    def start_session(self, ip: str):
        """Mark simulation start time for accurate tracking."""
        self._init_ip_if_needed(ip)
        self.usage[ip]["session_start"] = datetime.utcnow()
        logger.info(f"IP {ip} started simulation session")
    
    def record_simulation_time(self, ip: str, seconds: float):
        """
        Add simulation runtime to IP's daily usage.
        
        Args:
            ip: Client IP address
            seconds: Number of seconds to add (typically 0.5s per tick)
        """
        self._reset_if_new_day(ip)
        if ip not in self.usage:
            self._init_ip_if_needed(ip)
            
        old_usage = self.usage[ip]["daily_seconds_used"]
        self.usage[ip]["daily_seconds_used"] += seconds
        
        new_usage = self.usage[ip]["daily_seconds_used"]
        
        # Log usage every 30 seconds to keep terminal clean but visible
        if int(new_usage) // 30 != int(old_usage) // 30:
             logger.info(f"⏱️ IP {ip} usage: {new_usage:.1f}/{self.DAILY_LIMIT_SECONDS}s")
             self._save_state() # Save periodically
        
        # Also save if we just crossed the limit to lock it in IMMEDIATELY
        if old_usage < self.DAILY_LIMIT_SECONDS and new_usage >= self.DAILY_LIMIT_SECONDS:
             self._save_state()
    
    def get_usage_stats(self, ip: str) -> Dict:
        """Get current usage stats for an IP."""
        self._reset_if_new_day(ip)
        
        used = self.usage.get(ip, {}).get("daily_seconds_used", 0)
        remaining = max(0, self.DAILY_LIMIT_SECONDS - used)
        
        return {
            "daily_limit_seconds": self.DAILY_LIMIT_SECONDS,
            "used_seconds": used,
            "remaining_seconds": remaining,
            "can_run": remaining > 0,
            "reset_at": self._get_next_reset_time().isoformat()
        }
    
    def _init_ip_if_needed(self, ip: str):
        """Initialize tracking data for new IP."""
        if ip not in self.usage:
            self.usage[ip] = {
                "daily_seconds_used": 0,
                "last_reset": datetime.utcnow(),
                "last_inject": None,
                "session_start": None
            }
    
    def _reset_if_new_day(self, ip: str):
        """Reset usage if it's a new UTC day."""
        if ip in self.usage:
            last_reset = self.usage[ip].get("last_reset", datetime.utcnow())
            current_date = datetime.utcnow().date()
            if isinstance(last_reset, str): # Handle potential string from bad json load
                 last_reset = datetime.fromisoformat(last_reset)
            last_reset_date = last_reset.date()
            
            if current_date > last_reset_date:
                logger.info(f"Resetting daily usage for IP {ip} (new day)")
                self.usage[ip] = {
                    "daily_seconds_used": 0,
                    "last_reset": datetime.utcnow(),
                    "last_inject": self.usage[ip].get("last_inject"),  # Keep inject cooldown
                    "session_start": None
                }
                self._save_state()
    
    def _get_next_reset_time(self) -> datetime:
        """Get next midnight UTC."""
        now = datetime.utcnow()
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, datetime.min.time())


# Singleton instance
rate_limiter = RateLimiter()
