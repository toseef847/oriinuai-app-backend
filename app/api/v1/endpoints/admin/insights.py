from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.utils.response import api_success

router = APIRouter()


@router.get("/insights/dashboard")
async def admin_dashboard_insights(_: dict = Depends(require_admin)):
    profiles_res = supabase_admin.table("profiles").select("id").eq("role", "user").execute()
    user_ids = [profile["id"] for profile in (profiles_res.data or []) if profile.get("id")]
    total_users = len(user_ids)

    plan_distribution = {
        "foundation": 0,
        "core": 0,
        "inner_circle": 0,
    }

    free_users = 0
    premium_users = 0
    if user_ids:
        plans_res = supabase_admin.table("plans").select("id, name").execute()
        plan_map = {
            plan["id"]: plan["name"]
            for plan in (plans_res.data or [])
            if plan.get("id") and plan.get("name")
        }

        subs_res = (
            supabase_admin.table("subscriptions")
            .select("user_id, plan_id, updated_at, created_at")
            .in_("user_id", user_ids)
            .order("updated_at", desc=True)
            .order("created_at", desc=True)
            .execute()
        )

        latest_plan_by_user: dict[str, str] = {}
        for subscription in (subs_res.data or []):
            user_id = subscription.get("user_id")
            if not user_id or user_id in latest_plan_by_user:
                continue

            plan_name = plan_map.get(subscription.get("plan_id"), "foundation")
            latest_plan_by_user[user_id] = plan_name if plan_name in plan_distribution else "foundation"

        for plan_name in latest_plan_by_user.values():
            if plan_name in ("core", "inner_circle"):
                premium_users += 1
                plan_distribution[plan_name] += 1

        free_users = total_users - premium_users
        plan_distribution["foundation"] = free_users

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
