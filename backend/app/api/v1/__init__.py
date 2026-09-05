from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.auth import router as auth_router
from app.api.v1.consumer import router as consumer_router
from app.api.v1.health import router as health_router
from app.api.v1.inspections import router as inspections_router
from app.api.v1.notices import router as notices_router
from app.api.v1.products import router as products_router
from app.api.v1.rules import router as rules_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(products_router)
api_router.include_router(inspections_router)
api_router.include_router(notices_router)
api_router.include_router(rules_router)
api_router.include_router(users_router)
api_router.include_router(analytics_router)
api_router.include_router(consumer_router)
api_router.include_router(assistant_router)

