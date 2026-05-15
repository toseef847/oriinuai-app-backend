from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.utils.response import api_success

router = APIRouter()


@router.get("/insights")
async def admin_insights(_: dict = Depends(require_admin)):
    return api_success(data={"status": "insights placeholder"}, message="Insights retrieved successfully")
