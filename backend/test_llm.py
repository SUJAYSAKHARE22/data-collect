import asyncio
import sys
from app.agents.llm_provider import KimiProvider
from app.config.settings import get_settings

async def main():
    settings = get_settings()
    print("API Key:", settings.kimi_api_key)
    print("Base URL:", settings.kimi_base_url)
    print("Model:", settings.kimi_model)
    provider = KimiProvider(
        api_key=settings.kimi_api_key,
        base_url=settings.kimi_base_url,
        model=settings.kimi_model,
        timeout_seconds=20.0,
        max_retries=0,
    )
    try:
        res = await provider.complete([{"role": "user", "content": "Hello"}], json_mode=False)
        print("Success without json_mode:", res.content)
    except Exception as e:
        print("Failed without json_mode:", e)

    try:
        res = await provider.complete([{"role": "user", "content": "Hello. Response in JSON: {\\\"reply\\\": \\\"hello\\\"}"}], json_mode=True)
        print("Success with json_mode:", res.content)
    except Exception as e:
        print("Failed with json_mode:", e)

if __name__ == "__main__":
    asyncio.run(main())
