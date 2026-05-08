from fastapi import APIRouter, Depends
from app.core.security import require_admin

router = APIRouter()


@router.get("/insights")
async def admin_insights(_: dict = Depends(require_admin)):
    return {"status": "insights placeholder"}
