import asyncio
import logging
from typing import AsyncGenerator

from google import genai

from app.services.llm.base import LLMProvider
from app.services.llm.google_errors import FriendlyGoogleError, translate_google_error
from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleGemmaProvider(LLMProvider):

    def __init__(self, model: str):
        self.client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_KEY)
        self.model_name = model

    async def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]:
        prompt = self._build_prompt(system_prompt, conversation_history, user_message)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                stream = await self.client.aio.models.generate_content_stream(
                    model=self.model_name,
                    contents=prompt,
                )
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return  # Success
            except Exception as e:
                error_message = str(e).lower()
                if (
                    "429" in error_message
                    or "quota" in error_message
                    or "exhausted" in error_message
                ):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 15  # 15s, 30s
                        print(f"Chat rate limit hit. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                logger.exception("Google generation stream failed")
                raise FriendlyGoogleError(translate_google_error(e)) from e

    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str:
        prompt = self._build_prompt(system_prompt, conversation_history, user_message)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                return response.text or ""
            except Exception as e:
                error_message = str(e).lower()
                if (
                    "429" in error_message
                    or "quota" in error_message
                    or "exhausted" in error_message
                ):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 15
                        await asyncio.sleep(wait_time)
                        continue
                logger.exception("Google generation request failed")
                raise FriendlyGoogleError(translate_google_error(e)) from e

    def _build_prompt(
        self, system_prompt: str, history: list[dict], user_message: str
    ) -> str:
        parts = [f"[SYSTEM]\n{system_prompt}\n\n"]
        for msg in history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}\n")
        parts.append(f"User: {user_message}\nAssistant:")
        return "".join(parts)
