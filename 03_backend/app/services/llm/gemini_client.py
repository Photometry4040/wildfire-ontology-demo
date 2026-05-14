# Gemini LLM 클라이언트 (우선 LLM, Anthropic fallback)
# SDK: google-genai (구 google-generativeai 교체)
# 모델: gemini-2.0-flash — 빠르고 한국어 우수
from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent.parent.parent / ".env")
except ImportError:
    pass

try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

# gemini-2.0-flash: 무료 15 RPM / 1500 RPD — 브리핑 호출 빈도에 적합
# gemini-2.5-flash-lite: 20 RPM이나 일일 할당량 소진 빠름 → fallback 모델
MODEL         = "gemini-2.0-flash"
MODEL_FALLBACK = "gemini-2.5-flash-lite"

# 출력 제어: 1200 토큰 (파이프라인 4섹션 표 포함), temperature=0.3
_GEN_CFG = {"max_output_tokens": 1200, "temperature": 0.3}


class GeminiClient:
    """
    Google Gemini API 래퍼 (google-genai SDK).
    - generate_async: asyncio.to_thread()로 FastAPI blocking 방지
    - GOOGLE_API_KEY 없거나 오류 시 fallback 텍스트 반환
    """

    def __init__(self) -> None:
        from .prompts import SYSTEM_PROMPT  # 지연 import (순환 참조 방지)

        key = os.getenv("GOOGLE_API_KEY", "")
        self._available = bool(key and _GENAI_AVAILABLE)
        self._system    = SYSTEM_PROMPT

        if self._available:
            self._client = genai.Client(api_key=key)

    @property
    def available(self) -> bool:
        return self._available

    def _call(self, user: str) -> str:
        """동기 Gemini 호출 (asyncio.to_thread에서 실행)."""
        config = genai_types.GenerateContentConfig(
            system_instruction=self._system,
            max_output_tokens=_GEN_CFG["max_output_tokens"],
            temperature=_GEN_CFG["temperature"],
        )
        response = self._client.models.generate_content(
            model=MODEL,
            contents=user,
            config=config,
        )
        return response.text

    def _call_model(self, user: str, model: str) -> str:
        """지정 모델로 동기 Gemini 호출."""
        config = genai_types.GenerateContentConfig(
            system_instruction=self._system,
            max_output_tokens=_GEN_CFG["max_output_tokens"],
            temperature=_GEN_CFG["temperature"],
        )
        response = self._client.models.generate_content(
            model=model, contents=user, config=config,
        )
        return response.text

    async def generate_async(self, user: str, retries: int = 1) -> tuple[str, bool]:
        """
        비동기 Gemini 호출.
        - 1차: gemini-2.0-flash
        - 429/503 → gemini-2.5-flash-lite fallback (모델 전환)
        반환: (text, from_llm: bool)
        """
        if not self._available:
            return "[Gemini 미연결: .env에 GOOGLE_API_KEY 설정 필요]", False

        for model in (MODEL, MODEL_FALLBACK):
            try:
                text = await asyncio.to_thread(self._call_model, user, model)
                return text, True
            except Exception as e:
                err_str = str(e)
                is_quota = ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                            or "503" in err_str or "UNAVAILABLE" in err_str)
                if is_quota:
                    continue   # 다음 모델로 재시도
                return f"[Gemini 오류: {e}]", False

        return "[Gemini 할당량 초과 — 잠시 후 새로고침하세요]", False


@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    """싱글톤 GeminiClient."""
    return GeminiClient()
