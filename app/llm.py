"""
LLM client with:
  - Gemini (Google AI Studio) as primary, multiple keys in rotation
  - Groq (Llama 3.3 70B) as fallback, multiple keys in rotation
  - Per-key cooldown on HTTP 429 (60s)
  - Local throttle to stay under free-tier RPM
  - Serialised Gemini calls (google-generativeai uses module-level state)
"""
import asyncio
import logging
import time
from typing import List, Optional

import google.generativeai as genai
from groq import AsyncGroq

from .config import settings

log = logging.getLogger("the_factory.llm")


class KeyPool:
    """Rotating pool of API keys with per-key cooldown."""

    def __init__(self, keys: List[str], cooldown_seconds: int = 60):
        self.keys = [k for k in keys if k]
        self.cooldowns: dict[str, float] = {}
        self.cooldown_seconds = cooldown_seconds
        self._idx = 0
        self._lock = asyncio.Lock()

    async def next(self) -> Optional[str]:
        async with self._lock:
            if not self.keys:
                return None
            now = time.time()
            n = len(self.keys)
            for _ in range(n):
                k = self.keys[self._idx % n]
                self._idx += 1
                if self.cooldowns.get(k, 0) < now:
                    return k
            return None

    async def cool(self, key: str) -> None:
        async with self._lock:
            self.cooldowns[key] = time.time() + self.cooldown_seconds
            log.warning("Key %s...%s cooled down for %ss",
                        key[:6], key[-4:], self.cooldown_seconds)


class Throttle:
    """Simple per-provider minimum-interval rate limiter."""

    def __init__(self, rpm: int):
        self.min_interval = 60.0 / rpm if rpm > 0 else 0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self.min_interval <= 0:
            return
        async with self._lock:
            now = time.time()
            wait = self.min_interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.time()


class LLMClient:
    def __init__(self):
        self.gemini_pool = KeyPool(settings.gemini_keys)
        self.groq_pool = KeyPool(settings.groq_keys)
        self.gemini_throttle = Throttle(rpm=12)
        self.groq_throttle = Throttle(rpm=24)
        self._gemini_lock = asyncio.Lock()
        self._groq_clients: dict[str, AsyncGroq] = {}

    async def complete(self, prompt: str, system: str = "", max_tokens: int = 800) -> str:
        result = await self._try_gemini(prompt, system, max_tokens)
        if result is not None:
            return result
        result = await self._try_groq(prompt, system, max_tokens)
        if result is not None:
            return result
        raise RuntimeError("All LLM providers exhausted or rate-limited.")

    def _gemini_sync(self, key: str, prompt: str, system: str, max_tokens: int) -> str:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=system,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": 0.2,
            },
        )
        resp = model.generate_content(prompt)
        return resp.text if hasattr(resp, "text") else ""

    async def _try_gemini(self, prompt: str, system: str, max_tokens: int) -> Optional[str]:
        while True:
            key = await self.gemini_pool.next()
            if not key:
                return None
            await self.gemini_throttle.acquire()
            try:
                async with self._gemini_lock:
                    text = await asyncio.to_thread(
                        self._gemini_sync, key, prompt, system, max_tokens
                    )
                return text
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate" in msg or "quota" in msg or "resource" in msg:
                    await self.gemini_pool.cool(key)
                    continue
                log.error("Gemini key %s...%s failed: %s", key[:6], key[-4:], e)
                return None

    async def _get_groq_client(self, key: str) -> AsyncGroq:
        if key not in self._groq_clients:
            self._groq_clients[key] = AsyncGroq(api_key=key)
        return self._groq_clients[key]

    async def _try_groq(self, prompt: str, system: str, max_tokens: int) -> Optional[str]:
        while True:
            key = await self.groq_pool.next()
            if not key:
                return None
            await self.groq_throttle.acquire()
            try:
                client = await self._get_groq_client(key)
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                resp = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.2,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate" in msg or "quota" in msg:
                    await self.groq_pool.cool(key)
                    continue
                log.error("Groq key %s...%s failed: %s", key[:6], key[-4:], e)
                return None


llm = LLMClient()
