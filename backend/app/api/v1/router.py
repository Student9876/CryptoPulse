"""API version 1 consolidated router."""

from fastapi import APIRouter
from app.api.v1.endpoints.analytics import router as analytics_router

api_v1_router = APIRouter()
api_v1_router.include_router(analytics_router)

