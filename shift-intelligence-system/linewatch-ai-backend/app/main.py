"""FastAPI application entry point for LineWatch AI backend."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.utils.logging import setup_logging, get_agent_logger

# Initialize logging
setup_logging()
logger = get_agent_logger("SYSTEM")

from app.services.simulation import simulation

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("🚀 LineWatch AI Backend starting...")
    logger.info(f"📊 Department: {settings.department_name}")
    logger.info(f"🏭 Production Lines: {settings.num_production_lines}")
    logger.info(f"🤖 Gemini Model: {settings.gemini_model}")  # Using gemini-3-flash-preview
    
    # STRICT API KEY CHECK - System will not work without it
    if not settings.google_api_key:
        logger.error("❌ GOOGLE_API_KEY is not set! The system requires a valid API key to function.")
        logger.error("❌ Please set GOOGLE_API_KEY in your .env file and restart.")
        raise RuntimeError("GOOGLE_API_KEY is required. No fake AI data allowed - only simulated input data is mocked.")
    else:
        logger.info("✅ GOOGLE_API_KEY is configured")
    
    # Initialize agents
    # In a real app we'd load agent instances here if they needed persistence
    
    # Start Simulation Service
    # Note: Simulation starts in "stopped" state, waits for API call
    # await simulation.start()  # Uncomment to auto-start
    
    yield
    
    # Shutdown
    logger.info("👋 LineWatch AI Backend shutting down...")
    await simulation.stop()


# Create FastAPI app
app = FastAPI(
    title="LineWatch AI Backend",
    description="Production-grade shift intelligence multi-agent system",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
# Configure CORS - RELAXED FOR DEVELOPMENT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins to fix 403 Forbidden in dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
from app.api.routers import simulation as sim_router
from app.api.routers import human as human_router
from app.api.routers import hypothesis as hypo_router
from app.api.routers import graph as graph_router

app.include_router(sim_router.router, prefix="/api")
app.include_router(human_router.router, prefix="/api")
app.include_router(hypo_router.router, prefix="/api")
app.include_router(graph_router.router)


@app.get("/")
async def root():
    """Root endpoint with system info."""
    return {
        "service": "LineWatch AI Backend",
        "version": "0.1.0",
        "status": "operational",
        "department": settings.department_name,
        "lines": settings.num_production_lines,
        "simulation": "active" if simulation.is_running else "stopped"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# WebSocket Endpoint
from app.services.websocket import manager

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for client messages (heartbeats)
            data = await websocket.receive_text()
            # Echo or process if needed
            # await websocket.send_text(f"Message received: {data}")
    except Exception:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=True,
    )
