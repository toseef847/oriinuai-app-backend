from fastapi import APIRouter, Depends, Query
from app.core.security import require_admin
from app.db.supabase import supabase_admin, get_signed_url
from app.core.config import settings
from app.utils.response import api_success

router = APIRouter()


@router.get("/transactions")
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: str | None = None,
    plan: str | None = None,
    status: str | None = None,
    admin: dict = Depends(require_admin)
):
    # Build base query
    query = supabase_admin.table("payments").select(
        "id, amount_cents, status, created_at, user_id, profiles(id, full_name, email, profile_image_path, subscriptions(id, billing_interval, created_at, current_period_end, plans(display_name)))"
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
            
        # Get latest subscription
        subscription = None
        if profile.get("subscriptions") and len(profile["subscriptions"]) > 0:
            subscription = profile["subscriptions"][0]
            
        package_name = subscription.get("plans", {}).get("display_name", "Foundation") if subscription else "Foundation"
        
        # Apply plan filter if provided
        if plan and package_name.lower() != plan.lower():
            continue
            
        transaction_data = {
            "id": payment["id"],
            "payment_id": payment["id"],
            "user_id": payment["user_id"],
            "username": profile.get("full_name") or (profile.get("email").split("@")[0] if profile.get("email") else "user"),
            "full_name": profile.get("full_name"),
            "email": profile.get("email"),
            "profile_image_url": get_signed_url(
                settings.PROFILE_IMAGE_BUCKET,
                profile.get("profile_image_path"),
                expires_in=3600 * 24
            ),
            "package_name": package_name,
            "started_on": subscription.get("created_at") if subscription else None,
            "ends_on": subscription.get("current_period_end") if subscription else None,
            "price": (payment.get("amount_cents") or 0) / 100.0,
            "subscription_type": subscription.get("billing_interval", "free") if subscription else "free",
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
