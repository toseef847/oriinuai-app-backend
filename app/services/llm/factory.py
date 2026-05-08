from app.core.config import settings
from app.services.llm.base import LLMProvider


def get_llm_provider(plan_tier: str = "free") -> LLMProvider:
    provider = settings.LLM_PROVIDER

    if provider == "google_ai_studio":
        from app.services.llm.google_gemma import GoogleGemmaProvider
        model_map = {
            "free":  settings.GEMMA_FREE_MODEL,
            "pro":   settings.GEMMA_PRO_MODEL,
            "elite": settings.GEMMA_ELITE_MODEL,
        }
        return GoogleGemmaProvider(model=model_map.get(plan_tier, settings.GEMMA_FREE_MODEL))

    elif provider == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        model_map = {
            "free":  settings.OPENAI_MINI_MODEL,
            "pro":   settings.OPENAI_MINI_MODEL,
            "elite": settings.OPENAI_FULL_MODEL,
        }
        return OpenAIProvider(model=model_map.get(plan_tier, settings.OPENAI_MINI_MODEL))

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported values: 'google_ai_studio' | 'openai'. "
            f"Note: 'ollama' is not supported."
        )
