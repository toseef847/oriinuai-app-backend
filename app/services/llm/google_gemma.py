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
        response = self.model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str:
        prompt = self._build_prompt(system_prompt, conversation_history, user_message)
        return self.model.generate_content(prompt).text

    def _build_prompt(self, system_prompt: str, history: list[dict], user_message: str) -> str:
        parts = [f"[SYSTEM]\n{system_prompt}\n\n"]
        for msg in history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}\n")
        parts.append(f"User: {user_message}\nAssistant:")
        return "".join(parts)
