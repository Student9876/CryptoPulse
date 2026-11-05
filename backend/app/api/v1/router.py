"""API version 1 consolidated router."""

from fastapi import APIRouter
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.history import router as history_router
from app.api.v1.endpoints.rules import router as rules_router

api_v1_router = APIRouter()
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(rules_router)
api_v1_router.include_router(history_router)

