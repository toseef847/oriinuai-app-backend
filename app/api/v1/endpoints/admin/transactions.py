from fastapi import APIRouter, Depends, Query
from app.core.security import require_admin
from app.db.supabase import supabase_admin, get_public_url
from app.core.config import settings
from app.utils.response import api_success

router = APIRouter()


def _matches_transaction_search(payment: dict, profile: dict, search: str | None) -> bool:
    if not search:
        return True

    normalized = search.strip().lower()
    package_name = payment.get("package_name") or "Unknown"
    return any(
        normalized in field
        for field in (
            str(payment.get("id", "")).lower(),
            str(payment.get("user_id", "")).lower(),
            str(profile.get("id", "")).lower(),
            str(profile.get("full_name", "")).lower(),
            str(profile.get("email", "")).lower(),
            package_name.lower(),
        )
    )


@router.get("/transactions")
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: str | None = None,
    plan: str | None = None,
    status: str | None = None,
    search: str | None = Query(None, min_length=1),
    admin: dict = Depends(require_admin)
):
    # Build base query
    query = supabase_admin.table("payments").select(
        "id, amount_cents, status, created_at, user_id, package_name, billing_interval, period_start, period_end, profiles(id, full_name, email, profile_image_path)"
    )
    
    # Apply filters
    if date_from:
        query = query.gte("created_at", f"{date_from}T00:00:00Z")
    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59Z")
    if status:
        query = query.eq("status", status)
    if user_id:
        query = query.eq("user_id", user_id)

    # Execute query
    result = query.order("created_at", desc=True).execute()
    data = result.data or []
    
    # Format and filter in Python
    transactions = []
    for payment in data:
        profile = payment.get("profiles")
        if not profile:
            continue
            
        package_name = payment.get("package_name") or "Unknown"
        
        # Apply plan filter if provided
        if plan and package_name.lower() != plan.lower():
            continue

        if not _matches_transaction_search(payment, profile, search):
            continue
            
        transaction_data = {
            "id": payment["id"],
            "payment_id": payment["id"],
            "user_id": payment["user_id"],
            "username": profile.get("full_name") or (profile.get("email").split("@")[0] if profile.get("email") else "user"),
            "full_name": profile.get("full_name"),
            "email": profile.get("email"),
            "profile_image_url": get_public_url(
                settings.PROFILE_IMAGE_BUCKET,
                profile.get("profile_image_path"),
            ),
            "package_name": package_name,
            "started_on": payment.get("period_start"),
            "ends_on": payment.get("period_end"),
            "price": (payment.get("amount_cents") or 0) / 100.0,
            "subscription_type": payment.get("billing_interval") or "unknown",
            "status": payment.get("status") or "pending",
            "created_at": payment.get("created_at")
        }
        
        transactions.append(transaction_data)
        
    total = len(transactions)
    
    # Apply pagination offset and limit
    offset = (page - 1) * limit
    paginated_transactions = transactions[offset:offset + limit]
    
    return api_success(data={
        "transactions": paginated_transactions,
        "total": total,
        "page": page,
        "limit": limit
    }, message="Transactions retrieved")
