# B-2: ExposureSignal Feature 3개
# 출처: docs/06_decision-logic.md §ExposureSignal
#        docs/05_feature-contract.md §ExposureSignal
#
# 실데이터 현황:
#   - ResidentialExposureFeature: 인구 통계 실데이터 없음 → mock
#   - CriticalAssetFeature: 전남 vulnerable 일부 mock 좌표
#   - ForestInterfaceFeature: 거리·접점 GIS derived → mock
# 발표 멘트: "구조는 김O학님 DOL 그대로, 값은 시연용 mock"
from __future__ import annotations
from dataclasses import dataclass, field

from .base import FeatureResult, level5, norm, inv


# ─── 입력 dataclass ───────────────────────────────────────────

@dataclass
class ResidentialExposureInput:
    """출처: docs/05_feature-contract.md §ResidentialExposureFeature"""
    sigucode: str
    sigun: str
    residential_building_count: int        # 건물 수 [0, 5000]
    residential_population: int            # 인구 [0, 30000]
    residential_household_count: int       # 가구 수 [0, 12000]
    forest_to_residence_distance_m: float  # 산림→주거지 최근접 거리(m) [0, 2000]
    is_mock: bool = True


@dataclass
class CriticalAssetInput:
    """출처: docs/05_feature-contract.md §CriticalAssetFeature"""
    sigucode: str
    sigun: str
    critical_asset_count: int                              # 총 보호대상 수 [0, 20]
    critical_asset_class_mix: dict[str, int] = field(default_factory=dict)
    # 키: "문화재" | "요양시설" | "병원" | "공공시설"
    # 값: segment buffer 안의 개수
    critical_asset_min_distance_m: float = 2000.0         # 산림→최근접 보호대상(m) [0, 2000]
    is_mock: bool = True


@dataclass
class ForestInterfaceInput:
    """출처: docs/05_feature-contract.md §ForestInterfaceFeature"""
    sigucode: str
    sigun: str
    forest_asset_distance_m: float         # 산림→자산 최근접 거리(m) [0, 2000]
    forest_asset_interface_length_m: float # 산림-자산 접경선 길이(m) [0, 1000]
    is_mock: bool = True


# ─── ExposureSignal 전용 가중합 ───────────────────────────────
# 출처: docs/06_decision-logic.md §ExposureSignal weighted_class_mix

_CLASS_WEIGHT: dict[str, float] = {
    "문화재":   1.00,
    "요양시설": 0.95,
    "병원":     0.90,
    "공공시설": 0.55,
}
_MAX_COUNT_CAP = 20


def _weighted_class_mix(mix: dict[str, int]) -> float:
    """weighted_class_mix(mix, CLASS_WEIGHT, max_count_cap=20)."""
    total = sum(_CLASS_WEIGHT.get(cls, 0.0) * cnt for cls, cnt in mix.items())
    return min(total / _MAX_COUNT_CAP, 1.0)


# ─── Feature 4: ResidentialExposureFeature ───────────────────
# 출처: §ExposureSignal / F_exposure_residential

def residential_exposure(r: ResidentialExposureInput) -> FeatureResult:
    """
    인구·건물·가구 밀도 + 산림 근접성 → 주거 노출 score.
    F = 0.40*norm(pop,[0,30000]) + 0.20*norm(hh,[0,12000])
      + 0.15*norm(bld,[0,5000]) + 0.25*inv(norm(dist,[0,2000]))
    """
    score = (
        0.40 * norm(r.residential_population,        0, 30000)
      + 0.20 * norm(r.residential_household_count,   0, 12000)
      + 0.15 * norm(r.residential_building_count,    0,  5000)
      + 0.25 * inv(norm(r.forest_to_residence_distance_m, 0, 2000))
    )
    return FeatureResult(
        feature="ResidentialExposureFeature",
        sigucode=r.sigucode, sigun=r.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=r.is_mock,
        confidence="medium-high",  # 05_feature-contract.md §ExposureSignal
    )


# ─── Feature 5: CriticalAssetFeature ─────────────────────────
# 출처: §ExposureSignal / F_exposure_critical

def critical_asset(c: CriticalAssetInput) -> FeatureResult:
    """
    문화재·요양·병원·공공시설 가중합 + 근접성 → 핵심자산 노출 score.
    F = 0.45*weighted_class_mix + 0.20*norm(count,[0,20])
      + 0.35*inv(norm(min_dist,[0,2000]))
    """
    score = (
        0.45 * _weighted_class_mix(c.critical_asset_class_mix)
      + 0.20 * norm(c.critical_asset_count, 0, 20)
      + 0.35 * inv(norm(c.critical_asset_min_distance_m, 0, 2000))
    )
    return FeatureResult(
        feature="CriticalAssetFeature",
        sigucode=c.sigucode, sigun=c.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=c.is_mock,
        confidence="medium-high",
    )


# ─── Feature 6: ForestInterfaceFeature ───────────────────────
# 출처: §ExposureSignal / F_exposure_interface

def forest_interface(fi: ForestInterfaceInput) -> FeatureResult:
    """
    산림→자산 근접성 + 접경선 길이 → 산림 경계 노출 score.
    F = 0.55*inv(norm(dist,[0,2000])) + 0.45*norm(length,[0,1000])
    """
    score = (
        0.55 * inv(norm(fi.forest_asset_distance_m,        0, 2000))
      + 0.45 * norm(fi.forest_asset_interface_length_m, 0, 1000)
    )
    return FeatureResult(
        feature="ForestInterfaceFeature",
        sigucode=fi.sigucode, sigun=fi.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=fi.is_mock,
        confidence="medium",   # GIS derived, 전부 mock
    )


# ─── Mock 데이터 ──────────────────────────────────────────────
# 발표 데모용 시연 값. 구조는 김O학님 DOL 그대로.
# ★ 곡성군(4672000000): 2025-01-22 산불 회고 검증 기준 → 높은 노출도 설정
#
# ResidentialExposureInput 컬럼:
#   (sigucode, sigun, bld_cnt, pop, hh_cnt, forest_dist_m)
# CriticalAssetInput 컬럼:
#   (sigucode, sigun, asset_cnt, {mix}, min_dist_m)
# ForestInterfaceInput 컬럼:
#   (sigucode, sigun, forest_dist_m, interface_len_m)

_RESIDENTIAL_MOCK: list[tuple] = [
    # sigucode,        sigun,    bld,   pop,   hh,    dist_m
    ("2911000000", "동구",      3200, 28000, 11200,   800),
    ("2914000000", "서구",      4200, 29000, 11800,   900),
    ("2915500000", "남구",      3800, 27500, 11000,   700),
    ("2917000000", "북구",      4800, 29500, 12000,   600),
    ("2920000000", "광산구",    4600, 29000, 11500,   500),
    ("4611000000", "목포시",    3600, 22000,  8800,   650),
    ("4613000000", "여수시",    3200, 21000,  8400,   400),
    ("4615000000", "순천시",    3400, 25000,  9800,   350),
    ("4617000000", "나주시",    2200, 12000,  4800,   300),
    ("4623000000", "광양시",    2800, 15000,  5900,   280),
    ("4671000000", "담양군",    1200,  9500,  3800,   180),
    ("4672000000", "곡성군",    1800, 25000, 10000,   150),  # ★ 산불 기준 지역
    ("4673000000", "구례군",    1000,  7500,  3000,   120),
    ("4677000000", "고흥군",     900,  7000,  2800,   200),
    ("4678000000", "보성군",     950,  7200,  2900,   220),
    ("4679000000", "화순군",    1100,  9000,  3600,   160),
    ("4680000000", "장흥군",     800,  6500,  2600,   250),
    ("4681000000", "강진군",     750,  6000,  2400,   270),
    ("4682000000", "해남군",     850,  7800,  3100,   310),
    ("4683000000", "영암군",     820,  6800,  2700,   290),
    ("4684000000", "무안군",    1300, 10000,  4000,   330),
    ("4686000000", "함평군",     700,  5500,  2200,   340),
    ("4687000000", "영광군",     780,  5800,  2300,   260),
    ("4688000000", "장성군",     920,  8000,  3200,   200),
    ("4689000000", "완도군",     680,  5200,  2100,   180),
    ("4690000000", "진도군",     720,  5600,  2250,   210),
    ("4691000000", "신안군",     600,  4800,  1900,   400),
]

_CRITICAL_ASSET_MOCK: list[tuple] = [
    # sigucode,        sigun,  cnt,  mix(문/요/병/공),                min_dist_m
    ("2911000000", "동구",       8, {"문화재":1,"요양시설":2,"병원":2,"공공시설":3}, 200),
    ("2914000000", "서구",      10, {"문화재":0,"요양시설":3,"병원":3,"공공시설":4}, 180),
    ("2915500000", "남구",       9, {"문화재":1,"요양시설":2,"병원":3,"공공시설":3}, 190),
    ("2917000000", "북구",      12, {"문화재":1,"요양시설":3,"병원":4,"공공시설":4}, 160),
    ("2920000000", "광산구",    11, {"문화재":0,"요양시설":3,"병원":4,"공공시설":4}, 170),
    ("4611000000", "목포시",    10, {"문화재":2,"요양시설":2,"병원":3,"공공시설":3}, 300),
    ("4613000000", "여수시",    11, {"문화재":3,"요양시설":2,"병원":3,"공공시설":3}, 250),
    ("4615000000", "순천시",    13, {"문화재":4,"요양시설":3,"병원":3,"공공시설":3}, 220),  # 선암사
    ("4617000000", "나주시",     7, {"문화재":3,"요양시설":1,"병원":1,"공공시설":2}, 280),
    ("4623000000", "광양시",     6, {"문화재":1,"요양시설":2,"병원":2,"공공시설":1}, 300),
    ("4671000000", "담양군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 150),
    ("4672000000", "곡성군",     5, {"문화재":2,"요양시설":1,"병원":0,"공공시설":2}, 300),  # ★
    ("4673000000", "구례군",     7, {"문화재":4,"요양시설":1,"병원":0,"공공시설":2}, 100),  # 화엄사
    ("4677000000", "고흥군",     4, {"문화재":1,"요양시설":1,"병원":1,"공공시설":1}, 400),
    ("4678000000", "보성군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 350),
    ("4679000000", "화순군",     6, {"문화재":2,"요양시설":2,"병원":1,"공공시설":1}, 200),
    ("4680000000", "장흥군",     4, {"문화재":1,"요양시설":1,"병원":1,"공공시설":1}, 420),
    ("4681000000", "강진군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 380),
    ("4682000000", "해남군",     8, {"문화재":5,"요양시설":1,"병원":1,"공공시설":1}, 200),  # 대흥사
    ("4683000000", "영암군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 300),
    ("4684000000", "무안군",     5, {"문화재":1,"요양시설":2,"병원":1,"공공시설":1}, 310),
    ("4686000000", "함평군",     4, {"문화재":1,"요양시설":1,"병원":1,"공공시설":1}, 450),
    ("4687000000", "영광군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 330),
    ("4688000000", "장성군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 280),
    ("4689000000", "완도군",     4, {"문화재":1,"요양시설":1,"병원":1,"공공시설":1}, 360),
    ("4690000000", "진도군",     5, {"문화재":2,"요양시설":1,"병원":1,"공공시설":1}, 300),
    ("4691000000", "신안군",     3, {"문화재":1,"요양시설":1,"병원":0,"공공시설":1}, 500),
]

_FOREST_INTERFACE_MOCK: list[tuple] = [
    # sigucode,        sigun,    dist_m,  iface_len_m
    ("2911000000", "동구",         900,       100),
    ("2914000000", "서구",        1100,        80),
    ("2915500000", "남구",         800,       150),
    ("2917000000", "북구",         400,       400),
    ("2920000000", "광산구",       350,       450),
    ("4611000000", "목포시",       600,       300),
    ("4613000000", "여수시",       200,       700),
    ("4615000000", "순천시",       150,       800),
    ("4617000000", "나주시",       250,       600),
    ("4623000000", "광양시",       120,       850),
    ("4671000000", "담양군",       100,       900),
    ("4672000000", "곡성군",        50,       950),  # ★ 산림 매우 가까움
    ("4673000000", "구례군",        80,       920),
    ("4677000000", "고흥군",       300,       550),
    ("4678000000", "보성군",       180,       750),
    ("4679000000", "화순군",       130,       870),
    ("4680000000", "장흥군",       200,       680),
    ("4681000000", "강진군",       220,       640),
    ("4682000000", "해남군",       250,       580),
    ("4683000000", "영암군",       280,       540),
    ("4684000000", "무안군",       400,       420),
    ("4686000000", "함평군",       350,       460),
    ("4687000000", "영광군",       310,       500),
    ("4688000000", "장성군",       150,       820),
    ("4689000000", "완도군",       200,       700),
    ("4690000000", "진도군",       280,       560),
    ("4691000000", "신안군",       500,       350),
]


def get_mock_residential() -> list[ResidentialExposureInput]:
    return [
        ResidentialExposureInput(sc, sn, bld, pop, hh, dist)
        for sc, sn, bld, pop, hh, dist in _RESIDENTIAL_MOCK
    ]


def get_mock_critical_asset() -> list[CriticalAssetInput]:
    return [
        CriticalAssetInput(sc, sn, cnt, mix, dist)
        for sc, sn, cnt, mix, dist in _CRITICAL_ASSET_MOCK
    ]


def get_mock_forest_interface() -> list[ForestInterfaceInput]:
    return [
        ForestInterfaceInput(sc, sn, dist, iface)
        for sc, sn, dist, iface in _FOREST_INTERFACE_MOCK
    ]
