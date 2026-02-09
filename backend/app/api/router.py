from fastapi import APIRouter

from app.api.v1 import chat, health, reports, whatsapp

api_router = APIRouter(prefix="/v1")

api_router.include_router(reports.router, tags=["Reports"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(whatsapp.router, tags=["WhatsApp"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
