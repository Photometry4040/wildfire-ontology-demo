# D-1: Anthropic API 클라이언트 + 프롬프트 캐싱
# 출처: claude-api skill, CLAUDE.md 모델 = claude-sonnet-4-6
#
# 설계 원칙:
#   - ANTHROPIC_API_KEY 없으면 template fallback (데모·테스트 무중단)
#   - system prompt에 cache_control → 반복 호출 비용 절감
#   - 일일 1회 호출 제한 목적의 in-process 캐시
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent.parent.parent / ".env")
except ImportError:
    pass

try:
    from anthropic import Anthropic, APIConnectionError, APIStatusError
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_BRIEFING = 1200
MAX_TOKENS_RETRO    = 1800


class LLMClient:
    """
    Anthropic API 래퍼.
    API 키 없거나 연결 실패 시 template fallback으로 무중단 운영.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client  = None
        if _ANTHROPIC_AVAILABLE and self._api_key:
            self._client = Anthropic(api_key=self._api_key)
        # in-process 결과 캐시 (hash → text)
        self._cache: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = MAX_TOKENS_BRIEFING,
        use_cache: bool = True,
    ) -> tuple[str, bool]:
        """
        LLM 호출.
        반환: (text, from_llm: bool)
          from_llm=True  → 실제 API 응답
          from_llm=False → fallback (API 키 없음 또는 오류)
        """
        cache_key = hashlib.md5(f"{system}{user}".encode()).hexdigest()
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key], True

        if not self._client:
            return "[LLM 미연결: .env에 ANTHROPIC_API_KEY 설정 필요]", False

        try:
            resp = self._client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},  # 프롬프트 캐싱
                    }
                ],
                messages=[{"role": "user", "content": user}],
            )
            text = resp.content[0].text
            if use_cache:
                self._cache[cache_key] = text
            return text, True

        except Exception as e:  # APIConnectionError, APIStatusError 등
            return f"[LLM 오류: {e}]", False


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """싱글톤 LLMClient."""
    return LLMClient()
