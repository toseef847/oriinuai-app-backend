from pydantic import BaseModel
from uuid import UUID


class PlanResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    daily_message_limit: int
    rag_chunks: int
    llm_tier: str
    stripe_monthly_price_id: str | None = None
    stripe_yearly_price_id: str | None = None
