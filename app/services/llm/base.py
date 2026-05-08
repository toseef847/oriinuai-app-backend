from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMProvider(ABC):

    @abstractmethod
    async def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str: ...
