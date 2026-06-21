from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.utils.response import api_success

router = APIRouter()


@router.get("/insights/dashboard")
async def admin_dashboard_insights(_: dict = Depends(require_admin)):
    # 1. Total users
    profiles_res = supabase_admin.table("profiles").select("id").eq("role", "user").execute()
    total_users = len(profiles_res.data) if profiles_res.data else 0

    # 2. Plan mapping & distribution
    plans_res = supabase_admin.table("plans").select("id, name").execute()
    plan_map = {p["id"]: p["name"] for p in plans_res.data} if plans_res.data else {}

    subs_res = supabase_admin.table("subscriptions").select("plan_id").execute()
    plan_distribution = {
        "foundation": 0,
        "core": 0,
        "inner_circle": 0
    }
    for sub in (subs_res.data or []):
        plan_name = plan_map.get(sub["plan_id"])
        if plan_name:
            plan_distribution[plan_name] = plan_distribution.get(plan_name, 0) + 1

    free_users = plan_distribution.get("foundation", 0)
    premium_users = plan_distribution.get("core", 0) + plan_distribution.get("inner_circle", 0)

    # 3. Earnings & Earnings over time
    payments_res = supabase_admin.table("payments").select("amount_cents, created_at").eq("status", "paid").execute()
    total_earnings = 0.0
    earnings_by_month = {}
    
    for p in (payments_res.data or []):
        cents = p.get("amount_cents") or 0
        total_earnings += cents / 100.0
        
        created_at = p.get("created_at")
        period = created_at[:7] if created_at else "unknown"
        earnings_by_month[period] = earnings_by_month.get(period, 0.0) + cents / 100.0

    earnings_over_time = [
        {"period": k, "amount": round(v, 2)}
        for k, v in sorted(earnings_by_month.items(), reverse=True)
    ]

    # 4. Recent users
    recent_res = supabase_admin.table("profiles").select("id, email, full_name, created_at").eq("role", "user").order("created_at", desc=True).limit(6).execute()
    recent_users = recent_res.data or []

    data = {
        "total_users": total_users,
        "free_users": free_users,
        "premium_users": premium_users,
        "total_earnings": round(total_earnings, 2),
        "plan_distribution": plan_distribution,
        "earnings_over_time": earnings_over_time,
        "recent_users": recent_users
    }

    return api_success(data=data, message="Dashboard metrics retrieved")
