# B-4: TimeUrgencySignal Feature 2개
# 출처: docs/06_decision-logic.md §TimeUrgencySignal
#        docs/05_feature-contract.md §TimeUrgencySignal
#
# 주의: S_time에서 RainOffset은 inv(F_time_rain)으로 사용됨.
#        이 모듈은 Feature 원값(F_time_rain)을 출력하고,
#        Signal 계산 시 inv()를 적용한다.
from __future__ import annotations
from dataclasses import dataclass, field

from .base import FeatureResult, level5, norm, inv, risk_grade_score


# ─── 입력 dataclass ───────────────────────────────────────────

@dataclass
class HorizonSnapshot:
    """단일 시점 위험 스냅샷 (t = 현재, +6h, +12h, …).
    출처: docs/06_decision-logic.md §TimeUrgencySignal danger_t
    """
    risk_grade_score: float   # OfficialRisk 5단계 점수 [0, 1]
    reh: float                # 상대습도 % [20, 90]
    wsd: float                # 풍속 m/s  [0, 20]
    tmp: float                # 기온 °C   [0, 35]


@dataclass
class HighRiskTimeWindowInput:
    """출처: docs/05_feature-contract.md §HighRiskTimeWindowFeature"""
    sigucode: str
    sigun: str
    horizons: list[HorizonSnapshot]  # 시간 순 스냅샷 목록 (최소 1개)
    hours_to_peak: float             # 최대 위험 시점까지 남은 시간(h)
    is_mock: bool = True


@dataclass
class RainOffsetInput:
    """출처: docs/05_feature-contract.md §RainOffsetFeature"""
    sigucode: str
    sigun: str
    expected_rainfall_mm: float   # 예상 강수량 mm  [0, 30]
    rain_probability: float       # 강수 확률 %     [0, 100]
    rain_duration_hr: float       # 강수 지속 시간 h [0, 12]
    is_mock: bool = True


# ─── TimeUrgency 전용 함수 ────────────────────────────────────
# 출처: docs/06_decision-logic.md §TimeUrgencySignal

def _danger(h: HorizonSnapshot) -> float:
    """단일 시점 위험도 계산 (danger_t)."""
    return (
        0.40 * h.risk_grade_score
      + 0.20 * inv(norm(h.reh, 20, 90))
      + 0.20 * norm(h.wsd, 0, 20)
      + 0.20 * norm(h.tmp, 0, 35)
    )


def _imminence(hours: float) -> float:
    """hours_to_peak → imminence 계수."""
    if hours < 3:   return 1.00
    if hours < 12:  return 0.85
    if hours < 24:  return 0.65
    if hours < 48:  return 0.40
    return 0.20


# ─── Feature 14: HighRiskTimeWindowFeature ───────────────────
# 출처: §TimeUrgencySignal / F_time_window

def high_risk_time_window(inp: HighRiskTimeWindowInput) -> FeatureResult:
    """
    다중 시점 위험도 최대값 × imminence → 시간창 긴박도 score.
    F = max_t(danger_t) * imminence(hours_to_peak)
    """
    max_danger = max(_danger(h) for h in inp.horizons)
    score = max_danger * _imminence(inp.hours_to_peak)
    return FeatureResult(
        feature="HighRiskTimeWindowFeature",
        sigucode=inp.sigucode, sigun=inp.sigun,
        score=round(min(score, 1.0), 4),
        cls=level5(score),
        mock_input=inp.is_mock,
        confidence="medium",        # 05_feature-contract.md #14
    )


# ─── Feature 17: RainOffsetFeature ───────────────────────────
# 출처: §TimeUrgencySignal / F_time_rain
# ★ 주의: Signal 단계에서 inv()를 적용해 주수 긴급도를 낮춤.
#          이 함수는 F_time_rain(원값) 출력. inv 적용은 Signal 레이어에서.

def rain_offset(inp: RainOffsetInput) -> FeatureResult:
    """
    강수 예보 → 예비주수 필요성 상쇄 score (높을수록 비가 많이 올 것).
    F = norm(mm, [0,30]) * norm(prob, [0,100])
      * clip(norm(dur, [0,12]) + 0.3, 0, 1)
    S_time에서는 inv(F_time_rain)을 사용한다.
    """
    rain_score = (
        norm(inp.expected_rainfall_mm, 0, 30)
      * norm(inp.rain_probability, 0, 100)
      * max(0.0, min(1.0, norm(inp.rain_duration_hr, 0, 12) + 0.3))
    )
    return FeatureResult(
        feature="RainOffsetFeature",
        sigucode=inp.sigucode, sigun=inp.sigun,
        score=round(rain_score, 4),
        cls=level5(rain_score),
        mock_input=inp.is_mock,
        confidence="medium",        # 05_feature-contract.md #17
    )


# ─── Mock 데이터 ──────────────────────────────────────────────
# ★ 곡성군(4672000000): 2025-01-22 산불 — 건조·강풍·위험등급 최고, 강수 없음
#
# HighRiskTimeWindowInput 컬럼:
#   (sigucode, sigun, [(rgs, reh, wsd, tmp), ...], hours_to_peak)
#   horizons: (현재, +6h) 2개 스냅샷
#
# RainOffsetInput 컬럼:
#   (sigucode, sigun, mm, prob%, dur_hr)

_TIME_WINDOW_MOCK: list[tuple] = [
    # sigucode,        sigun,    horizons: [(rgs, reh, wsd, tmp), (+6h)],  h_peak
    ("2911000000", "동구",    [(0.40, 50, 5.0, 18), (0.40, 55,  4.5, 16)],  12.0),
    ("2914000000", "서구",    [(0.40, 52, 5.2, 18), (0.40, 56,  4.8, 16)],  14.0),
    ("2915500000", "남구",    [(0.45, 48, 6.0, 19), (0.45, 50,  5.5, 17)],  10.0),
    ("2917000000", "북구",    [(0.55, 42, 7.5, 17), (0.55, 44,  7.0, 15)],   8.0),
    ("2920000000", "광산구",  [(0.55, 40, 8.0, 17), (0.60, 38,  7.5, 15)],   6.0),
    ("4611000000", "목포시",  [(0.60, 38, 10.0, 12), (0.65, 35, 10.5, 10)],  5.0),
    ("4613000000", "여수시",  [(0.55, 40,  9.0, 13), (0.60, 38,  9.5, 11)],  6.0),
    ("4615000000", "순천시",  [(0.60, 38,  8.5, 11), (0.65, 35,  9.0,  9)],  4.0),
    ("4617000000", "나주시",  [(0.50, 45,  7.0, 14), (0.55, 43,  6.5, 12)],  8.0),
    ("4623000000", "광양시",  [(0.55, 42,  8.0, 12), (0.60, 40,  8.5, 10)],  5.0),
    ("4671000000", "담양군",  [(0.60, 36,  9.0, 10), (0.65, 33,  9.5,  8)],  4.0),
    # ★ 곡성군 2025-01-22: 매우 건조(reh=25), 강풍(14), 최고 위험등급, 2시간 후 최고조
    ("4672000000", "곡성군",  [(0.75, 25, 14.0,  8), (0.75, 22, 16.0,  6)],  2.0),
    ("4673000000", "구례군",  [(0.70, 28, 11.0,  9), (0.70, 25, 12.0,  7)],  3.0),
    ("4677000000", "고흥군",  [(0.50, 45,  7.5, 12), (0.55, 43,  7.0, 10)],  8.0),
    ("4678000000", "보성군",  [(0.55, 40,  7.0, 11), (0.60, 38,  7.5,  9)],  6.0),
    ("4679000000", "화순군",  [(0.60, 36,  9.5, 10), (0.65, 33, 10.0,  8)],  3.0),
    ("4680000000", "장흥군",  [(0.45, 50,  6.0, 12), (0.50, 48,  5.5, 10)],  10.0),
    ("4681000000", "강진군",  [(0.45, 52,  6.5, 13), (0.50, 50,  6.0, 11)],  11.0),
    ("4682000000", "해남군",  [(0.60, 38, 11.0, 11), (0.65, 35, 11.5,  9)],  5.0),
    ("4683000000", "영암군",  [(0.55, 42,  8.5, 12), (0.60, 40,  9.0, 10)],  6.0),
    ("4684000000", "무안군",  [(0.55, 44,  9.0, 13), (0.60, 42,  9.5, 11)],  7.0),
    ("4686000000", "함평군",  [(0.50, 46,  7.5, 13), (0.55, 44,  7.0, 11)],  8.0),
    ("4687000000", "영광군",  [(0.55, 40,  9.5, 12), (0.60, 38, 10.0, 10)],  5.0),
    ("4688000000", "장성군",  [(0.60, 36, 10.0, 10), (0.65, 33, 10.5,  8)],  4.0),
    ("4689000000", "완도군",  [(0.55, 42, 10.5, 12), (0.60, 40, 11.0, 10)],  6.0),
    ("4690000000", "진도군",  [(0.60, 38, 11.0, 11), (0.65, 35, 11.5,  9)],  5.0),
    ("4691000000", "신안군",  [(0.55, 40, 12.0, 11), (0.60, 38, 12.5,  9)],  5.0),
]

_RAIN_OFFSET_MOCK: list[tuple] = [
    # sigucode,        sigun,    mm,   prob%, dur_hr
    # 광주: 맑음, 강수 없음
    ("2911000000", "동구",      0.0,  10.0,  0.0),
    ("2914000000", "서구",      0.0,   8.0,  0.0),
    ("2915500000", "남구",      0.0,  10.0,  0.0),
    ("2917000000", "북구",      0.0,   5.0,  0.0),
    ("2920000000", "광산구",    0.0,   5.0,  0.0),
    # 전남 시 — 해안 일부 이슬비 가능
    ("4611000000", "목포시",    1.0,  20.0,  1.0),
    ("4613000000", "여수시",    1.5,  25.0,  1.5),
    ("4615000000", "순천시",    0.5,  15.0,  0.5),
    ("4617000000", "나주시",    0.0,   5.0,  0.0),
    ("4623000000", "광양시",    0.5,  15.0,  0.5),
    # 내륙 산간 — 건조, 강수 없음
    ("4671000000", "담양군",    0.0,   5.0,  0.0),
    # ★ 곡성군 2025-01-22: 강수 없음 → inv(F_time_rain) = 1.0 → 주수 긴급성 최고
    ("4672000000", "곡성군",    0.0,   3.0,  0.0),
    ("4673000000", "구례군",    0.0,   3.0,  0.0),
    ("4677000000", "고흥군",    0.5,  15.0,  0.5),
    ("4678000000", "보성군",    0.0,  10.0,  0.0),
    ("4679000000", "화순군",    0.0,   5.0,  0.0),
    ("4680000000", "장흥군",    1.0,  20.0,  1.0),
    ("4681000000", "강진군",    1.0,  18.0,  1.0),
    ("4682000000", "해남군",    0.5,  15.0,  0.5),
    ("4683000000", "영암군",    0.0,  10.0,  0.0),
    ("4684000000", "무안군",    0.5,  15.0,  0.5),
    ("4686000000", "함평군",    0.0,  10.0,  0.0),
    ("4687000000", "영광군",    0.5,  15.0,  0.5),
    ("4688000000", "장성군",    0.0,   5.0,  0.0),
    ("4689000000", "완도군",    2.0,  30.0,  2.0),
    ("4690000000", "진도군",    1.5,  25.0,  1.5),
    ("4691000000", "신안군",    2.0,  30.0,  2.5),
]


def get_mock_time_window() -> list[HighRiskTimeWindowInput]:
    result = []
    for sc, sn, raw_horizons, h_peak in _TIME_WINDOW_MOCK:
        horizons = [HorizonSnapshot(rgs, reh, wsd, tmp) for rgs, reh, wsd, tmp in raw_horizons]
        result.append(HighRiskTimeWindowInput(sc, sn, horizons, h_peak))
    return result


def get_mock_rain_offset() -> list[RainOffsetInput]:
    return [
        RainOffsetInput(sc, sn, mm, prob, dur)
        for sc, sn, mm, prob, dur in _RAIN_OFFSET_MOCK
    ]
