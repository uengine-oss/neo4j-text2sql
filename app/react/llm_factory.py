"""
Shared LLM factory for ReAct components.

Centralizes construction of the LLM used by:
- ReactAgent
- ExplainAnalysisGenerator
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.react.gemini_context_cache import GeminiCachedContentManager


@dataclass(frozen=True)
class ReactLLMHandle:
    llm: ChatGoogleGenerativeAI
    cached_content_name: Optional[str] = None

    @property
    def uses_context_cache(self) -> bool:
        return bool(self.cached_content_name)


_cache_manager: Optional[GeminiCachedContentManager] = None


def _get_cache_manager() -> Optional[GeminiCachedContentManager]:
    global _cache_manager
    if _cache_manager is not None:
        return _cache_manager
    api_key = getattr(settings, "google_api_key", "") or ""
    if not api_key.strip():
        return None
    _cache_manager = GeminiCachedContentManager(api_key=api_key)
    return _cache_manager


def create_react_llm(
    *,
    purpose: str,
    thinking_level: str,
    system_prompt: Optional[str] = None,
    allow_context_cache: bool = True,
    include_thoughts: bool = True,
) -> ReactLLMHandle:
    """
    Create the default LLM instance for the ReAct flow.

    NOTE: Centralizing this avoids drift across generators/agents.

    This factory is cached so repeated calls return the same LLM instance
    within the current process.
    """
    cached_content_name: Optional[str] = None
    cache_info: Optional[dict] = None

    if (
        allow_context_cache
        and bool(getattr(settings, "gemini_context_cache_enabled", False))
        and (system_prompt is not None)
        and system_prompt.strip()
    ):
        mgr = _get_cache_manager()
        if mgr is not None:
            cached_content_name, cache_info = mgr.get_or_schedule(
                purpose=purpose,
                model=settings.react_google_llm_model,
                system_prompt=system_prompt,
                ttl_seconds=int(getattr(settings, "gemini_context_cache_ttl_seconds", 3600)),
                refresh_buffer_seconds=int(
                    getattr(settings, "gemini_context_cache_refresh_buffer_seconds", 120)
                ),
                retry_backoff_seconds=int(
                    getattr(settings, "gemini_context_cache_retry_backoff_seconds", 60)
                ),
            )
            if cache_info and cache_info.get("status") in {"not_ready"}:
                # Even if SmartLogger INFO is filtered, this print will surface for ops.
                try:
                    # cache_info contains last_error only; avoid logging full prompt.
                    print(
                        f"[gemini.context_cache.pending] purpose={purpose} model={settings.react_google_llm_model} status={cache_info.get('status')}"
                    )
                except Exception:
                    pass

    llm_kwargs = dict(
        model=settings.react_google_llm_model,
        google_api_key=settings.google_api_key,
        thinking_level=thinking_level,
        include_thoughts=include_thoughts,
    )
    if cached_content_name:
        llm_kwargs["cached_content"] = cached_content_name

    llm = ChatGoogleGenerativeAI(**llm_kwargs)
    # Attach minimal debug info (best-effort; do not rely on attribute existence).
    try:
        setattr(llm, "_gemini_cached_content_name", cached_content_name)
        setattr(llm, "_gemini_cache_info", cache_info)
    except Exception:
        pass
    return ReactLLMHandle(llm=llm, cached_content_name=cached_content_name)


