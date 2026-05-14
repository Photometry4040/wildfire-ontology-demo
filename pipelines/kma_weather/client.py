"""
KMA 기상청 단기예보 + 기상특보 클라이언트
출처: docs/source_inventory.json SOURCE_KMA_SHORT_TERM_FORECAST, SOURCE_KMA_WEATHER_WARNINGS
단기예보 API: https://www.data.go.kr/data/15084084/openapi.do
기상특보 API: https://www.data.go.kr/data/15139476/openapi.do
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    from .grids import GRIDS, UNIQUE_STN_IDS, GridInfo, _BY_SIGUCODE
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from grids import GRIDS, UNIQUE_STN_IDS, GridInfo, _BY_SIGUCODE  # type: ignore

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

API_KEY: str = os.getenv("FORESTRY_API_KEY", "")  # 공공데이터포털 공통 키

FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
WARN_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnList"

# 기상특보 카테고리 → 건조·강풍 여부
_DRY_WARN  = {"건조주의보", "건조경보"}
_WIND_WARN = {"강풍주의보", "강풍경보"}


# ─── 도메인 모델 ─────────────────────────────────────────────

@dataclass
class WeatherForecast:
    sigucode: str    # 시군구 코드
    sigun: str       # 시군구명
    uplocalcd: str   # 광역 구분
    nx: int          # 격자 X
    ny: int          # 격자 Y
    base_date: str   # 예보 기준일 YYYYMMDD
    base_time: str   # 예보 기준시 HHMM
    fcst_date: str   # 예보 대상일 YYYYMMDD
    fcst_time: str   # 예보 대상시 HHMM
    reh: float       # 상대습도 % (실효습도 근사)
    wsd: float       # 풍속 m/s
    vec: int         # 풍향 deg (0=북, 90=동, 180=남, 270=서)
    pcp: float       # 1h 강수량 mm (강수없음=0)
    tmp: float       # 기온 °C
    is_mock: bool


@dataclass
class WeatherWarning:
    stn_id: str      # 관측소 코드
    sigungu: str     # 적용 시군구 (원문)
    warn_var: str    # 특보 종류 (건조경보, 강풍주의보 등)
    warn_str: str    # 특보 강도 문자열
    is_dry: bool     # 건조 특보 여부
    is_wind: bool    # 강풍 특보 여부
    is_mock: bool


# ─── 기준시 계산 ─────────────────────────────────────────────

_VALID_TIMES = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]

def _latest_base_time(now: datetime | None = None) -> tuple[str, str]:
    """현재 시각 기준으로 가장 최근 유효한 (base_date, base_time) 반환."""
    now = now or datetime.now()
    hhmm = now.strftime("%H%M")
    for t in reversed(_VALID_TIMES):
        # API 데이터는 기준시 + 10분 후 제공
        avail = int(t) + 10
        if int(hhmm) >= avail:
            return now.strftime("%Y%m%d"), t
    # 자정 직후 → 전날 2300 사용
    prev = now - timedelta(days=1)
    return prev.strftime("%Y%m%d"), "2300"


# ─── mock 시나리오 ─────────────────────────────────────────────
# 곡성 산불(2025-01-22) 전후 — 건조·강풍 시나리오
# reh=상대습도%, wsd=풍속m/s, vec=풍향deg, pcp=강수mm, tmp=기온°C
_MockWeather = tuple[float, float, int, float, float]  # reh, wsd, vec, pcp, tmp

_WEATHER_SCENARIO: dict[str, dict[str, _MockWeather]] = {
    # sigucode: API verificated 10자리 (2026-05-10)
    "2025-01-20": {
        "4672000000": (35.0, 6.5, 315, 0.0, 3.0),   # 곡성 (API:46720)
        "4671000000": (38.0, 5.8, 310, 0.0, 2.5),   # 담양
        "4673000000": (40.0, 5.2, 320, 0.0, 2.0),   # 구례 (API:46730)
    },
    "2025-01-21": {
        "4672000000": (28.0, 9.2, 315, 0.0, 1.5),   # 곡성: 습도↓ 강풍↑
        "4671000000": (30.0, 8.5, 310, 0.0, 1.0),   # 담양
        "4673000000": (32.0, 7.8, 320, 0.0, 0.5),   # 구례
        "4679000000": (35.0, 7.0, 300, 0.0, 2.0),   # 화순 (API:46790)
    },
    "2025-01-22": {                                   # 산불 당일
        "4672000000": (22.0, 12.5, 315, 0.0, 0.5),  # 곡성 ★ 건조경보·강풍경보
        "4671000000": (24.0, 11.8, 310, 0.0, 0.0),  # 담양
        "4673000000": (26.0, 10.5, 320, 0.0, -0.5), # 구례
        "4679000000": (28.0,  9.8, 305, 0.0,  1.0), # 화순
        "4678000000": (30.0,  8.5, 300, 0.0,  1.5), # 보성 (API:46780)
    },
    "2025-01-23": {                                   # 다음날
        "4672000000": (45.0, 5.0, 270, 2.5, 3.0),   # 곡성: 비 + 풍속↓
        "4671000000": (48.0, 4.5, 260, 1.5, 2.5),   # 담양
    },
}

_WARN_SCENARIO: dict[str, list[tuple[str, str, str]]] = {
    # date → list of (stn_id, warn_var, warn_str)
    "2025-01-21": [("192", "건조주의보", "전라남도 동부"),
                   ("192", "강풍주의보", "전라남도 동부")],
    "2025-01-22": [("192", "건조경보",  "전라남도 동부"),
                   ("192", "강풍경보",  "전라남도 동부"),
                   ("156", "건조주의보", "광주·전남 서부")],
}


def _mock_weather(sigucode: str, date: str) -> _MockWeather:
    """시나리오에 없는 시군구: 결정적 해시로 평범한 값 생성."""
    h = lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16)
    reh = 50 + (h(f"{sigucode}{date}reh") % 30)  # 50~79%
    wsd = 2.0 + (h(f"{sigucode}{date}wsd") % 40) / 10  # 2.0~5.9 m/s
    vec = (h(f"{sigucode}{date}vec") % 8) * 45   # 0,45,90,135,180,225,270,315
    pcp = 0.0
    tmp = 5 + (h(f"{sigucode}{date}tmp") % 15)   # 5~19°C
    return (float(reh), wsd, vec, pcp, float(tmp))


def _build_mock_weather(date: str) -> list[WeatherForecast]:
    scenario = _WEATHER_SCENARIO.get(date, {})
    base_date = date.replace("-", "")
    results: list[WeatherForecast] = []
    for g in GRIDS:
        reh, wsd, vec, pcp, tmp = scenario.get(g.sigucode) or _mock_weather(g.sigucode, date)
        results.append(WeatherForecast(
            sigucode=g.sigucode, sigun=g.sigun, uplocalcd=g.uplocalcd,
            nx=g.nx, ny=g.ny,
            base_date=base_date, base_time="0800",
            fcst_date=base_date, fcst_time="1200",
            reh=reh, wsd=wsd, vec=vec, pcp=pcp, tmp=tmp,
            is_mock=True,
        ))
    return results


def _build_mock_warnings(date: str) -> list[WeatherWarning]:
    return [
        WeatherWarning(stn_id=sid, sigungu=area, warn_var=var, warn_str=area,
                       is_dry=(var in _DRY_WARN), is_wind=(var in _WIND_WARN),
                       is_mock=True)
        for sid, var, area in _WARN_SCENARIO.get(date, [])
    ]


# ─── 실제 API 호출 ─────────────────────────────────────────────

async def _fetch_fcst_for(grid: GridInfo, base_date: str, base_time: str) -> list[dict]:
    """단일 격자 단기예보 → 항목 리스트."""
    params = {
        "ServiceKey": API_KEY,
        "pageNo": "1", "numOfRows": "300", "dataType": "JSON",
        "base_date": base_date, "base_time": base_time,
        "nx": str(grid.nx), "ny": str(grid.ny),
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(FCST_URL, params=params)
        r.raise_for_status()
    body = r.json()
    items = body.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    return items if isinstance(items, list) else [items]


def _extract_weather(items: list[dict], grid: GridInfo,
                     base_date: str, base_time: str) -> WeatherForecast | None:
    """첫 번째 예보 시각의 REH/WSD/VEC/PCP/TMP 추출."""
    # items는 여러 예보 시각 × 카테고리의 혼합
    # 가장 이른 fcstDate+fcstTime 기준으로 추출
    by_time: dict[tuple[str, str], dict[str, str]] = {}
    for it in items:
        key = (it.get("fcstDate", ""), it.get("fcstTime", ""))
        by_time.setdefault(key, {})[it.get("category", "")] = it.get("fcstValue", "0")

    if not by_time:
        return None

    first_key = sorted(by_time.keys())[0]
    cats = by_time[first_key]

    def _float(cat: str) -> float:
        v = cats.get(cat, "0")
        if isinstance(v, str):
            v = v.replace("강수없음", "0").replace("mm미만", "0").strip()
            v = v.split("~")[0].replace("<", "").strip()
        try:
            return float(v)
        except ValueError:
            return 0.0

    return WeatherForecast(
        sigucode=grid.sigucode, sigun=grid.sigun, uplocalcd=grid.uplocalcd,
        nx=grid.nx, ny=grid.ny,
        base_date=base_date, base_time=base_time,
        fcst_date=first_key[0], fcst_time=first_key[1],
        reh=_float("REH"), wsd=_float("WSD"),
        vec=int(_float("VEC")), pcp=_float("PCP"), tmp=_float("TMP"),
        is_mock=False,
    )


async def _fetch_warnings() -> list[WeatherWarning]:
    """광주·전남 관련 기상특보 조회."""
    warnings: list[WeatherWarning] = []
    for stn_id in UNIQUE_STN_IDS:
        params = {"ServiceKey": API_KEY, "pageNo": "1", "numOfRows": "20",
                  "dataType": "JSON", "stnId": stn_id}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(WARN_URL, params=params)
            r.raise_for_status()
        body = r.json()
        rc = body.get("response", {}).get("header", {}).get("resultCode", "99")
        if rc != "00":
            continue
        items = body.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not isinstance(items, list):
            items = [items]
        for it in items:
            var = it.get("warnVar", "")
            warnings.append(WeatherWarning(
                stn_id=stn_id,
                sigungu=it.get("sigungu", ""),
                warn_var=var,
                warn_str=it.get("warnStr", ""),
                is_dry=(var in _DRY_WARN),
                is_wind=(var in _WIND_WARN),
                is_mock=False,
            ))
    return warnings


# ─── 공개 인터페이스 ──────────────────────────────────────────

class KmaWeatherClient:
    async def fetch_forecasts(self, date: str,
                              force_mock: bool = False) -> list[WeatherForecast]:
        """광주·전남 전체 단기예보. date='YYYY-MM-DD'."""
        if not API_KEY or force_mock:
            return _build_mock_weather(date)

        base_date, base_time = _latest_base_time()

        # 병렬 호출 (격자별)
        tasks = [_fetch_fcst_for(g, base_date, base_time) for g in GRIDS]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        forecasts: list[WeatherForecast] = []
        for g, raw in zip(GRIDS, results_raw):
            if isinstance(raw, Exception):
                continue
            wf = _extract_weather(raw, g, base_date, base_time)
            if wf:
                forecasts.append(wf)
        return forecasts

    async def fetch_warnings(self, date: str,
                             force_mock: bool = False) -> list[WeatherWarning]:
        """광주·전남 기상특보 조회."""
        if not API_KEY or force_mock:
            return _build_mock_warnings(date)
        return await _fetch_warnings()


# ─── CLI ──────────────────────────────────────────────────────

async def _main() -> None:
    parser = argparse.ArgumentParser(description="기상청 단기예보·기상특보 조회")
    parser.add_argument("--date",  default="2025-01-22", help="조회 날짜 YYYY-MM-DD")
    parser.add_argument("--mock",  action="store_true",  help="mock 모드 강제")
    args = parser.parse_args()

    client = KmaWeatherClient()
    use_mock = args.mock or not API_KEY
    forecasts = await client.fetch_forecasts(args.date, force_mock=use_mock)
    warnings  = await client.fetch_warnings(args.date,  force_mock=use_mock)

    mode = "MOCK" if use_mock else "REAL API"
    print(f"\n[{args.date}] 기상청 단기예보 ({mode}) — {len(forecasts)}개 시군구\n")
    print(f"{'시군구':<10} {'습도%':>6} {'풍속':>5} {'풍향':>5} {'강수':>5} {'기온':>5}")
    print("─" * 42)
    for f in sorted(forecasts, key=lambda x: x.reh):
        flag = " ★" if (f.reh < 30 and f.wsd >= 9) else ""
        print(f"{f.sigun:<10} {f.reh:>6.1f} {f.wsd:>5.1f} {f.vec:>5} {f.pcp:>5.1f} {f.tmp:>5.1f}{flag}")

    if warnings:
        print(f"\n기상특보 {len(warnings)}건:")
        for w in warnings:
            print(f"  [{w.stn_id}] {w.warn_var} — {w.sigungu}")
    else:
        print("\n기상특보: 없음")


if __name__ == "__main__":
    asyncio.run(_main())
