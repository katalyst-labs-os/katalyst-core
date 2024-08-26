import os
from typing import Optional
from openai import OpenAI


def init_client(llm_api_key: Optional[str] = None) -> OpenAI:
    return OpenAI(
        api_key=(
            llm_api_key if llm_api_key is not None else os.getenv("OPENROUTER_API_KEY")
        ),
        base_url="https://openrouter.ai/api/v1",
        timeout=100,
    )
