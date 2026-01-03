
import csv
import os
import aiofiles
from datetime import datetime
from typing import Dict, Any, List

from app.utils.logging import logger
from app.config import settings

class ExperimentService:
    """
    Service for logging high-resolution experiment data for scientific analysis.
    Logs metrics to CSV for portability and performance analysis.
    """
    
    
    def __init__(self, log_dir: str = "data"):
        self.log_dir = log_dir
        # Create unique log file for this session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"experiment_log_{timestamp}.csv")
        self.headers = [
            "timestamp", "sim_time_hours", 
            "oee", "safety_score", 
            "revenue_cum", "expenses_cum", "profit_cum",
            "active_alerts", "safety_incidents",
            "agent_tokens_in", "agent_tokens_out", "agent_cost_est",
            "production_rate_avg", "inventory_level"
        ]
        self._ensure_log_file()
        
    def _ensure_log_file(self):
        """Ensure CSV file exists with headers."""
        os.makedirs(self.log_dir, exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all experiment CSV files in data directory."""
        sessions = []
        try:
            if not os.path.exists(self.log_dir):
                return []
                
            for f in os.listdir(self.log_dir):
                if f.startswith("experiment_log_") and f.endswith(".csv"):
                    path = os.path.join(self.log_dir, f)
                    stat = os.stat(path)
                    sessions.append({
                        "filename": f,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "size_bytes": stat.st_size,
                        "is_current": path == self.log_file
                    })
            
            # Sort by creation time desc
            sessions.sort(key=lambda x: x["created_at"], reverse=True)
            return sessions
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    async def log_tick(self, state: Dict[str, Any]):
        """
        Log a single simulation tick/state snapshot.
        Call this periodically (e.g. every minute or hour of sim time).
        """
        try:
            # Calculate derived metrics
            kpi = state.get("kpi", {})
            fin = state.get("financials", {})
            
            # Estimate Agent Cost ($0.15/1M input, $0.60/1M output - blended estimate)
            # Checking shared_context for token stats would be better, but assuming passed in state for now
            # For hackathon, we assume 'agent_stats' is injected into state or we fetch from shared context
            
            tokens_in = state.get("agent_stats", {}).get("total_tokens_in", 0)
            tokens_out = state.get("agent_stats", {}).get("total_tokens_out", 0)
            agent_cost = (tokens_in / 1_000_000 * 0.15) + (tokens_out / 1_000_000 * 0.60)
            
            row = [
                datetime.now().isoformat(),
                f"{state.get('simulation_hours', 0):.2f}",
                f"{kpi.get('oee', 0):.4f}",
                f"{kpi.get('safety_score', 100):.2f}",
                f"{fin.get('total_revenue', 0):.2f}",
                f"{fin.get('total_expenses', 0):.2f}",
                f"{fin.get('balance', 0):.2f}",
                len(state.get("active_alerts", [])),
                len(state.get("safety_violations", [])),
                tokens_in,
                tokens_out,
                f"{agent_cost:.4f}",
                f"{state.get('production_rate', 0):.2f}",
                sum(state.get('inventory', {}).values())
            ]
            
            async with aiofiles.open(self.log_file, 'a', newline='') as f:
                # simple CSV writing async
                line = ",".join(map(str, row)) + "\n"
                await f.write(line)
                
        except Exception as e:
            logger.error(f"Failed to log experiment metric: {e}")

    async def get_history(self, limit: int = 1000, filename: str = None) -> List[Dict[str, Any]]:
        """
        Get history for frontend graphing.
        If filename is provided, reads that specific file.
        Otherwise reads the current session's log file.
        """
        data = []
        target_file = self.log_file
        
        if filename:
            # Security check
            if "/" in filename or "\\" in filename or not filename.endswith(".csv"):
                 logger.warning(f"Invalid filename request: {filename}")
                 return []
            target_file = os.path.join(self.log_dir, filename)

        try:
            if not os.path.exists(target_file):
                return []
                
            async with aiofiles.open(target_file, 'r') as f:
                content = await f.read()
                lines = content.strip().split('\n')
                
                if len(lines) < 2:
                    return []
                    
                headers = lines[0].split(',')
                # Get last N lines
                for line in lines[-limit:]: 
                    if line == lines[0]: continue # Skip header if gathered
                    
                    values = line.split(',')
                    if len(values) != len(headers): continue
                    
                    item = {}
                    for i, h in enumerate(headers):
                        val = values[i]
                        # Try convert to number
                        try:
                            if '.' in val:
                                item[h] = float(val)
                            else:
                                item[h] = int(val)
                        except:
                            item[h] = val
                    data.append(item)
            return data
            
        except Exception as e:
            logger.error(f"Error reading experiment history: {e}")
            return []

experiment_service = ExperimentService()
