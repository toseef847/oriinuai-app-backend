from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def payments_health():
    return {"status": "payments endpoint placeholder"}
