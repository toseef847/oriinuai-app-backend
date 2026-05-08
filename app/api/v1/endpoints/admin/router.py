from fastapi import APIRouter
from app.api.v1.endpoints.admin import books, users, plans, insights

router = APIRouter()
router.include_router(books.router, prefix="", tags=["Admin Books"])
router.include_router(users.router, prefix="", tags=["Admin Users"])
router.include_router(plans.router, prefix="", tags=["Admin Plans"])
router.include_router(insights.router, prefix="", tags=["Admin Insights"])
