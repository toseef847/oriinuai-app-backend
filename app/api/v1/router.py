from fastapi import APIRouter
from app.api.v1.endpoints import auth, chat, plans, payments, users
from app.api.v1.endpoints.admin.router import router as admin_router

api_router = APIRouter()
api_router.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
api_router.include_router(chat.router,     prefix="",          tags=["Chat"])
api_router.include_router(plans.router,    prefix="/plans",    tags=["Plans"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"])
api_router.include_router(users.router,    prefix="/users",    tags=["Users"])
api_router.include_router(admin_router,    prefix="/admin",    tags=["Admin"])
