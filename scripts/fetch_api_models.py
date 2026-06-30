# PYTHONPATH=. python3 scripts/fetch_api_models.py
import asyncio

from dotenv import load_dotenv
from google import genai
from openai import AsyncOpenAI

from app.core.config import settings

load_dotenv()


async def list_google_models():
    print("--- Google AI Studio Models ---")
    if not settings.GOOGLE_AI_STUDIO_KEY:
        print("❌ GOOGLE_AI_STUDIO_KEY not found in config.")
        return

    try:
        client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_KEY)
        for m in client.models.list():
            if "generateContent" in (m.supported_actions or []):
                print(f"Model: {m.name}")
                print(f"  - Display Name: {m.display_name}")
                print(f"  - Description: {m.description}")
        print()
    except Exception as e:
        print(f"❌ Error fetching Google models: {e}\n")


async def list_openai_models():
    print("--- OpenAI Models ---")
    if not settings.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not found in config.")
        return

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        models = await client.models.list()
        # Sort and filter for chat models usually
        for m in sorted(models.data, key=lambda x: x.id):
            if "gpt" in m.id:
                print(f"Model: {m.id}")
        print()
    except Exception as e:
        print(f"❌ Error fetching OpenAI models: {e}\n")


async def main():
    print("Fetching available models from APIs...\n")
    await list_google_models()
    await list_openai_models()


if __name__ == "__main__":
    asyncio.run(main())
