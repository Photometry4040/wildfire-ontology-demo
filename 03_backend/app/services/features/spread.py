# B-3: SpreadToAssetSignal Feature 3개
# 출처: docs/06_decision-logic.md §SpreadToAssetSignal
#        docs/05_feature-contract.md §SpreadToAssetSignal
#
# 실데이터 현황:
#   - WindTowardAssetFeature : KMA 풍향/풍속은 실데이터 가능.
#                               bearing_to_asset_deg(GIS derived) 는 mock.
#   - TerrainTowardAssetFeature: DEM 제외 → 방위 클래스 mock.
#   - FuelContinuityFeature : 산림·도로 속성 일부 실데이터.
#                               광주 임도 0 → disconnect_count mock.
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

from .base import FeatureResult, level5, norm, inv


# ─── 입력 dataclass ───────────────────────────────────────────

BearingClass = Literal["정면", "사면-가까움", "사면-먼", "외면"]
ContinuityClass = Literal["연속", "부분단절", "단절"]
DensityClass = Literal["조밀", "보통", "성긴", "미입목"]


@dataclass
class WindTowardAssetInput:
    """출처: docs/05_feature-contract.md §WindTowardAssetFeature"""
    sigucode: str
    sigun: str
    wind_toward_asset_flag: bool   # 풍향이 산림→자산 방향인지 (DERIVED)
    gust_toward_asset_flag: bool   # 돌풍 방향이 산림→자산 방향인지 (DERIVED)
    wsd: float                     # KMA 예보 풍속 m/s
    observed_wind_speed: float     # 관측 풍속 m/s
    observed_gust_speed: float     # 관측 돌풍 m/s
    is_mock: bool = True


@dataclass
class TerrainTowardAssetInput:
    """출처: docs/05_feature-contract.md §TerrainTowardAssetFeature
    DEM 제외 → slope/aspect/elevation 없음. 방위 클래스만 사용.
    """
    sigucode: str
    sigun: str
    forest_to_asset_bearing_class: BearingClass
    is_mock: bool = True


@dataclass
class FuelContinuityInput:
    """출처: docs/05_feature-contract.md §FuelContinuityFeature
    natural barrier 제외. 광주 임도 0 → disconnect_count는 도로 기준.
    """
    sigucode: str
    sigun: str
    forest_continuity_class: ContinuityClass
    disconnect_count: int       # 산림 연속성 단절 수 [0, 10]
    forest_density_class: DensityClass
    is_mock: bool = True


# ─── SpreadToAsset 전용 lookup ────────────────────────────────
# 출처: docs/06_decision-logic.md §SpreadToAssetSignal

_BEARING_SCORE: dict[str, float] = {
    "정면":      1.00,
    "사면-가까움": 0.65,
    "사면-먼":   0.35,
    "외면":      0.00,
}

_CONTINUITY_SCORE: dict[str, float] = {
    "연속":   1.0,
    "부분단절": 0.5,
    "단절":   0.0,
}

_DENSITY_SCORE: dict[str, float] = {
    "조밀":  1.0,
    "보통":  0.6,
    "성긴":  0.3,
    "미입목": 0.0,
}


# ─── Feature 7: WindTowardAssetFeature ───────────────────────
# 출처: §SpreadToAssetSignal / F_spread_wind

def wind_toward_asset(w: WindTowardAssetInput) -> FeatureResult:
    """
    풍향·풍속이 산림→자산 방향으로 불어가는 강도 → score.
    F = 0.45 * wind_flag * norm(max(WSD, obs_wind), [0,20])
      + 0.25 * gust_flag * norm(obs_gust, [0,25])
      + 0.30 * norm(max(WSD, obs_wind), [0,20])
    """
    effective_wind = max(w.wsd, w.observed_wind_speed)
    score = (
        0.45 * int(w.wind_toward_asset_flag) * norm(effective_wind, 0, 20)
      + 0.25 * int(w.gust_toward_asset_flag) * norm(w.observed_gust_speed, 0, 25)
      + 0.30 * norm(effective_wind, 0, 20)
    )
    return FeatureResult(
        feature="WindTowardAssetFeature",
        sigucode=w.sigucode, sigun=w.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=w.is_mock,
        confidence="medium",        # 05_feature-contract.md #7
    )


# ─── Feature 8: TerrainTowardAssetFeature ────────────────────
# 출처: §SpreadToAssetSignal / F_spread_terrain

def terrain_toward_asset(t: TerrainTowardAssetInput) -> FeatureResult:
    """
    산림→자산 방위 클래스 lookup → score.
    F = lookup(bearing_class, {정면:1.00, 사면-가까움:0.65, 사면-먼:0.35, 외면:0.00})
    DEM 제외로 slope/aspect/elevation 미반영 (축소 정의).
    """
    score = _BEARING_SCORE.get(t.forest_to_asset_bearing_class, 0.0)
    return FeatureResult(
        feature="TerrainTowardAssetFeature",
        sigucode=t.sigucode, sigun=t.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=t.is_mock,
        confidence="medium-low",    # 05_feature-contract.md #8 (DEM 제외)
    )


# ─── Feature 9: FuelContinuityFeature ────────────────────────
# 출처: §SpreadToAssetSignal / F_spread_fuel

def fuel_continuity(fc: FuelContinuityInput) -> FeatureResult:
    """
    산림 연속성·단절 수·밀도 → 연소 전파 가능성 score.
    F = 0.40 * lookup(continuity) + 0.25 * inv(norm(disconnect, [0,10]))
      + 0.35 * lookup(density)
    """
    score = (
        0.40 * _CONTINUITY_SCORE.get(fc.forest_continuity_class, 0.0)
      + 0.25 * inv(norm(fc.disconnect_count, 0, 10))
      + 0.35 * _DENSITY_SCORE.get(fc.forest_density_class, 0.0)
    )
    return FeatureResult(
        feature="FuelContinuityFeature",
        sigucode=fc.sigucode, sigun=fc.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=fc.is_mock,
        confidence="medium-high",   # 05_feature-contract.md #9
    )


# ─── 실데이터 경로: 풍향 플래그 계산 보조함수 ─────────────────
# KMA WeatherForecast.vec (풍향, 바람이 불어오는 방향) + bearing_to_asset_deg
# → wind_toward_asset_flag 계산.
# mock 데이터에는 필요 없지만 A-2 KMA 실연동 시 사용.

def wind_flags_from_bearing(
    bearing_to_asset_deg: float,
    vec: int,
    gust_vec: int | None = None,
    threshold_deg: float = 45.0,
) -> tuple[bool, bool]:
    """
    bearing_to_asset_deg: 산림→자산 방향(도)
    vec               : KMA 풍향 (바람이 '오는' 방향, 0=북)
    → (wind_toward_flag, gust_toward_flag)
    바람이 '부는' 방향 = (vec + 180) % 360
    """
    def _angular_diff(a: float, b: float) -> float:
        return abs((a - b + 180) % 360 - 180)

    wind_blowing = (vec + 180) % 360
    wind_flag = _angular_diff(wind_blowing, bearing_to_asset_deg) < threshold_deg

    if gust_vec is not None:
        gust_blowing = (gust_vec + 180) % 360
        gust_flag = _angular_diff(gust_blowing, bearing_to_asset_deg) < threshold_deg
    else:
        gust_flag = wind_flag

    return wind_flag, gust_flag


# ─── Mock 데이터 ──────────────────────────────────────────────
# ★ 곡성군(4672000000): 2025-01-22 산불 — 강한 북서풍, 남쪽 마을 정면 노출
#
# WindTowardAssetInput 컬럼:
#   (sigucode, sigun, wind_toward, gust_toward, wsd, obs_wind, obs_gust)
# TerrainTowardAssetInput 컬럼:
#   (sigucode, sigun, bearing_class)
# FuelContinuityInput 컬럼:
#   (sigucode, sigun, continuity_class, disconnect_count, density_class)

_WIND_MOCK: list[tuple] = [
    # 광주: 도심 → 풍향이 자산 방향 아닐 가능성 높음, 풍속 보통
    ("2911000000", "동구",    False, False,  5.0,  4.5,  7.0),
    ("2914000000", "서구",    False, False,  5.2,  4.8,  7.5),
    ("2915500000", "남구",    True,  False,  6.0,  5.5,  9.0),
    ("2917000000", "북구",    True,  True,   7.5,  7.0, 11.0),
    ("2920000000", "광산구",  True,  True,   8.0,  7.5, 12.0),
    # 전남 시
    ("4611000000", "목포시",  True,  True,  10.0,  9.5, 14.0),  # 해안, 강풍
    ("4613000000", "여수시",  True,  True,   9.0,  8.5, 13.0),
    ("4615000000", "순천시",  True,  True,   8.5,  8.0, 12.5),
    ("4617000000", "나주시",  True,  False,  7.0,  6.5, 10.5),
    ("4623000000", "광양시",  True,  True,   8.0,  7.5, 12.0),
    # 전남 군 — 산간 내륙
    ("4671000000", "담양군",  True,  True,   9.0,  8.5, 13.0),
    ("4672000000", "곡성군",  True,  True,  14.0, 12.0, 18.0),  # ★ 산불 기준
    ("4673000000", "구례군",  True,  True,  11.0, 10.5, 16.0),
    ("4677000000", "고흥군",  True,  False,  7.5,  7.0, 11.0),
    ("4678000000", "보성군",  True,  False,  7.0,  6.5, 10.0),
    ("4679000000", "화순군",  True,  True,   9.5,  9.0, 14.0),
    ("4680000000", "장흥군",  False, False,  6.0,  5.5,  8.5),
    ("4681000000", "강진군",  False, False,  6.5,  6.0,  9.0),
    ("4682000000", "해남군",  True,  True,  11.0, 10.5, 16.0),  # 해안 강풍
    ("4683000000", "영암군",  True,  True,   8.5,  8.0, 12.5),
    ("4684000000", "무안군",  True,  True,   9.0,  8.5, 13.5),
    ("4686000000", "함평군",  True,  False,  7.5,  7.0, 11.0),
    ("4687000000", "영광군",  True,  True,   9.5,  9.0, 14.0),
    ("4688000000", "장성군",  True,  True,  10.0,  9.5, 15.0),
    ("4689000000", "완도군",  True,  True,  10.5, 10.0, 15.5),
    ("4690000000", "진도군",  True,  True,  11.0, 10.5, 16.5),
    ("4691000000", "신안군",  True,  True,  12.0, 11.5, 17.5),  # 섬, 강풍
]

_TERRAIN_MOCK: list[tuple] = [
    # sigucode,        sigun,    bearing_class
    ("2911000000", "동구",    "외면"),
    ("2914000000", "서구",    "외면"),
    ("2915500000", "남구",    "사면-먼"),
    ("2917000000", "북구",    "사면-가까움"),
    ("2920000000", "광산구",  "사면-가까움"),
    ("4611000000", "목포시",  "사면-가까움"),
    ("4613000000", "여수시",  "사면-가까움"),
    ("4615000000", "순천시",  "정면"),
    ("4617000000", "나주시",  "사면-먼"),
    ("4623000000", "광양시",  "정면"),
    ("4671000000", "담양군",  "정면"),
    ("4672000000", "곡성군",  "정면"),           # ★ 협곡, 마을 정면 노출
    ("4673000000", "구례군",  "정면"),
    ("4677000000", "고흥군",  "사면-먼"),
    ("4678000000", "보성군",  "사면-가까움"),
    ("4679000000", "화순군",  "정면"),
    ("4680000000", "장흥군",  "사면-먼"),
    ("4681000000", "강진군",  "사면-먼"),
    ("4682000000", "해남군",  "사면-가까움"),
    ("4683000000", "영암군",  "사면-먼"),
    ("4684000000", "무안군",  "외면"),
    ("4686000000", "함평군",  "사면-먼"),
    ("4687000000", "영광군",  "사면-가까움"),
    ("4688000000", "장성군",  "정면"),
    ("4689000000", "완도군",  "사면-가까움"),
    ("4690000000", "진도군",  "사면-가까움"),
    ("4691000000", "신안군",  "외면"),
]

_FUEL_MOCK: list[tuple] = [
    # sigucode,        sigun,    continuity,  disconnect, density
    ("2911000000", "동구",    "단절",    8, "성긴"),
    ("2914000000", "서구",    "단절",    9, "성긴"),
    ("2915500000", "남구",    "단절",    7, "성긴"),
    ("2917000000", "북구",    "부분단절", 5, "보통"),
    ("2920000000", "광산구",  "부분단절", 4, "보통"),
    ("4611000000", "목포시",  "부분단절", 5, "보통"),
    ("4613000000", "여수시",  "부분단절", 3, "조밀"),
    ("4615000000", "순천시",  "연속",    2, "조밀"),
    ("4617000000", "나주시",  "부분단절", 4, "보통"),
    ("4623000000", "광양시",  "연속",    2, "조밀"),
    ("4671000000", "담양군",  "연속",    1, "조밀"),
    ("4672000000", "곡성군",  "연속",    1, "조밀"),  # ★ 빽빽한 산림, 거의 단절 없음
    ("4673000000", "구례군",  "연속",    1, "조밀"),
    ("4677000000", "고흥군",  "부분단절", 3, "보통"),
    ("4678000000", "보성군",  "연속",    2, "조밀"),
    ("4679000000", "화순군",  "연속",    2, "조밀"),
    ("4680000000", "장흥군",  "부분단절", 3, "보통"),
    ("4681000000", "강진군",  "부분단절", 4, "보통"),
    ("4682000000", "해남군",  "부분단절", 4, "보통"),
    ("4683000000", "영암군",  "부분단절", 3, "보통"),
    ("4684000000", "무안군",  "부분단절", 5, "성긴"),
    ("4686000000", "함평군",  "부분단절", 4, "보통"),
    ("4687000000", "영광군",  "부분단절", 3, "보통"),
    ("4688000000", "장성군",  "연속",    2, "조밀"),
    ("4689000000", "완도군",  "부분단절", 3, "보통"),
    ("4690000000", "진도군",  "부분단절", 4, "보통"),
    ("4691000000", "신안군",  "부분단절", 6, "성긴"),
]


def get_mock_wind() -> list[WindTowardAssetInput]:
    return [
        WindTowardAssetInput(sc, sn, wt, gt, wsd, ow, og)
        for sc, sn, wt, gt, wsd, ow, og in _WIND_MOCK
    ]


def get_mock_terrain() -> list[TerrainTowardAssetInput]:
    return [
        TerrainTowardAssetInput(sc, sn, bc)
        for sc, sn, bc in _TERRAIN_MOCK
    ]


def get_mock_fuel() -> list[FuelContinuityInput]:
    return [
        FuelContinuityInput(sc, sn, cont, disc, dens)
        for sc, sn, cont, disc, dens in _FUEL_MOCK
    ]
