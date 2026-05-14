"""
산림청 OFFICIAL_FIRE_RISK_FORECAST API 클라이언트
출처: docs/source_inventory.json SOURCE_OFFICIAL_FIRE_RISK_FORECAST
API 신청: https://www.data.go.kr/data/15084817/openapi.do
오퍼레이션: forestPointListSigunguSearchV2
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .cache import ForecastCache
    from .regions import SIGUNGU, TARGET_UPLOCALCD
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from cache import ForecastCache  # type: ignore
    from regions import SIGUNGU, TARGET_UPLOCALCD  # type: ignore

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

# 시군구 단위 오퍼레이션 URL (확인됨 2026-05-10)
API_URL = "https://apis.data.go.kr/1400377/forestPointV2/forestPointListSigunguSearchV2"
API_KEY: str = os.getenv("FORESTRY_API_KEY", "")


# ─── 도메인 모델 ──────────────────────────────────────────────

@dataclass
class FireRiskForecast:
    sigun: str        # 시군구명 ("곡성군")
    sigucode: str     # 5자리 지역코드 ("46730")
    uplocalcd: str    # 광역 구분 ("29"=광주, "46"=전남)
    analdate: str     # 분석기준일시 ("2026-05-10 21")
    d1: int           # 1등급(낮음) 격자 비율 % — d1+d2+d3+d4 = 100
    d2: int           # 2등급(보통) 격자 비율 %
    d3: int           # 3등급(높음) 격자 비율 %
    d4: int           # 4등급(매우높음) 격자 비율 %
    maxi: int         # 최고 위험지수 (0~100 연속값)
    meanavg: int      # 평균 위험지수
    mini: int         # 최저 위험지수
    is_mock: bool     # mock fallback 여부


# ─── mock 시나리오 ─────────────────────────────────────────────
# 곡성 산불(2025-01-22) 전후 회고 검증용
# d1~d4 = 각 등급 격자 비율 %, 합=100
# maxi/meanavg/mini = 위험지수 (0~100)
# 출처: MVP_PLAN.md §Phase D 회고 검증
_MockRaw = tuple[int, int, int, int, int, int, int]  # d1,d2,d3,d4,maxi,mean,mini

_MOCK_SCENARIO: dict[str, dict[str, _MockRaw]] = {
    # code5 = API sigucode 5자리 (verificated 2026-05-10)
    "2025-01-20": {  # 이틀 전 — 보통 위험
        "46720": (40, 35, 20,  5, 72, 55, 30),  # 곡성 API:46720
        "46710": (50, 30, 15,  5, 68, 50, 28),  # 담양 API:46710
        "46730": (55, 30, 12,  3, 65, 48, 25),  # 구례 API:46730
        "46790": (60, 28, 10,  2, 62, 45, 22),  # 화순 API:46790
    },
    "2025-01-21": {  # 전날 — 위험 급상승
        "46720": (15, 20, 40, 25, 88, 72, 50),  # 곡성 ★
        "46710": (20, 25, 38, 17, 84, 68, 45),  # 담양
        "46730": (25, 30, 33, 12, 80, 62, 40),  # 구례
        "46790": (30, 30, 30, 10, 77, 58, 38),  # 화순
        "46780": (35, 33, 25,  7, 73, 55, 35),  # 보성 API:46780
    },
    "2025-01-22": {  # 산불 당일 — 최고 위험
        "46720": ( 5, 15, 45, 35, 94, 80, 60),  # 곡성 ★★
        "46710": (10, 18, 43, 29, 90, 76, 55),  # 담양
        "46730": (12, 22, 42, 24, 86, 72, 50),  # 구례
        "46790": (15, 25, 40, 20, 83, 68, 47),  # 화순
        "46780": (20, 28, 38, 14, 79, 63, 43),  # 보성
        "46770": (25, 32, 33, 10, 75, 58, 38),  # 고흥 API:46770
    },
    "2025-01-23": {  # 다음날 — 진화 중, 위험 잔존
        "46720": (20, 30, 35, 15, 82, 65, 45),  # 곡성
        "46710": (25, 32, 33, 10, 78, 60, 40),  # 담양
    },
}


def _mock_index(sigucode: str, date: str, seed: int) -> int:
    """시나리오 없는 시군구: 결정적 해시로 낮은 위험 지수 생성."""
    h = int(hashlib.md5(f"{sigucode}{date}{seed}".encode()).hexdigest(), 16)
    return (h % 40) + 10  # 10~49 (낮음 구간)


def _build_mock(date: str) -> list[FireRiskForecast]:
    """날짜 기준 광주·전남 전체 mock 예보 생성."""
    scenario = _MOCK_SCENARIO.get(date, {})
    results: list[FireRiskForecast] = []
    for sigucode, (sigun, uplocalcd) in SIGUNGU.items():
        # regions.py의 sigucode는 10자리, API의 regioncode는 5자리
        code5 = sigucode[:5]  # "4673000000" → "46730"
        if code5 in scenario:
            d1, d2, d3, d4, maxi, mean, mini = scenario[code5]
        else:
            maxi = _mock_index(sigucode, date, 0)
            mean = max(5, maxi - 15)
            mini = max(1, mean - 15)
            d1 = 80 + (int(hashlib.md5(f"{sigucode}{date}d1".encode()).hexdigest(), 16) % 20)
            d1 = min(d1, 100)
            d2 = 100 - d1
            d3, d4 = 0, 0
        results.append(FireRiskForecast(
            sigun=sigun, sigucode=sigucode, uplocalcd=uplocalcd,
            analdate=date.replace("-", " ") + " 00",
            d1=d1, d2=d2, d3=d3, d4=d4,
            maxi=maxi, meanavg=mean, mini=mini,
            is_mock=True,
        ))
    return results


# ─── 실제 API 호출 ────────────────────────────────────────────

async def _fetch_api_for(uplocalcd: str) -> list[ET.Element]:
    """단일 광역코드(29 또는 46) → XML item 요소 리스트."""
    params = {
        "ServiceKey": API_KEY,
        "numOfRows": "100",
        "pageNo":    "1",
        "upplocalcd": uplocalcd,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(API_URL, params=params)
        resp.raise_for_status()
    root = ET.fromstring(resp.text)
    return root.findall(".//item")


def _elem(item: ET.Element, tag: str, default: str = "") -> str:
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else default


def _parse_items(items: list[ET.Element]) -> list[FireRiskForecast]:
    """XML item 요소 → FireRiskForecast."""
    results: list[FireRiskForecast] = []
    for item in items:
        results.append(FireRiskForecast(
            sigun    = _elem(item, "sigun"),
            sigucode = _elem(item, "sigucode"),
            uplocalcd= _elem(item, "upplocalcd"),
            analdate = _elem(item, "analdate"),
            d1       = int(_elem(item, "d1",  "0")),
            d2       = int(_elem(item, "d2",  "0")),
            d3       = int(_elem(item, "d3",  "0")),
            d4       = int(_elem(item, "d4",  "0")),
            maxi     = int(_elem(item, "maxi",    "0")),
            meanavg  = int(_elem(item, "meanavg", "0")),
            mini     = int(_elem(item, "mini",    "0")),
            is_mock  = False,
        ))
    return results


# ─── 공개 인터페이스 ──────────────────────────────────────────

class FireRiskClient:
    def __init__(self, use_cache: bool = True):
        self._cache = ForecastCache() if use_cache else None

    async def fetch(self, date: str, force_mock: bool = False) -> list[FireRiskForecast]:
        """
        date: 'YYYY-MM-DD' (실 API는 date 파라미터 미지원 — 현재 예보만 반환)
        API 키 없거나 force_mock=True면 mock 반환.
        """
        if not API_KEY or force_mock:
            return _build_mock(date)

        cache_key = f"forecast:{date}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return [FireRiskForecast(**r) for r in cached]

        # 광주(29) + 전남(46) 병렬 호출
        gwangju, jeonnam = await asyncio.gather(
            _fetch_api_for("29"),
            _fetch_api_for("46"),
        )
        forecasts = _parse_items(gwangju + jeonnam)

        if self._cache and forecasts:
            self._cache.set(cache_key, [asdict(f) for f in forecasts])

        return forecasts

    def close(self) -> None:
        if self._cache:
            self._cache.close()


# ─── CLI ──────────────────────────────────────────────────────

async def _main() -> None:
    parser = argparse.ArgumentParser(description="산림청 산불위험예보 조회")
    parser.add_argument("--date",  default="2025-01-22", help="조회 날짜 YYYY-MM-DD")
    parser.add_argument("--mock",  action="store_true",  help="mock 모드 강제")
    args = parser.parse_args()

    client = FireRiskClient()
    use_mock = args.mock or not API_KEY
    forecasts = await client.fetch(args.date, force_mock=use_mock)
    client.close()

    mode = "MOCK" if use_mock else "REAL API"
    print(f"\n[{args.date}] 산불위험예보 ({mode}) — 광주·전남 {len(forecasts)}개 시군구")
    print(f"\n  등급비율(%): d1=낮음 d2=보통 d3=높음 d4=매우높음 | 지수=maxi(0~100)\n")
    print(f"{'시군구':<10} {'d1':>4} {'d2':>4} {'d3':>4} {'d4':>4} {'지수':>5}")
    print("─" * 38)
    for f in sorted(forecasts, key=lambda x: (-x.maxi, -x.d4)):
        flag = " ★" if f.d4 >= 20 or f.maxi >= 85 else ""
        print(f"{f.sigun:<10} {f.d1:>4} {f.d2:>4} {f.d3:>4} {f.d4:>4} {f.maxi:>5}{flag}")


if __name__ == "__main__":
    asyncio.run(_main())
