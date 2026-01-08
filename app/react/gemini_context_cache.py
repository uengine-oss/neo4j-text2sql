from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from google import genai
from google.genai.types import CreateCachedContentConfig

from app.smart_logger import SmartLogger


@dataclass
class CacheEntry:
    cache_name: Optional[str] = None
    created_at_epoch: float = 0.0
    expires_at_epoch: float = 0.0
    refresh_at_epoch: float = 0.0

    in_flight: bool = False
    last_error: Optional[str] = None
    last_attempt_epoch: float = 0.0
    next_retry_epoch: float = 0.0


class GeminiCachedContentManager:
    """
    Process-local CachedContent manager (옵션 A).
    - Lazy 생성/갱신은 백그라운드 task로 수행
    - TTL + refresh buffer 적용
    - 실패 시 backoff 후 재시도
    """

    def __init__(self, *, api_key: str):
        self._client = genai.Client(api_key=api_key)
        self._lock = threading.Lock()
        self._entries: dict[str, CacheEntry] = {}

    @staticmethod
    def _fingerprint(*, model: str, system_prompt: str) -> str:
        return hashlib.sha256(f"{model}\n{system_prompt}".encode("utf-8")).hexdigest()

    def get_or_schedule(
        self,
        *,
        purpose: str,
        model: str,
        system_prompt: str,
        ttl_seconds: int,
        refresh_buffer_seconds: int,
        retry_backoff_seconds: int,
    ) -> Tuple[Optional[str], dict[str, Any]]:
        """
        Non-blocking lookup.
        - Returns cache_name if ready and not expired.
        - Schedules background create/refresh when needed (if running loop exists).
        """
        now = time.time()
        ttl_seconds = int(ttl_seconds)
        refresh_buffer_seconds = int(refresh_buffer_seconds)
        retry_backoff_seconds = int(retry_backoff_seconds)

        if ttl_seconds <= 0:
            return None, {"status": "disabled", "reason": "ttl_seconds<=0"}
        if refresh_buffer_seconds < 0:
            refresh_buffer_seconds = 0
        if refresh_buffer_seconds >= ttl_seconds:
            # Keep a minimal safety margin.
            refresh_buffer_seconds = max(0, ttl_seconds - 1)

        fp = self._fingerprint(model=model, system_prompt=system_prompt)
        with self._lock:
            entry = self._entries.get(fp)
            if entry is None:
                entry = CacheEntry()
                self._entries[fp] = entry

            # Valid cache ready
            if entry.cache_name and now < float(entry.expires_at_epoch or 0.0):
                needs_refresh = now >= float(entry.refresh_at_epoch or 0.0)
                if needs_refresh:
                    self._maybe_schedule_background(
                        purpose=purpose,
                        fp=fp,
                        model=model,
                        system_prompt=system_prompt,
                        ttl_seconds=ttl_seconds,
                        refresh_buffer_seconds=refresh_buffer_seconds,
                        retry_backoff_seconds=retry_backoff_seconds,
                        reason="refresh_due",
                    )
                return entry.cache_name, {
                    "status": "ready",
                    "needs_refresh": needs_refresh,
                    "expires_at_epoch": entry.expires_at_epoch,
                    "refresh_at_epoch": entry.refresh_at_epoch,
                }

            # Not ready / expired
            if entry.cache_name and now >= float(entry.expires_at_epoch or 0.0):
                # Expired: clear so we can recreate.
                entry.cache_name = None

            self._maybe_schedule_background(
                purpose=purpose,
                fp=fp,
                model=model,
                system_prompt=system_prompt,
                ttl_seconds=ttl_seconds,
                refresh_buffer_seconds=refresh_buffer_seconds,
                retry_backoff_seconds=retry_backoff_seconds,
                reason="create_needed",
            )
            return None, {
                "status": "not_ready",
                "next_retry_epoch": entry.next_retry_epoch,
                "last_error": entry.last_error,
            }

    def _maybe_schedule_background(
        self,
        *,
        purpose: str,
        fp: str,
        model: str,
        system_prompt: str,
        ttl_seconds: int,
        refresh_buffer_seconds: int,
        retry_backoff_seconds: int,
        reason: str,
    ) -> None:
        now = time.time()
        entry = self._entries[fp]
        if entry.in_flight:
            return
        if entry.next_retry_epoch and now < entry.next_retry_epoch:
            return

        # Best-effort schedule: only if a loop is running
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        entry.in_flight = True
        entry.last_attempt_epoch = now

        async def _runner() -> None:
            try:
                cache_name = await asyncio.to_thread(
                    self._create_cached_content_sync,
                    purpose=purpose,
                    fp=fp,
                    model=model,
                    system_prompt=system_prompt,
                    ttl_seconds=ttl_seconds,
                )
                created_at = time.time()
                expires_at = created_at + float(ttl_seconds)
                refresh_at = created_at + float(max(0, ttl_seconds - refresh_buffer_seconds))
                with self._lock:
                    e = self._entries.get(fp) or CacheEntry()
                    e.cache_name = cache_name
                    e.created_at_epoch = created_at
                    e.expires_at_epoch = expires_at
                    e.refresh_at_epoch = refresh_at
                    e.in_flight = False
                    e.last_error = None
                    e.next_retry_epoch = 0.0
                    self._entries[fp] = e

                SmartLogger.log(
                    "INFO",
                    "gemini.context_cache.ready",
                    category="gemini.context_cache.ready",
                    params={
                        "purpose": purpose,
                        "reason": reason,
                        "model": model,
                        "fingerprint": fp[:12],
                        "cache_name": cache_name,
                        "ttl_seconds": ttl_seconds,
                        "refresh_buffer_seconds": refresh_buffer_seconds,
                    },
                )
                print(
                    f"[gemini.context_cache.ready] purpose={purpose} model={model} fp={fp[:12]} ttl={ttl_seconds}s"
                )
            except Exception as exc:
                err = repr(exc)
                with self._lock:
                    e = self._entries.get(fp) or CacheEntry()
                    e.in_flight = False
                    e.last_error = err
                    e.next_retry_epoch = time.time() + float(max(1, retry_backoff_seconds))
                    self._entries[fp] = e
                SmartLogger.log(
                    "ERROR",
                    "gemini.context_cache.error",
                    category="gemini.context_cache.error",
                    params={
                        "purpose": purpose,
                        "reason": reason,
                        "model": model,
                        "fingerprint": fp[:12],
                        "error": err,
                        "retry_backoff_seconds": retry_backoff_seconds,
                    },
                )
                print(
                    f"[gemini.context_cache.error] purpose={purpose} model={model} fp={fp[:12]} error={err}"
                )

        try:
            loop.create_task(_runner())
        except Exception:
            # If scheduling failed, mark it idle so next request can retry.
            entry.in_flight = False

    def _create_cached_content_sync(
        self,
        *,
        purpose: str,
        fp: str,
        model: str,
        system_prompt: str,
        ttl_seconds: int,
    ) -> str:
        ttl = f"{int(ttl_seconds)}s"
        display_name = f"{purpose}-{fp[:8]}"
        # NOTE: google-genai SDK requires `contents` to be non-empty.
        # We keep a minimal neutral placeholder to satisfy validation.
        dummy_contents = [{"role": "user", "parts": [{"text": "(cache placeholder)"}]}]
        cache = self._client.caches.create(
            model=model,
            config=CreateCachedContentConfig(
                display_name=display_name,
                system_instruction=system_prompt,
                contents=dummy_contents,
                ttl=ttl,
            ),
        )
        # google-genai returns a resource name like: "cachedContents/...."
        return str(cache.name)


