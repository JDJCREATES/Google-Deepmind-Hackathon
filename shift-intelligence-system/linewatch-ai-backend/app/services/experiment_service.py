
import csv
import os
import aiofiles
from datetime import datetime
from typing import Dict, Any, List

from app.utils.logging import logger
from app.config import settings

import csv
import os
import aiofiles
import aiosqlite
from datetime import datetime
from typing import Dict, Any, List

from app.utils.logging import logger
from app.config import settings

class ExperimentService:
    """
    Service for logging high-resolution experiment data to SQLite.
    Supports on-demand CSV export.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "experiment.db")
        self._ensure_data_dir()
        self._table_initialized = False

    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)

    async def _ensure_table(self, db):
        """Ensure logs table exists."""
        if self._table_initialized:
            return
            
        await db.execute("""
            CREATE TABLE IF NOT EXISTS experiment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sim_time_hours REAL,
                oee REAL,
                safety_score REAL,
                revenue_cum REAL,
                expenses_cum REAL,
                profit_cum REAL,
                active_alerts INTEGER,
                safety_incidents INTEGER,
                agent_tokens_in INTEGER,
                agent_tokens_out INTEGER,
                agent_cost_est REAL,
                production_rate_avg REAL,
                inventory_level INTEGER
            )
        """)
        await db.commit()
        self._table_initialized = True

    async def log_tick(self, state: Dict[str, Any]):
        """Log a single simulation tick metrics to DB."""
        try:
            kpi = state.get("kpi", {})
            fin = state.get("financials", {})
            stats = state.get("agent_stats", {})
            
            # Derived metrics
            tokens_in = stats.get("total_tokens_in", 0)
            tokens_out = stats.get("total_tokens_out", 0)
            agent_cost = (tokens_in / 1_000_000 * 0.15) + (tokens_out / 1_000_000 * 0.60)
            inventory = sum(state.get('inventory', {}).values())
            
            async with aiosqlite.connect(self.db_path) as db:
                await self._ensure_table(db)
                
                await db.execute("""
                    INSERT INTO experiment_logs (
                        timestamp, sim_time_hours, oee, safety_score,
                        revenue_cum, expenses_cum, profit_cum,
                        active_alerts, safety_incidents,
                        agent_tokens_in, agent_tokens_out, agent_cost_est,
                        production_rate_avg, inventory_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    state.get('simulation_hours', 0),
                    kpi.get('oee', 0),
                    kpi.get('safety_score', 100),
                    fin.get('total_revenue', 0),
                    fin.get('total_expenses', 0),
                    fin.get('balance', 0),
                    len(state.get("active_alerts", [])),
                    len(state.get("safety_violations", [])),
                    tokens_in,
                    tokens_out,
                    agent_cost,
                    state.get('production_rate', 0),
                    inventory
                ))
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to log experiment metric: {e}")

    async def get_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get recent history for frontend."""
        data = []
        try:
            if not os.path.exists(self.db_path):
                return []
                
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM experiment_logs 
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                rows = await cursor.fetchall()
                
                # Convert to dict and match frontend expected format (reverse to chronological)
                for row in reversed(rows):
                    data.append(dict(row))
                    
            return data
        except Exception as e:
            logger.error(f"Error reading history: {e}")
            return []

    async def export_csv(self) -> str:
        """
        Export all DB logs to a CSV file on demand and return filepath.
        User can then download this file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"experiment_export_{timestamp}.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM experiment_logs ORDER BY id ASC")
                rows = await cursor.fetchall()
                
                if not rows:
                    return ""
                    
                headers = rows[0].keys()
                
                # Write to CSV
                async with aiofiles.open(filepath, 'w', newline='') as f:
                    # Write header
                    await f.write(",".join(headers) + "\n")
                    
                    # Write rows
                    for row in rows:
                        values = [str(row[k]) for k in headers]
                        await f.write(",".join(values) + "\n")
                        
            logger.info(f"✅ Experiment data exported to {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return ""

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Mock compatibility for now, or list exports."""
        # For now, just return empty or list exports if we want
        # The frontend might expect this method to exist
        return []

experiment_service = ExperimentService()
