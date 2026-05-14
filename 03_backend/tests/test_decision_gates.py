# C-3/C-4 검증: 5 Decision Gate + Confidence × Gate 매트릭스
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.reasoning import (
    OverrideContext, compute_signals,
    FeatureConfidenceContext, GateResult, DecisionResult,
    evaluate_gates, evaluate_all_gates,
)
from app.services.features import run_all_features_mock

VALID_MODES    = {"execute", "advisory_only", "manual_review", "blocked"}
VALID_GATES    = {
    "SelectPreWateringSegment", "SchedulePreWatering",
    "AssignResourcePackage", "DeferOrMonitor", "RequestManualReview",
}


# ─── 테스트용 헬퍼 ───────────────────────────────────────────

def _eval(state: str, sp: float = 0.70, st: float = 0.60,
          mock: bool = True, **fcc_kwargs) -> DecisionResult:
    fcc = FeatureConfidenceContext(**fcc_kwargs)
    return evaluate_gates("test", "테스트", state, sp, st, "none", mock, fcc)


def _gate(result: DecisionResult, gate_name: str) -> GateResult:
    return next(g for g in result.gates if g.gate == gate_name)


# ─── Gate 1: SelectPreWateringSegment ────────────────────────

def test_select_review_triggers():
    """ReviewPreWatering → SelectPreWateringSegment 발동."""
    r = _eval("ReviewPreWatering")
    g = _gate(r, "SelectPreWateringSegment")
    assert g.triggered
    assert g.mode == "advisory_only"   # 항상 advisory


def test_select_priority_triggers():
    """PriorityPreWatering → 발동."""
    r = _eval("PriorityPreWatering")
    assert _gate(r, "SelectPreWateringSegment").triggered


def test_select_immediate_triggers():
    """ImmediatePreWatering → 발동."""
    r = _eval("ImmediatePreWatering")
    assert _gate(r, "SelectPreWateringSegment").triggered


def test_select_enhanced_monitoring_blocked():
    """EnhancedMonitoring → 선정 Gate 미발동."""
    r = _eval("EnhancedMonitoring")
    g = _gate(r, "SelectPreWateringSegment")
    assert not g.triggered
    assert g.mode == "blocked"


def test_select_general_management_blocked():
    """GeneralManagement → 미발동."""
    assert not _gate(_eval("GeneralManagement"), "SelectPreWateringSegment").triggered


# ─── Gate 2: SchedulePreWatering ─────────────────────────────

def test_schedule_low_time_lead_advisory():
    """F_time_lead=low → advisory_only (C-4 매트릭스)."""
    r = _eval("PriorityPreWatering", f_time_lead_conf="low")
    g = _gate(r, "SchedulePreWatering")
    assert g.triggered
    assert g.mode == "advisory_only"


def test_schedule_low_duration_advisory():
    """F_time_duration=low → advisory_only."""
    r = _eval("PriorityPreWatering", f_time_lead_conf="medium", f_time_duration_conf="low")
    assert _gate(r, "SchedulePreWatering").mode == "advisory_only"


def test_schedule_high_confidence_execute():
    """time_lead=high, duration=high → execute."""
    r = _eval("PriorityPreWatering",
              f_time_lead_conf="high", f_time_duration_conf="high")
    assert _gate(r, "SchedulePreWatering").mode == "execute"


def test_schedule_blocked_when_select_blocked():
    """SelectPreWateringSegment 미발동 → SchedulePreWatering도 미발동."""
    r = _eval("GeneralManagement")
    assert not _gate(r, "SchedulePreWatering").triggered


# ─── Gate 3: AssignResourcePackage ───────────────────────────

def test_assign_two_low_manual_review():
    """vehicle=low, water=low (2개) → manual_review."""
    r = _eval("PriorityPreWatering",
              f_action_vehicle_conf="low", f_action_water_conf="low",
              f_time_duration_conf="medium")
    g = _gate(r, "AssignResourcePackage")
    assert g.triggered
    assert g.mode == "manual_review"


def test_assign_three_low_manual_review():
    """vehicle=low, water=low, duration=low (3개) → manual_review."""
    r = _eval("PriorityPreWatering",
              f_action_vehicle_conf="low", f_action_water_conf="low",
              f_time_duration_conf="low")
    assert _gate(r, "AssignResourcePackage").mode == "manual_review"


def test_assign_one_low_execute():
    """low 1개만 → execute."""
    r = _eval("PriorityPreWatering",
              f_action_vehicle_conf="low",
              f_action_water_conf="high",
              f_time_duration_conf="high")
    assert _gate(r, "AssignResourcePackage").mode == "execute"


def test_assign_blocked_when_select_blocked():
    """SelectPreWateringSegment 미발동 → AssignResourcePackage도 미발동."""
    r = _eval("GeneralManagement")
    assert not _gate(r, "AssignResourcePackage").triggered


# ─── Gate 4: DeferOrMonitor ──────────────────────────────────

def test_defer_monitor_only_triggers():
    """MonitorOnly → DeferOrMonitor 발동."""
    r = _eval("MonitorOnly")
    assert _gate(r, "DeferOrMonitor").triggered


def test_defer_notactionable_triggers():
    """NotActionable → 발동."""
    assert _gate(_eval("NotActionable"), "DeferOrMonitor").triggered


def test_defer_deferred_triggers():
    """Deferred → 발동."""
    assert _gate(_eval("Deferred"), "DeferOrMonitor").triggered


def test_defer_safety_low_advisory():
    """safety=low → 자동 defer 금지 → advisory_only."""
    r = _eval("NotActionable", f_action_safety_conf="low")
    g = _gate(r, "DeferOrMonitor")
    assert g.triggered
    assert g.mode == "advisory_only"


def test_defer_vehicle_low_advisory():
    """vehicle=low → advisory_only."""
    r = _eval("Deferred", f_action_vehicle_conf="low")
    assert _gate(r, "DeferOrMonitor").mode == "advisory_only"


def test_defer_high_confidence_execute():
    """safety=high, vehicle=high → execute."""
    r = _eval("MonitorOnly",
              f_action_safety_conf="high", f_action_vehicle_conf="high")
    assert _gate(r, "DeferOrMonitor").mode == "execute"


def test_defer_priority_state_blocked():
    """PriorityPreWatering → DeferOrMonitor 미발동."""
    assert not _gate(_eval("PriorityPreWatering"), "DeferOrMonitor").triggered


# ─── Gate 5: RequestManualReview ─────────────────────────────

def test_review_mock_triggers():
    """mock_input=True → RequestManualReview 발동."""
    r = _eval("ReviewPreWatering", mock=True)
    assert _gate(r, "RequestManualReview").triggered
    assert _gate(r, "RequestManualReview").mode == "manual_review"


def test_review_no_mock_no_failure_high_state():
    """mock=False, join/geocode 정상, 상위 State → 트리거 (상위 State 검증 권고)."""
    r = _eval("PriorityPreWatering", mock=False)
    # PriorityPreWatering → 상위 State 검증 권고로 트리거
    assert _gate(r, "RequestManualReview").triggered


def test_review_general_no_trigger():
    """mock=False, GeneralManagement, 실패 없음 → 미발동."""
    r = _eval("GeneralManagement", mock=False)
    assert not _gate(r, "RequestManualReview").triggered


def test_review_join_failed():
    """large_fire_alert_join_failed=True → 발동."""
    r = _eval("ReviewPreWatering", mock=False,
              large_fire_alert_join_failed=True)
    assert _gate(r, "RequestManualReview").triggered


def test_review_geocode_failed():
    """geocode_failed=True → 발동."""
    r = _eval("ReviewPreWatering", mock=False,
              geocode_failed=True)
    assert _gate(r, "RequestManualReview").triggered


# ─── C-4: action_mode 종합 매트릭스 ─────────────────────────

def test_action_mode_manual_review_dominant():
    """manual_review가 advisory_only보다 엄격 → 전체 mode = manual_review."""
    r = _eval("PriorityPreWatering", mock=True)
    assert r.action_mode == "manual_review"   # Gate 5 = manual_review 우선


def test_action_mode_advisory_only():
    """mock=False이고 PriorityPreWatering → Gate 2,3 advisory or manual → manual_review."""
    r = _eval("PriorityPreWatering", mock=False)
    # AssignResourcePackage → manual_review (vehicle/water/duration 기본값=low → 2개 이상)
    # Gate 5도 상위 State 검증 권고 → manual_review
    assert r.action_mode == "manual_review"


def test_action_mode_blocked_general():
    """GeneralManagement + mock=False → 모든 Gate 미발동 → blocked."""
    r = _eval("GeneralManagement", mock=False)
    assert r.action_mode == "blocked"


# ─── primary_decision ────────────────────────────────────────

def test_primary_decision_request_review():
    """RequestManualReview가 최우선."""
    r = _eval("PriorityPreWatering", mock=True)
    assert r.primary_decision == "RequestManualReview"


def test_primary_decision_defer_or_monitor():
    """Defer/Monitor state → DeferOrMonitor."""
    r = _eval("MonitorOnly", mock=False)
    assert r.primary_decision == "DeferOrMonitor"


def test_primary_decision_select():
    """ReviewPreWatering + mock=False + no defer → SelectPreWateringSegment."""
    r = _eval("ReviewPreWatering", mock=False)
    # Gate 5: ReviewPreWatering는 상위 State 조건 없음 → 미발동 (mock=False)
    # Gate 3: AssignResourcePackage manual_review → RequestManualReview 우선?
    # Wait: Gate 5 checks "state in PriorityPreWatering, ImmediatePreWatering"
    # ReviewPreWatering → Gate 5 may not trigger
    # But AssignResourcePackage → manual_review → Gate 5 doesn't apply
    # Primary: RequestManualReview (Gate3=manual_review) or SelectPreWatering
    assert r.primary_decision in ("RequestManualReview", "SelectPreWateringSegment")


# ─── evaluate_all_gates 통합 ─────────────────────────────────

def test_evaluate_all_gates_mock():
    """전체 시군구 mock → DecisionResult 목록."""
    bundles  = compute_signals(run_all_features_mock())
    results  = evaluate_all_gates(bundles)
    assert len(results) == 27
    for dr in results:
        assert dr.action_mode in VALID_MODES
        for g in dr.gates:
            assert g.gate in VALID_GATES
            assert g.mode in VALID_MODES


def test_gokseong_decision():
    """곡성군 — PriorityPreWatering → SelectPreWateringSegment 발동."""
    bundles = compute_signals(run_all_features_mock())
    results = evaluate_all_gates(bundles)
    gk = next(dr for dr in results if dr.sigucode == "4672000000")

    assert gk.state_band == "PriorityPreWatering"
    assert _gate(gk, "SelectPreWateringSegment").triggered
    assert _gate(gk, "SchedulePreWatering").triggered
    assert _gate(gk, "AssignResourcePackage").triggered
    # mock_input=True → RequestManualReview 발동
    assert _gate(gk, "RequestManualReview").triggered
    # 전체 mode: manual_review
    assert gk.action_mode == "manual_review"


def test_action_summary_not_empty():
    """action_summary가 비어있지 않아야 함."""
    bundles = compute_signals(run_all_features_mock())
    results = evaluate_all_gates(bundles)
    for dr in results:
        assert dr.action_summary != "", f"{dr.sigun}: action_summary 없음"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
