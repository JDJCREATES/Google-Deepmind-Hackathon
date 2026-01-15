"""
Budget Manager for Gemini API Costs

Monitors daily API spend and enforces budget limits to prevent
runaway costs during live demo.
"""
import json
import os
from datetime import datetime, date
from typing import Dict, Optional
from pathlib import Path


class BudgetManager:
    """
    Manages daily API budget tracking.
    
    Features:
    - Tracks token usage per day
    - Enforces daily spend limit
    - Auto-resets at midnight UTC
    - Persists to disk for restarts
    """
    
    def __init__(self, daily_limit_usd: float = 5.0, data_path: str = "data/budget.json"):
        self.daily_limit_usd = daily_limit_usd
        self.data_path = data_path
        
        # Gemini Flash pricing (as of Jan 2024)
        self.cost_per_1k_input = 0.000075  # $0.075 per 1M tokens
        self.cost_per_1k_output = 0.00030  # $0.30 per 1M tokens
        
        # Create data directory
        os.makedirs(os.path.dirname(data_path) or ".", exist_ok=True)
        
        # Load or initialize budget data
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Load budget data from disk."""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    # Check if we need to reset for new day
                    if data.get("date") != str(date.today()):
                        return self._create_new_day_data()
                    return data
            except Exception as e:
                print(f"Error loading budget data: {e}")
        
        return self._create_new_day_data()
    
    def _create_new_day_data(self) -> Dict:
        """Create fresh budget data for a new day."""
        return {
            "date": str(date.today()),
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "requests": 0,
            "budget_exceeded_at": None
        }
    
    def _save_data(self):
        """Persist budget data to disk."""
        try:
            with open(self.data_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving budget data: {e}")
    
    def record_usage(self, input_tokens: int, output_tokens: int):
        """
        Record token usage and update cost.
        
        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
        """
        # Check if new day
        if self.data.get("date") != str(date.today()):
            self.data = self._create_new_day_data()
        
        # Update counters
        self.data["input_tokens"] += input_tokens
        self.data["output_tokens"] += output_tokens
        self.data["requests"] += 1
        
        # Calculate cost
        input_cost = (input_tokens / 1000) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self.cost_per_1k_output
        self.data["total_cost_usd"] += (input_cost + output_cost)
        
        # Check if we just exceeded budget
        if (not self.data.get("budget_exceeded_at") and 
            self.data["total_cost_usd"] >= self.daily_limit_usd):
            self.data["budget_exceeded_at"] = datetime.now().isoformat()
        
        self._save_data()
    
    def can_make_request(self) -> bool:
        """
        Check if we can make another API request within budget.
        
        Returns:
            True if within budget, False if exceeded
        """
        # Check if new day (auto-reset)
        if self.data.get("date") != str(date.today()):
            self.data = self._create_new_day_data()
            self._save_data()
            return True
        
        return self.data["total_cost_usd"] < self.daily_limit_usd
    
    def get_stats(self) -> Dict:
        """Get current budget statistics."""
        # Check if new day
        if self.data.get("date") != str(date.today()):
            self.data = self._create_new_day_data()
            self._save_data()
        
        return {
            "date": self.data["date"],
            "total_cost_usd": round(self.data["total_cost_usd"], 4),
            "daily_limit_usd": self.daily_limit_usd,
            "remaining_usd": round(self.daily_limit_usd - self.data["total_cost_usd"], 4),
            "input_tokens": self.data["input_tokens"],
            "output_tokens": self.data["output_tokens"],
            "total_tokens": self.data["input_tokens"] + self.data["output_tokens"],
            "requests_made": self.data["requests"],
            "budget_exceeded": not self.can_make_request(),
            "budget_exceeded_at": self.data.get("budget_exceeded_at")
        }


# Global singleton
budget_manager = BudgetManager(daily_limit_usd=5.0)
