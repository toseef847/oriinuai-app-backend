import asyncio
import google.generativeai as genai
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from app.core.config import settings


class GoogleGemmaProvider(LLMProvider):

    def __init__(self, model: str):
        genai.configure(api_key=settings.GOOGLE_AI_STUDIO_KEY)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

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
                response = self.model.generate_content(prompt, stream=True)
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return  # Success
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 15 # 15s, 30s
                        print(f"Chat rate limit hit. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                raise e

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
                return self.model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 15
                        await asyncio.sleep(wait_time)
                        continue
                raise e

    def _build_prompt(self, system_prompt: str, history: list[dict], user_message: str) -> str:
        parts = [f"[SYSTEM]\n{system_prompt}\n\n"]
        for msg in history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}\n")
        parts.append(f"User: {user_message}\nAssistant:")
        return "".join(parts)
