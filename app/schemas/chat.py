from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

class ChatRenameRequest(BaseModel):
    title: str

class ChatMessageSnapshot(BaseModel):
    role: str
    content: str
    created_at: datetime | None = None

class SharedChatResponse(BaseModel):
    id: UUID
    title: str
    messages: list[ChatMessageSnapshot]
    created_at: datetime
