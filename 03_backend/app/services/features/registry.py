# Feature dispatch registry + 시군구 단위 일괄 실행
# 출처: docs/05_feature-contract.md §Feature Summary
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from pipelines.fire_risk_forecast.client import FireRiskForecast
from pipelines.kma_weather.client import WeatherForecast, WeatherWarning
from .base import FeatureResult
from .official_risk import fire_risk_level, fire_risk_trend, large_fire_risk_alert
from .exposure import (
    ResidentialExposureInput, CriticalAssetInput, ForestInterfaceInput,
    residential_exposure, critical_asset, forest_interface,
    get_mock_residential, get_mock_critical_asset, get_mock_forest_interface,
)
from .spread import (
    WindTowardAssetInput, TerrainTowardAssetInput, FuelContinuityInput,
    wind_toward_asset, terrain_toward_asset, fuel_continuity,
    get_mock_wind, get_mock_terrain, get_mock_fuel,
)
from .time_urgency import (
    HighRiskTimeWindowInput, RainOffsetInput,
    high_risk_time_window, rain_offset,
    get_mock_time_window, get_mock_rain_offset,
)


def _to_row(res: FeatureResult) -> dict:
    return {
        "feature":    res.feature,
        "sigucode":   res.sigucode,
        "sigun":      res.sigun,
        "score":      res.score,
        "class":      res.cls,
        "mock_input": res.mock_input,
        "confidence": res.confidence,
    }


def run_official_risk(
    forecasts: list[FireRiskForecast],
    weather_map: dict[str, WeatherForecast] | None = None,
    warnings: list[WeatherWarning] | None = None,
) -> list[dict]:
    """
    B-1 OfficialRiskSignal 3 Feature 일괄 실행.
    forecasts: 산림청 시군구별 예보
    weather_map: sigucode → WeatherForecast
    warnings: 기상특보 리스트
    반환: Feature 결과 dict 리스트 (sigucode별 3행)
    """
    weather_map = weather_map or {}
    warnings    = warnings    or []
    results: list[dict] = []

    for f in forecasts:
        wf = weather_map.get(f.sigucode)
        for r in (fire_risk_level(f), fire_risk_trend(f), large_fire_risk_alert(f, wf, warnings)):
            results.append(_to_row(r))
    return results


def run_exposure(
    residential: list[ResidentialExposureInput] | None = None,
    assets: list[CriticalAssetInput] | None = None,
    interfaces: list[ForestInterfaceInput] | None = None,
) -> list[dict]:
    """
    B-2 ExposureSignal 3 Feature 일괄 실행.
    입력 없으면 mock 데이터 자동 사용.
    반환: Feature 결과 dict 리스트 (sigucode별 3행)
    """
    residential = residential or get_mock_residential()
    assets      = assets      or get_mock_critical_asset()
    interfaces  = interfaces  or get_mock_forest_interface()

    asset_map = {c.sigucode: c for c in assets}
    iface_map = {fi.sigucode: fi for fi in interfaces}

    results: list[dict] = []
    for r in residential:
        rows = [residential_exposure(r)]
        if c := asset_map.get(r.sigucode):
            rows.append(critical_asset(c))
        if fi := iface_map.get(r.sigucode):
            rows.append(forest_interface(fi))
        results.extend(_to_row(res) for res in rows)
    return results


def run_spread(
    winds: list[WindTowardAssetInput] | None = None,
    terrains: list[TerrainTowardAssetInput] | None = None,
    fuels: list[FuelContinuityInput] | None = None,
) -> list[dict]:
    """
    B-3 SpreadToAssetSignal 3 Feature 일괄 실행.
    입력 없으면 mock 데이터 자동 사용.
    반환: Feature 결과 dict 리스트 (sigucode별 3행)
    """
    winds    = winds    or get_mock_wind()
    terrains = terrains or get_mock_terrain()
    fuels    = fuels    or get_mock_fuel()

    terrain_map = {t.sigucode: t for t in terrains}
    fuel_map    = {fc.sigucode: fc for fc in fuels}

    results: list[dict] = []
    for w in winds:
        rows = [wind_toward_asset(w)]
        if t := terrain_map.get(w.sigucode):
            rows.append(terrain_toward_asset(t))
        if fc := fuel_map.get(w.sigucode):
            rows.append(fuel_continuity(fc))
        results.extend(_to_row(res) for res in rows)
    return results


def run_time_urgency(
    time_windows: list[HighRiskTimeWindowInput] | None = None,
    rain_offsets: list[RainOffsetInput] | None = None,
) -> list[dict]:
    """
    B-4 TimeUrgencySignal Feature 일괄 실행.
    입력 없으면 mock 데이터 자동 사용.
    반환: Feature 결과 dict 리스트 (sigucode별 2행)
    """
    time_windows = time_windows or get_mock_time_window()
    rain_offsets = rain_offsets or get_mock_rain_offset()

    rain_map = {r.sigucode: r for r in rain_offsets}

    results: list[dict] = []
    for tw in time_windows:
        rows = [high_risk_time_window(tw)]
        if ro := rain_map.get(tw.sigucode):
            rows.append(rain_offset(ro))
        results.extend(_to_row(res) for res in rows)
    return results


# ─── B-1 mock Feature rows ───────────────────────────────────
# API 없이 C-1 테스트용 mock.
# ★ 곡성군(4672000000): 2025-01-22 산불 시나리오 — 최고 위험 수준
#
# 컬럼: (sigucode, sigun, level_score, trend_score, alert_score)
_OFFICIAL_MOCK: list[tuple] = [
    # 광주 — 도심, 위험 보통
    ("2911000000", "동구",    0.40, 0.45, 0.00),
    ("2914000000", "서구",    0.40, 0.45, 0.00),
    ("2915500000", "남구",    0.45, 0.50, 0.00),
    ("2917000000", "북구",    0.55, 0.55, 0.00),
    ("2920000000", "광산구",  0.55, 0.60, 0.00),
    # 전남 시
    ("4611000000", "목포시",  0.60, 0.65, 0.00),
    ("4613000000", "여수시",  0.55, 0.60, 0.00),
    ("4615000000", "순천시",  0.60, 0.65, 0.00),
    ("4617000000", "나주시",  0.55, 0.55, 0.00),
    ("4623000000", "광양시",  0.55, 0.60, 0.00),
    # 전남 군 — 산간 내륙
    ("4671000000", "담양군",  0.65, 0.65, 0.00),
    ("4672000000", "곡성군",  0.75, 0.65, 0.60),  # ★ 높음+주의보
    ("4673000000", "구례군",  0.70, 0.65, 0.60),
    ("4677000000", "고흥군",  0.55, 0.55, 0.00),
    ("4678000000", "보성군",  0.55, 0.60, 0.00),
    ("4679000000", "화순군",  0.65, 0.65, 0.00),
    ("4680000000", "장흥군",  0.50, 0.50, 0.00),
    ("4681000000", "강진군",  0.50, 0.50, 0.00),
    ("4682000000", "해남군",  0.60, 0.65, 0.00),
    ("4683000000", "영암군",  0.55, 0.60, 0.00),
    ("4684000000", "무안군",  0.55, 0.55, 0.00),
    ("4686000000", "함평군",  0.50, 0.55, 0.00),
    ("4687000000", "영광군",  0.55, 0.60, 0.00),
    ("4688000000", "장성군",  0.60, 0.65, 0.00),
    ("4689000000", "완도군",  0.50, 0.55, 0.00),
    ("4690000000", "진도군",  0.55, 0.60, 0.00),
    ("4691000000", "신안군",  0.50, 0.55, 0.00),
]


def get_mock_official_features() -> list[dict]:
    """B-1 OfficialRisk 3 Feature mock rows (API 없이 C-1 테스트용)."""
    rows = []
    for sc, sn, lv, tr, al in _OFFICIAL_MOCK:
        for fname, score in [
            ("FireRiskLevelFeature",      lv),
            ("FireRiskTrendFeature",      tr),
            ("LargeFireRiskAlertFeature", al),
        ]:
            rows.append({
                "feature":    fname,
                "sigucode":   sc,
                "sigun":      sn,
                "score":      score,
                "class":      "mock",
                "mock_input": False,   # 구조 real, 값만 mock
                "confidence": "high",
            })
    return rows


def run_all_features_mock() -> list[dict]:
    """B-1~B-4 전체 Feature mock rows 합산 (C-1 Signal 집계 입력용)."""
    return (
        get_mock_official_features()
        + run_exposure()
        + run_spread()
        + run_time_urgency()
    )


async def run_all_features_live() -> list[dict]:
    """
    B-1 산림청 실 API + B-2~B-4 mock 합산.
    - FORESTRY_API_KEY 있으면 실 API 호출 (오늘 날짜 예보)
    - API 키 없거나 호출 실패 시 mock fallback (무중단)
    """
    import asyncio
    from datetime import date as _date

    try:
        from pipelines.fire_risk_forecast.client import FireRiskForecastClient
        client = FireRiskForecastClient()
        try:
            forecasts = await client.fetch(str(_date.today()))
            b1_rows = run_official_risk(forecasts)
        finally:
            client.close()
    except Exception:
        b1_rows = get_mock_official_features()

    return b1_rows + run_exposure() + run_spread() + run_time_urgency()
