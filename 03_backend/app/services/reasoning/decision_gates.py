# C-3: 5 Decision Gate + C-4: Confidence × Gate 매트릭스
# 출처: docs/06_decision-logic.md §Decision Gate, §Action Mapping
#
# 5 Gates:
#   Gate 1: SelectPreWateringSegment — State >= ReviewPreWatering
#   Gate 2: SchedulePreWatering      — selected + S_time
#   Gate 3: AssignResourcePackage    — schedule + actionability
#   Gate 4: DeferOrMonitor           — MonitorOnly/NotActionable/Deferred
#   Gate 5: RequestManualReview      — mock dominant / EXCLUDE / join failure
#
# C-4 Confidence × Gate 매트릭스:
#   execute      : 자동 실행 가능
#   advisory_only: 권고만 출력, 자동 실행 금지 (confidence 불충분)
#   manual_review: 인간 확인 필요 (mock dominant 또는 EXCLUDE 의존)
#   blocked      : Gate 미발동 (trigger 조건 미충족)
from __future__ import annotations
from dataclasses import dataclass, field


# ─── Feature Confidence Context ──────────────────────────────
# Gate confidence 판단에 필요한 개별 Feature confidence 수준.
# 미구현 Feature는 기본값 "low" (mock-dominant 처리).
# 출처: docs/05_feature-contract.md §Feature Summary

@dataclass
class FeatureConfidenceContext:
    """Gate confidence 입력. 미구현 Feature는 기본 'low'."""
    # Gate 2/3: TimeUrgency (DispatchLead, Duration → 미구현)
    f_time_lead_conf: str = "low"       # DispatchLeadTimeFeature (#15)
    f_time_duration_conf: str = "low"   # WateringDurationFeature (#16)
    # Gate 3/4: WateringActionability (미구현 → 전부 low)
    f_action_vehicle_conf: str = "low"  # VehicleAccessFeature (#10)
    f_action_water_conf: str = "low"    # WaterSourceFeature (#11)
    f_action_safety_conf: str = "low"   # WorkSafetyFeature (#13)
    # Gate 5: EXCLUDE / join failure flags
    large_fire_alert_join_failed: bool = False
    geocode_failed: bool = False


# ─── Gate 출력 dataclass ─────────────────────────────────────

@dataclass
class GateResult:
    """단일 Decision Gate 평가 결과."""
    gate: str                # SelectPreWateringSegment | ...
    triggered: bool          # Trigger 조건 충족 여부
    mode: str                # execute | advisory_only | manual_review | blocked
    reason: str              # 결정 이유 (발표/디버깅용)


@dataclass
class DecisionResult:
    """시군구별 전체 Decision Gate 평가 결과."""
    sigucode: str
    sigun: str
    state_band: str
    s_priority: float
    override_applied: str
    mock_input: bool
    gates: list[GateResult] = field(default_factory=list)
    # 핵심 요약
    primary_decision: str = ""    # 가장 중요한 triggered gate
    action_mode: str = "blocked"  # execute | advisory_only | manual_review | blocked
    action_summary: str = ""      # 발표용 한국어 요약


# ─── Action Mapping 한국어 ────────────────────────────────────
# 출처: docs/06_decision-logic.md §Action Mapping

_ACTION_MAP: dict[str, str] = {
    "ImmediatePreWatering":  "즉시 출동·주수·완료기록·재점검 예약",
    "PriorityPreWatering":   "예정 출동·주수·완료기록",
    "ReviewPreWatering":     "관할청 통보·일일 재점검 예약",
    "EnhancedMonitoring":    "일 2회 재점검 예약",
    "GeneralManagement":     "조치 없음",
    "MonitorOnly":           "강수 종료 후 재점검 예약",
    "NotActionable":         "안전 위험 통보·위험 해소 후 재점검",
    "Deferred":              "접근 차단 통보·접근 복구 후 재점검",
    "Completed":             "위험창 이후 재점검 예약",
    "Recheck":               "현장 재점검 출동 또는 완료 기록",
}

# ─── C-4: mode 판단 보조 함수 ────────────────────────────────

def _is_low(conf: str) -> bool:
    return conf == "low"


def _count_low(*confs: str) -> int:
    return sum(1 for c in confs if _is_low(c))


# ─── 5 Gate 함수 ─────────────────────────────────────────────
# 각 함수: (state_band, s_priority, mock_input, fcc) → GateResult

_SELECT_STATES = {"ReviewPreWatering", "PriorityPreWatering", "ImmediatePreWatering"}
_DEFER_STATES  = {"MonitorOnly", "NotActionable", "Deferred"}


def _gate_select(state: str, _sp: float, _mock: bool, _fcc: FeatureConfidenceContext) -> GateResult:
    """
    Gate 1: SelectPreWateringSegment.
    출처: §Decision Gate — '항상 advisory list 출력 가능'
    """
    if state not in _SELECT_STATES:
        return GateResult("SelectPreWateringSegment", False, "blocked",
                          f"State={state}: ReviewPreWatering 미만")
    return GateResult("SelectPreWateringSegment", True, "advisory_only",
                      f"State={state}: 예비주수 구간 선정 권고")


def _gate_schedule(state: str, st: float, _mock: bool, fcc: FeatureConfidenceContext) -> GateResult:
    """
    Gate 2: SchedulePreWatering.
    출처: §Decision Gate — 'F_time_lead or F_time_duration low → advisory_only'
    C-4: F_time_lead=low (미구현) → 항상 advisory_only
    """
    if state not in _SELECT_STATES:
        return GateResult("SchedulePreWatering", False, "blocked",
                          "SelectPreWateringSegment 미발동")

    if _is_low(fcc.f_time_lead_conf) or _is_low(fcc.f_time_duration_conf):
        return GateResult("SchedulePreWatering", True, "advisory_only",
                          f"F_time_lead={fcc.f_time_lead_conf} or "
                          f"F_time_duration={fcc.f_time_duration_conf}: advisory_only")

    return GateResult("SchedulePreWatering", True, "execute",
                      f"S_time={st:.3f}: 일정 자동 배정 가능")


def _gate_assign(state: str, _st: float, _mock: bool, fcc: FeatureConfidenceContext) -> GateResult:
    """
    Gate 3: AssignResourcePackage.
    출처: §Decision Gate — 'vehicle, water, duration 중 2개 이상 low → RequestManualReview'
    C-4: vehicle=low, water=low, duration=low → 3/3 → RequestManualReview
    """
    if state not in _SELECT_STATES:
        return GateResult("AssignResourcePackage", False, "blocked",
                          "SelectPreWateringSegment 미발동")

    low_count = _count_low(
        fcc.f_action_vehicle_conf,
        fcc.f_action_water_conf,
        fcc.f_time_duration_conf,
    )
    if low_count >= 2:
        return GateResult("AssignResourcePackage", True, "manual_review",
                          f"vehicle/water/duration 중 {low_count}개 low: 수동 배정 검토")

    return GateResult("AssignResourcePackage", True, "execute",
                      "actionability 충분: 자원 자동 배정 가능")


def _gate_defer(state: str, _st: float, _mock: bool, fcc: FeatureConfidenceContext) -> GateResult:
    """
    Gate 4: DeferOrMonitor.
    출처: §Decision Gate — 'safety or vehicle low → 자동 defer 금지'
    C-4: safety=low, vehicle=low → advisory_only (자동 defer 불가)
    """
    if state not in _DEFER_STATES:
        return GateResult("DeferOrMonitor", False, "blocked",
                          f"State={state}: defer/monitor 대상 아님")

    if _is_low(fcc.f_action_safety_conf) or _is_low(fcc.f_action_vehicle_conf):
        return GateResult("DeferOrMonitor", True, "advisory_only",
                          f"safety={fcc.f_action_safety_conf} or "
                          f"vehicle={fcc.f_action_vehicle_conf}: 자동 defer 금지, 수동 확인 필요")

    return GateResult("DeferOrMonitor", True, "execute",
                      f"State={state}: 자동 유예/모니터링 가능")


def _gate_review(state: str, _st: float, mock: bool, fcc: FeatureConfidenceContext) -> GateResult:
    """
    Gate 5: RequestManualReview.
    출처: §Decision Gate — 'mock dominant, EXCLUDE, join/geocode failure → 항상 허용'
    """
    reasons = []
    if mock:
        reasons.append("mock_input=True (mock dominant)")
    if fcc.large_fire_alert_join_failed:
        reasons.append("대형산불 경보 join 실패")
    if fcc.geocode_failed:
        reasons.append("geocoding 실패")
    # 미구현 Feature가 alert/grade 분기점 영향 가능성
    if state in ("PriorityPreWatering", "ImmediatePreWatering"):
        reasons.append("상위 State: 핵심 입력 검증 권고")

    if not reasons:
        return GateResult("RequestManualReview", False, "blocked",
                          "manual review 트리거 없음")

    return GateResult("RequestManualReview", True, "manual_review",
                      "; ".join(reasons))


# ─── C-4: 전체 action_mode 결정 ─────────────────────────────
# Gate 결과들로부터 최종 action_mode 도출.

_MODE_RANK = {"blocked": 0, "execute": 1, "advisory_only": 2, "manual_review": 3}


def _overall_mode(gates: list[GateResult]) -> str:
    """triggered된 Gate 중 가장 엄격한 mode를 최종 action_mode로."""
    triggered = [g for g in gates if g.triggered]
    if not triggered:
        return "blocked"
    return max(triggered, key=lambda g: _MODE_RANK.get(g.mode, 0)).mode


def _primary_decision(gates: list[GateResult]) -> str:
    """triggered된 Gate 중 우선순위 최상위 Gate 이름."""
    priority_order = [
        "RequestManualReview",
        "DeferOrMonitor",
        "SelectPreWateringSegment",
        "SchedulePreWatering",
        "AssignResourcePackage",
    ]
    triggered_names = {g.gate for g in gates if g.triggered}
    for name in priority_order:
        if name in triggered_names:
            return name
    return "없음"


# ─── 메인 평가 함수 ──────────────────────────────────────────

def evaluate_gates(
    sigucode: str,
    sigun: str,
    state_band: str,
    s_priority: float,
    s_time: float,
    override_applied: str,
    mock_input: bool,
    fcc: FeatureConfidenceContext | None = None,
) -> DecisionResult:
    """
    단일 시군구 5 Decision Gate 평가.
    출처: docs/06_decision-logic.md §Decision Gate + C-4 Confidence × Gate 매트릭스
    """
    fcc = fcc or FeatureConfidenceContext()

    gates = [
        _gate_select(state_band, s_priority, mock_input, fcc),
        _gate_schedule(state_band, s_time, mock_input, fcc),
        _gate_assign(state_band, s_time, mock_input, fcc),
        _gate_defer(state_band, s_time, mock_input, fcc),
        _gate_review(state_band, s_time, mock_input, fcc),
    ]

    mode    = _overall_mode(gates)
    primary = _primary_decision(gates)
    action  = _ACTION_MAP.get(state_band, state_band)

    return DecisionResult(
        sigucode=sigucode, sigun=sigun,
        state_band=state_band, s_priority=s_priority,
        override_applied=override_applied, mock_input=mock_input,
        gates=gates,
        primary_decision=primary,
        action_mode=mode,
        action_summary=action,
    )


def evaluate_all_gates(
    bundles: list,   # list[SignalBundle]
    fcc_map: dict[str, FeatureConfidenceContext] | None = None,
) -> list[DecisionResult]:
    """
    SignalBundle 목록 → DecisionResult 목록 (S_priority 내림차순 유지).
    fcc_map: sigucode → FeatureConfidenceContext (없으면 기본값 사용)
    """
    fcc_map = fcc_map or {}
    return [
        evaluate_gates(
            sigucode=b.sigucode,
            sigun=b.sigun,
            state_band=b.state_band,
            s_priority=b.s_priority,
            s_time=b.s_time,
            override_applied=b.override_applied,
            mock_input=b.mock_input,
            fcc=fcc_map.get(b.sigucode),
        )
        for b in bundles
    ]
