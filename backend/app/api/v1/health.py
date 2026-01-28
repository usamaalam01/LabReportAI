from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return JSONResponse(
        content={"status": "healthy", "service": "labreportai"},
    )
