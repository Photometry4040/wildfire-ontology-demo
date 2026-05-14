# models.py
# 역할: FastAPI 응답 스키마 정의 (Pydantic v2)
# 출처: 06_decision-logic.md §State Transition, §Feature Contract

from pydantic import BaseModel
from typing import Optional, Union


class FeatureItem(BaseModel):
    """Feature 1개 — FireRiskLevel / ResidentialExposure / WindTowardAsset"""
    kind: str
    score: float
    feature_class: str


class SignalItem(BaseModel):
    """Signal 1개 — S_official / S_exposure"""
    kind: str
    score: float


class SegmentSummary(BaseModel):
    """구간 목록 조회 응답 (GET /api/segments)"""
    segment_id: str
    segment_name: str
    state_band: str
    s_priority: float
    override_applied: str


# ── B-1: Status 타임라인 ──

class StatusStep(BaseModel):
    """추론 파이프라인 진행 이력 1단계"""
    name: str         # init | calc-features | calc-signals | apply-override | decide | audit
    label: str        # 한국어 단계명
    completed: bool
    timestamp: str    # HH:MM:SS
    description: str  # 단계 설명 (툴팁용)


class SegmentDetail(SegmentSummary):
    """구간 상세 조회 응답 (GET /api/segments/{id})"""
    hazard_flag: bool
    risk_grade: str
    risk_index: float
    features: list[FeatureItem]
    signals: list[SignalItem]
    status_history: list[StatusStep] = []  # B-1 추가


class LineageItem(BaseModel):
    """Lineage 역추적 1행 (GET /api/segments/{id}/lineage)"""
    segment_id: str
    segment_name: str
    state_band: str
    s_priority: float
    override_applied: str
    feature_kind: str
    feature_score: float
    signal_kind: str
    signal_score: float


class HealthResponse(BaseModel):
    """헬스 체크 응답 (GET /api/health)"""
    status: str
    typedb: str
    db_name: str


class InferenceResult(BaseModel):
    """추론 재실행 응답 (POST /api/inference/run)"""
    success: bool
    message: str
    segments_processed: int


# ── B-4: 함수 추론 3단계 라이브 뷰 ──

class TraceIO(BaseModel):
    """추론 단계 입력·출력 1개 항목"""
    key: str
    value: Union[float, str, bool]
    label: Optional[str] = None   # 한국어 표시명
    weight: Optional[str] = None  # 가중치 표시 (예: "×0.20")


class TraceStep(BaseModel):
    """추론 파이프라인 1단계"""
    step: int
    name: str          # calc_features | calc_signals | decide
    label: str         # ① Feature 계산 | ② Signal 집계 | ③ 최종 결정
    inputs: list[TraceIO]
    outputs: list[TraceIO]
    typeql_snippet: str
    formula_note: Optional[str] = None  # 수식 설명 (발표용)


class InferenceTraceResponse(BaseModel):
    """GET /api/segments/{id}/inference-trace 응답"""
    segment_id: str
    segment_name: str
    steps: list[TraceStep]


# ── B-3: 가중치 시뮬레이터 ──

class WeightInput(BaseModel):
    """S_priority 5 Signal 가중치 (합계 권장 1.0)"""
    S_official: float = 0.20
    S_exposure: float = 0.25
    S_spread:   float = 0.20
    S_action:   float = 0.20
    S_time:     float = 0.15


class WeightRequest(BaseModel):
    """POST /api/inference/run-with-thresholds 요청 body"""
    weights: WeightInput


class SegmentThresholdResult(BaseModel):
    """가중치 시뮬레이션 결과 — 1개 구간"""
    segment_id:    str
    segment_name:  str
    before_sp:     float
    after_sp:      float
    delta:         float
    before_state:  str
    after_state:   str
    state_changed: bool
