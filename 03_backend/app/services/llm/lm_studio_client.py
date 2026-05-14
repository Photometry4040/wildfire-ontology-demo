# LM Studio 로컬 LLM 클라이언트
# LM Studio는 OpenAI 호환 API를 제공 (/v1/chat/completions)
# httpx로 직접 호출 (openai SDK 불필요)
#
# .env 설정:
#   LM_STUDIO_BASE_URL=http://127.0.0.1:1234
#   LM_STUDIO_MODEL=google/gemma-4-e4b
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
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_BASE_URL_DEFAULT = "http://127.0.0.1:1234"
_MODEL_DEFAULT    = "google/gemma-4-e4b"
_TIMEOUT          = 120.0  # 로컬 LLM은 reasoning 포함 시 느릴 수 있음
_MAX_TOKENS       = 4096   # 로컬 실행 → 비용 없음, reasoning 토큰 포함해서 넉넉하게


def _normalize_base_url(url: str) -> str:
    """http://host:port 또는 http://host:port/v1 → http://host:port 로 통일."""
    url = url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url


class LMStudioClient:
    """
    LM Studio 로컬 LLM 래퍼 (OpenAI 호환 /v1/chat/completions).

    - BASE_URL / MODEL은 .env 또는 기본값 사용
    - 연결 실패 시 (from_llm=False) 반환 — 무중단
    - 토큰 제한 없음 (로컬), temperature=0.3
    """

    def __init__(self) -> None:
        from .prompts import SYSTEM_PROMPT
        self._system   = SYSTEM_PROMPT
        self._base_url = _normalize_base_url(
            os.getenv("LM_STUDIO_BASE_URL", _BASE_URL_DEFAULT)
        )
        self._model    = os.getenv("LM_STUDIO_MODEL", _MODEL_DEFAULT)
        # 항상 {base_url}/v1/chat/completions — /v1 중복 방지
        self._endpoint  = f"{self._base_url}/v1/chat/completions"
        self._available = _HTTPX_AVAILABLE

    @property
    def available(self) -> bool:
        return self._available

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    def _call(self, user: str, max_tokens: int = _MAX_TOKENS) -> str:
        """동기 httpx 호출 (asyncio.to_thread에서 실행).

        max_tokens는 reasoning + 실제 출력 합산 기준.
        로컬 실행이므로 4096으로 넉넉하게 설정해 잘림 방지.
        """
        payload = {
            "model":       self._model,
            "messages": [
                {"role": "system", "content": self._system},
                {"role": "user",   "content": user},
            ],
            "max_tokens":  max_tokens,
            "temperature": 0.3,
            "stream":      False,
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(self._endpoint, json=payload)
            resp.raise_for_status()
            data     = resp.json()
            choice   = data["choices"][0]
            msg      = choice["message"]
            finish   = choice.get("finish_reason", "")

            # reasoning 모델: content가 비어있고 reasoning_content에 실제 답이 있는 경우 대비
            text = msg.get("content") or msg.get("reasoning_content") or ""

            if finish == "length":
                text += "\n\n> ⚠️ *응답이 max_tokens 한도로 잘렸습니다. LM Studio max_tokens 설정을 확인하세요.*"

            return text

    async def generate_async(self, user: str, max_tokens: int = _MAX_TOKENS) -> tuple[str, bool]:
        """
        비동기 LM Studio 호출 (reasoning 토큰 포함 4096 기본).
        반환: (text, from_llm: bool)
        """
        if not self._available:
            return "[LM Studio 미연결: httpx 패키지 필요]", False

        try:
            text = await asyncio.to_thread(self._call, user, max_tokens)
            return text, True
        except httpx.ConnectError:
            return f"[LM Studio 연결 실패: {self._base_url} — 서버 기동 여부 확인]", False
        except httpx.TimeoutException:
            return f"[LM Studio 타임아웃: {_TIMEOUT}초 초과 — 모델 로드 여부 확인]", False
        except Exception as e:
            return f"[LM Studio 오류: {e}]", False

    async def health_check(self) -> dict:
        """LM Studio 서버 상태 확인 (/v1/models)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/v1/models")
                resp.raise_for_status()
                models = [m["id"] for m in resp.json().get("data", [])]
                return {
                    "status":      "connected",
                    "base_url":    self._base_url,
                    "model":       self._model,
                    "loaded_models": models,
                }
        except Exception as e:
            return {
                "status":   "disconnected",
                "base_url": self._base_url,
                "error":    str(e),
            }


@lru_cache(maxsize=1)
def get_lm_studio_client() -> LMStudioClient:
    """싱글톤 LMStudioClient."""
    return LMStudioClient()
