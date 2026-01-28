from fastapi import APIRouter

from app.api.v1 import health, reports

api_router = APIRouter(prefix="/v1")

api_router.include_router(reports.router, tags=["Reports"])
api_router.include_router(health.router, tags=["Health"])
