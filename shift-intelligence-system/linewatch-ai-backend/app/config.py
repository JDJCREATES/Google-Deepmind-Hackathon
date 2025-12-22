"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Gemini 3 API Configuration
    google_api_key: str
    gemini_model: str = "gemini-3.0-flash-exp"  # Gemini 3.0 Flash (experimental)
    
    # FastAPI Configuration
    frontend_url: str = "http://localhost:5173"
    api_port: int = 8000
    
    # Department Configuration
    department_name: str = "Production Floor Alpha"
    num_production_lines: int = 20
    
    # Agent Reasoning Intervals (seconds)
    production_agent_interval: int = 30
    compliance_agent_interval: int = 300  # 5 minutes
    staffing_agent_interval: int = 180    # 3 minutes
    maintenance_agent_interval: int = 60
    analytics_agent_interval: int = 120   # 2 minutes
    
    # Simulation Settings
    simulation_speed: float = 1.0
    event_probability_bottleneck: float = 0.05
    event_probability_breakdown: float = 0.02
    event_probability_safety_violation: float = 0.03
    
    @property
    def cors_origins(self) -> List[str]:
        """Allowed CORS origins for frontend."""
        return [self.frontend_url, "http://localhost:3000"]


# Global settings instance
settings = Settings()
