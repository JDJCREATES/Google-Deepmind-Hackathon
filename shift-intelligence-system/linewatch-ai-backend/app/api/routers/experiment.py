from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import List, Dict, Any
import os

from app.services.experiment_service import experiment_service
from app.utils.logging import logger

router = APIRouter(prefix="/experiment", tags=["experiment"])

@router.get("/sessions")
async def list_experiment_sessions() -> List[Dict[str, Any]]:
    """List all available experiment sessions (CSV files)."""
    return experiment_service.list_sessions()

@router.get("/stats")
async def get_experiment_stats(limit: int = 1000, filename: str = None) -> List[Dict[str, Any]]:
    """
    Get historical metrics for the experiment dashboard.
    Optionally specify filename to view past run.
    """
    try:
        data = await experiment_service.get_history(limit, filename)
        return data
    except Exception as e:
        logger.error(f"Error fetching experiment stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download")
async def download_experiment_csv(filename: str = None):
    """
    Download the experiment log as CSV.
    Optionally specify filename.
    """
    log_file = experiment_service.log_file
    if filename:
        # Security check logic duplicated here or rely on service if we refactor,
        # but FileResponse needs path.
        if "/" in filename or "\\" in filename or not filename.endswith(".csv"):
             raise HTTPException(status_code=400, detail="Invalid filename")
        log_file = os.path.join(experiment_service.log_dir, filename)

    if not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="No experiment data log found")
    
    return FileResponse(
        path=log_file, 
        filename=filename or "linewatch_experiment_data.csv", 
        media_type='text/csv'
    )
