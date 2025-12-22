"""FastAPI application entry point for LineWatch AI backend."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.utils.logging import setup_logging, get_agent_logger

# Initialize logging
setup_logging()
logger = get_agent_logger("SYSTEM")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("🚀 LineWatch AI Backend starting...")
    logger.info(f"📊 Department: {settings.department_name}")
    logger.info(f"🏭 Production Lines: {settings.num_production_lines}")
    logger.info(f"🤖 Gemini Model: {settings.gemini_model}")
    
    # TODO: Initialize agents here
    # TODO: Start simulation
    
    yield
    
    # Shutdown
    logger.info("👋 LineWatch AI Backend shutting down...")
    # TODO: Cleanup agents


# Create FastAPI app
app = FastAPI(
    title="LineWatch AI Backend",
    description="Production-grade shift intelligence multi-agent system",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with system info."""
    return {
        "service": "LineWatch AI Backend",
        "version": "0.1.0",
        "status": "operational",
        "department": settings.department_name,
        "lines": settings.num_production_lines,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# TODO: Add API routers
# - /api/department
# - /api/agents
# - /api/alerts
# - /ws/stream (WebSocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=True,
    )
