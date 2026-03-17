"""Health check routes."""
from fastapi import APIRouter, Depends

from src.api.state import app_state

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check database
    db_status = "connected" if app_state.task_store else "disconnected"

    # Check KR
    kr_status = "ready" if app_state.kite_runner else "not_ready"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "kite_runner": kr_status,
        "version": "0.1.0",
    }
