# B-1: OfficialRiskSignal Feature 3개
# 출처: docs/06_decision-logic.md §OfficialRiskSignal
#        docs/05_feature-contract.md §OfficialRiskSignal
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from pipelines.fire_risk_forecast.client import FireRiskForecast
from pipelines.kma_weather.client import WeatherForecast, WeatherWarning
from .base import (
    FeatureResult, level5, norm,
    risk_index_score, risk_grade_score, index_to_grade,
)


# ─── Feature 1: FireRiskLevelFeature ─────────────────────────
# 출처: §OfficialRiskSignal / F_official_level

def fire_risk_level(f: FireRiskForecast) -> FeatureResult:
    """
    산림청 현재 시점 위험지수 → score.
    F_official_level = max(risk_grade_score(grade), risk_index_score(maxi))
    """
    grade = index_to_grade(f.maxi)
    score = max(risk_grade_score(grade), risk_index_score(f.maxi))
    return FeatureResult(
        feature="FireRiskLevelFeature",
        sigucode=f.sigucode, sigun=f.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=f.is_mock,
        confidence="high",
    )


# ─── Feature 2: FireRiskTrendFeature ─────────────────────────
# 출처: §OfficialRiskSignal / F_official_trend
# API d1~d4 = 등급별 격자 비율(%), maxi = 공간 최고 지수
# mean = 평균 지수 → current_grade_score 근사
# maxi = 최고 지수 → peak_grade_score 근사

def fire_risk_trend(f: FireRiskForecast) -> FeatureResult:
    """
    지역 내 위험 분포의 peak-vs-mean 격차 → 악화 추세 score.
    F_trend = clip(0.5 + (peak - current) * 1.5, 0, 1)
    """
    current = risk_index_score(f.meanavg)
    peak    = risk_index_score(f.maxi)
    score   = max(0.0, min(1.0, 0.5 + (peak - current) * 1.5))

    # d4 비율 > 10% 이면 공간 분포 위험도 가중
    if f.d4 >= 10:
        score = min(1.0, score + 0.10)

    return FeatureResult(
        feature="FireRiskTrendFeature",
        sigucode=f.sigucode, sigun=f.sigun,
        score=round(score, 4),
        cls=level5(score),
        mock_input=f.is_mock,
        confidence="high",
    )


# ─── Feature 3: LargeFireRiskAlertFeature ────────────────────
# 출처: §OfficialRiskSignal / F_official_alert + fallback derivation

_ALERT_SCORE = {"없음": 0.0, "주의보": 0.6, "경보": 1.0}

def large_fire_risk_alert(
    f: FireRiskForecast,
    weather: WeatherForecast | None = None,
    warnings: list[WeatherWarning] | None = None,
) -> FeatureResult:
    """
    기상특보(건조/강풍) + 산림청 위험지수 → 대형산불 경보 score.
    Primary: 기상특보 데이터
    Fallback: maxi + 실효습도(reh) + 풍속(wsd) 조합
    """
    warnings = warnings or []

    # warn_var: "건조경보", "강풍주의보" 등 → "경보" | "주의보" | "없음" 정규화
    def _level(var: str) -> str:
        if "경보" in var: return "경보"
        if "주의보" in var: return "주의보"
        return "없음"

    _rank = {"없음": 0, "주의보": 1, "경보": 2}
    dry_level  = max((_level(w.warn_var) for w in warnings if w.is_dry),  default="없음", key=_rank.get)
    wind_level = max((_level(w.warn_var) for w in warnings if w.is_wind), default="없음", key=_rank.get)
    alert_level = max(dry_level, wind_level, key=_rank.get)

    is_fallback = (alert_level == "없음") and weather is not None
    confidence  = "high"

    if alert_level != "없음":
        score = _ALERT_SCORE[alert_level]

    elif weather is not None:
        # Fallback: 산림청 기준 유도
        # 경보: maxi≥51 ∧ reh<30 ∧ wsd≥11
        # 주의보: maxi≥51 ∧ 30≤reh≤45 ∧ 7≤wsd<11
        idx, reh, wsd = f.maxi, weather.reh, weather.wsd
        if idx >= 51 and reh < 30 and wsd >= 11:
            score, alert_level = 1.0, "경보(파생)"
        elif idx >= 51 and 30 <= reh <= 45 and 7 <= wsd < 11:
            score, alert_level = 0.6, "주의보(파생)"
        else:
            score, alert_level = 0.0, "없음"
        confidence = "medium-high"  # fallback → confidence 격하

    else:
        score = 0.0

    return FeatureResult(
        feature="LargeFireRiskAlertFeature",
        sigucode=f.sigucode, sigun=f.sigun,
        score=round(score, 4),
        cls=alert_level,
        mock_input=f.is_mock or (weather.is_mock if weather else False),
        confidence=confidence,
    )
