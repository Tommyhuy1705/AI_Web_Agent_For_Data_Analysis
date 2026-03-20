"""
Centralized LLM Client
Provides a single AsyncOpenAI-compatible client for all LLM calls.
Supports Qwen (DashScope), OpenAI, and other OpenAI-compatible providers.

Priority: DASHSCOPE_API_KEY → OPENAI_API_KEY
"""

import logging
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ── Provider detection ──────────────────────────────────────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# DashScope (Qwen) configuration
DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen3.5-122b-a10b")

# OpenAI configuration
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def _detect_provider() -> tuple[str, str, str, str]:
    """Detect which LLM provider to use based on available API keys.
    Returns: (provider_name, api_key, base_url, default_model)
    """
    if DASHSCOPE_API_KEY:
        logger.info("LLM Provider: Qwen (DashScope)")
        return "dashscope", DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, DASHSCOPE_MODEL
    elif OPENAI_API_KEY:
        logger.info("LLM Provider: OpenAI")
        return "openai", OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
    else:
        logger.warning("No LLM API key found! Set DASHSCOPE_API_KEY or OPENAI_API_KEY.")
        return "none", "", OPENAI_BASE_URL, OPENAI_MODEL


PROVIDER, _API_KEY, _BASE_URL, DEFAULT_MODEL = _detect_provider()

# ── Shared client instance ──────────────────────────────────────────
client = AsyncOpenAI(
    api_key=_API_KEY,
    base_url=_BASE_URL,
) if _API_KEY else None

# ── Whether to disable thinking (for Qwen 3.5 to save tokens) ──────
DISABLE_THINKING = PROVIDER == "dashscope"


async def chat_completion(
    messages: list,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1000,
    response_format: dict | None = None,
) -> str:
    """
    Unified chat completion call.
    Automatically handles provider-specific params (e.g. enable_thinking for Qwen).

    Returns: The assistant message content string.
    """
    if client is None:
        raise RuntimeError("No LLM provider configured. Set DASHSCOPE_API_KEY or OPENAI_API_KEY.")

    model = model or DEFAULT_MODEL

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if response_format:
        kwargs["response_format"] = response_format

    # Qwen-specific: disable thinking to save tokens
    if DISABLE_THINKING:
        kwargs["extra_body"] = {"enable_thinking": False}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def get_model() -> str:
    """Return the default model name for the current provider."""
    return DEFAULT_MODEL


def get_provider() -> str:
    """Return the current provider name."""
    return PROVIDER


def is_configured() -> bool:
    """Check if any LLM provider is configured."""
    return client is not None
