"""Multi-provider LLM service abstraction.

Supports: Groq, OpenAI, Google (Gemini)
"""
import logging
from functools import lru_cache
from typing import Literal

from langchain_core.language_models import BaseChatModel

from app.config import get_settings

logger = logging.getLogger(__name__)

LLMProvider = Literal["groq", "openai", "google"]


def get_llm(
    model: str | None = None,
    provider: LLMProvider | None = None,
    temperature: float = 0.0,
) -> BaseChatModel:
    """Get an LLM instance for the configured provider.

    Args:
        model: Model name. If None, uses LLM_ANALYSIS_MODEL from settings.
        provider: Provider name. If None, uses LLM_PROVIDER from settings.
        temperature: Temperature for generation (default 0.0 for determinism).

    Returns:
        BaseChatModel instance for the provider.
    """
    settings = get_settings()
    provider = provider or settings.llm_provider
    model = model or settings.llm_analysis_model
    api_key = settings.llm_api_key

    if not api_key or api_key in ("placeholder", "your-api-key-here", "your-groq-api-key-here"):
        raise ValueError(
            f"LLM API key not configured. Set LLM_API_KEY in .env for provider '{provider}'."
        )

    logger.info(f"Creating LLM: provider={provider}, model={model}")

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. Supported: groq, openai, google."
        )


def get_validation_llm(temperature: float = 0.0) -> BaseChatModel:
    """Get the LLM configured for pre-validation (cheap/fast model)."""
    settings = get_settings()
    return get_llm(
        model=settings.llm_validation_model,
        provider=settings.llm_provider,
        temperature=temperature,
    )


def get_analysis_llm(temperature: float = 0.0) -> BaseChatModel:
    """Get the LLM configured for main analysis (smart model)."""
    settings = get_settings()
    return get_llm(
        model=settings.llm_analysis_model,
        provider=settings.llm_provider,
        temperature=temperature,
    )


def get_translation_llm(temperature: float = 0.0) -> BaseChatModel:
    """Get the LLM configured for translation (configurable, defaults to 8B)."""
    settings = get_settings()
    return get_llm(
        model=settings.llm_translation_model,
        provider=settings.llm_provider,
        temperature=temperature,
    )
