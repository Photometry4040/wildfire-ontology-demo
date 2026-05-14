# Feature 공통 출력 모델 + 보조 함수
# 출처: docs/05_feature-contract.md §공통 출력
#        docs/06_decision-logic.md §보조 함수 §Feature Formulas
from __future__ import annotations
from dataclasses import dataclass


# ─── 공통 출력 ────────────────────────────────────────────────

@dataclass
class FeatureResult:
    feature: str        # Feature 이름
    sigucode: str       # 시군구 10자리
    sigun: str          # 시군구명
    score: float        # [0, 1] — 예비주수 우선순위가 높을수록 1
    cls: str            # level5 label
    mock_input: bool    # mock 소스 포함 여부 (score에 반영 안 함)
    confidence: str     # high | medium-high | medium | medium-low | low


# ─── 보조 함수 ────────────────────────────────────────────────
# 출처: docs/06_decision-logic.md §보조 함수

def norm(x: float, a: float, b: float) -> float:
    """clip(x, a, b)를 [0,1]로 선형 정규화."""
    x = max(a, min(b, x))
    return (x - a) / (b - a) if b > a else 0.0


def inv(x: float) -> float:
    """1 - x. 거리/시간처럼 작을수록 위험한 값에 사용."""
    return 1.0 - x


def level5(s: float) -> str:
    """score → level5 label (낮음~높음). 출처: §level5."""
    if s < 0.20: return "낮음"
    if s < 0.40: return "다소낮음"
    if s < 0.60: return "보통"
    if s < 0.80: return "다소높음"
    return "높음"


# ─── OfficialRisk 전용 함수 ──────────────────────────────────
# 출처: docs/06_decision-logic.md §OfficialRiskSignal

_GRADE_SCORE: dict[str, float] = {
    "정상": 0.00, "낮음": 0.20, "다소높음": 0.55, "높음": 0.75, "매우높음": 1.00,
}

_RISK_BREAKPOINTS = [(0, 0.00), (50, 0.20), (65, 0.55), (85, 0.75), (100, 1.00)]


def risk_index_score(x: float) -> float:
    """연속 위험지수 (0~100) → [0,1] 점수 (piecewise linear)."""
    for i in range(1, len(_RISK_BREAKPOINTS)):
        x0, y0 = _RISK_BREAKPOINTS[i - 1]
        x1, y1 = _RISK_BREAKPOINTS[i]
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return 1.0


def risk_grade_score(grade: str) -> float:
    return _GRADE_SCORE.get(grade, 0.0)


def index_to_grade(idx: float) -> str:
    """위험지수 → 산림청 5단계 등급명."""
    if idx <= 50: return "낮음"
    if idx <= 65: return "다소높음"
    if idx <= 85: return "높음"
    return "매우높음"
