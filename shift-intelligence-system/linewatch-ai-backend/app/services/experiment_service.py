
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
    
    def __init__(self, data_dir: str = settings.data_dir):
        self.data_dir = data_dir
        
        # Safe initialization for Read-Only environments (Cloud Run)
        try:
             os.makedirs(self.data_dir, exist_ok=True)
             self.db_path = os.path.join(data_dir, "experiment.db")
             self.is_persistent = True
             logger.info(f"✅ ExperimentService persistence enabled at: {self.db_path}")
        except OSError:
             logger.warning("⚠️ Filesystem is read-only. Switching ExperimentService to IN-MEMORY mode.")
             self.db_path = ":memory:"
             self.is_persistent = False
             
        self._table_initialized = False

    def _ensure_data_dir(self):
        if self.is_persistent:
            os.makedirs(self.data_dir, exist_ok=True)

    async def _ensure_table(self, db):
        """Ensure logs table exists and SEED DEMO DATA if empty."""
        if self._table_initialized:
            return

        logger.info(f"💾 ExperimentService accessing DB at: {self.db_path}")

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

    async def log_metric(self, sim_time_hours: float, kpi: dict, fin: dict, state: dict):
        """Log a new data point to the database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await self._ensure_table(db)
                
                # Extract values with safe defaults
                oee = kpi.get('oee', 0.0)
                safety_score = kpi.get('safety_score', 100.0)
                
                revenue = fin.get('total_revenue', 0.0)
                expenses = fin.get('total_expenses', 0.0)
                profit = fin.get('balance', 0.0) # Using balance as profit_cum proxy for now
                if 'net_profit' in fin:
                    profit = fin['net_profit']
                elif 'balance' in fin: 
                     profit = fin['balance']

                active_alerts = len(state.get('active_alerts', []))
                safety_violations = len(state.get('safety_violations', []))
                
                # Mock token stats for now if not tracked
                tokens_in = state.get('agent_tokens_in', 0)
                tokens_out = state.get('agent_tokens_out', 0)
                agent_cost = state.get('agent_cost_est', 0.0)
                
                prod_rate = state.get('production_rate', 0.0)
                inventory = state.get('inventory_level', 0)

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
                    sim_time_hours,
                    oee,
                    safety_score,
                    revenue,
                    expenses,
                    profit,
                    active_alerts,
                    safety_violations,
                    tokens_in,
                    tokens_out,
                    agent_cost,
                    prod_rate,
                    inventory
                ))
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to log experiment metric: {e}")

    async def get_history(self, limit: int = 1000, filename: str = None) -> List[Dict[str, Any]]:
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
        """Return available sessions. Using SQLite DB as 'current' session."""
        sessions = []
        
        # Add current DB session if it exists/has data
        if os.path.exists(self.db_path):
            stats = os.stat(self.db_path)
            sessions.append({
                "filename": "current",
                "created_at": datetime.fromtimestamp(stats.st_ctime).isoformat(),
                "size_bytes": stats.st_size,
                "is_current": True
            })
            
        return sessions

experiment_service = ExperimentService(data_dir=settings.data_dir)
