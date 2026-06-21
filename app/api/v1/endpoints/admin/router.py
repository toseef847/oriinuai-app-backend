from fastapi import APIRouter
from app.api.v1.endpoints.admin import auth, books, users, plans, insights, profile, transactions

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["Admin Auth"])
router.include_router(books.router, prefix="", tags=["Admin Books"])
router.include_router(users.router, prefix="", tags=["Admin Users"])
router.include_router(plans.router, prefix="", tags=["Admin Plans"])
router.include_router(insights.router, prefix="", tags=["Admin Insights"])
router.include_router(profile.router, prefix="", tags=["Admin Profile"])
router.include_router(transactions.router, prefix="", tags=["Admin Transactions"])
