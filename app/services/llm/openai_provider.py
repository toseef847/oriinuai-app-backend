from openai import AsyncOpenAI
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from app.core.config import settings


class OpenAIProvider(LLMProvider):

    def __init__(self, model: str):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model

    async def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        stream = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages
        )
        return response.choices[0].message.content
