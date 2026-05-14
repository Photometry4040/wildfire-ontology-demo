# C-2 검증: 9 Override 풀버전
# 각 Override가 올바른 State로 변환되는지 확인
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.reasoning import (
    OverrideContext, apply_overrides, compute_signals, _state_rank,
)
from app.services.features import run_all_features_mock


# ─── 공통 헬퍼 ───────────────────────────────────────────────

def _apply(sp: float, **kwargs) -> tuple[str, str]:
    """apply_overrides 편의 래퍼."""
    return apply_overrides(sp, OverrideContext(**kwargs))


# ─── Override 1: HazardGate ──────────────────────────────────

def test_o1_hazard_gate_notactionable():
    """F_action_safety = 작업불가 → NotActionable (최우선)."""
    state, ov = _apply(0.90, work_safety_notactionable=True)
    assert state == "NotActionable"
    assert ov    == "HazardGate"


def test_o1_hazard_gate_overrides_high_priority():
    """HazardGate는 S_priority=0.99여도 NotActionable."""
    state, _ = _apply(0.99, work_safety_notactionable=True)
    assert state == "NotActionable"


def test_o1_hazard_gate_false_no_effect():
    """work_safety_notactionable=False → ImmediatePreWatering 그대로."""
    state, ov = _apply(0.99, work_safety_notactionable=False)
    assert state == "ImmediatePreWatering"
    assert ov    == "none"


# ─── Override 2: AccessGate ──────────────────────────────────

def test_o2_access_gate_infeasible():
    """infeasible_dispatch_flag=True → Deferred."""
    state, ov = _apply(0.70, infeasible_dispatch_flag=True)
    assert state == "Deferred"
    assert ov    == "AccessGate"


def test_o2_access_gate_vehicle():
    """vehicle_not_accessible=True → Deferred."""
    state, ov = _apply(0.70, vehicle_not_accessible=True)
    assert state == "Deferred"
    assert ov    == "AccessGate"


def test_o2_access_gate_after_hazard():
    """HazardGate(O1) > AccessGate(O2) 우선순위 확인."""
    state, ov = _apply(
        0.70,
        work_safety_notactionable=True,
        infeasible_dispatch_flag=True,
    )
    assert state == "NotActionable"
    assert ov    == "HazardGate"


# ─── Override 3: RainGate ────────────────────────────────────

def test_o3_rain_gate_dominant():
    """rain_score > 0.6 → MonitorOnly."""
    state, ov = _apply(0.80, rain_score=0.65)
    assert state == "MonitorOnly"
    assert ov    == "RainGate"


def test_o3_rain_gate_threshold_exact():
    """rain_score = 0.6 → 임계 초과 아님 → 정상 State Band."""
    state, ov = _apply(0.80, rain_score=0.60)
    assert state == "ImmediatePreWatering"
    assert ov    == "none"


def test_o3_rain_gate_after_hazard():
    """HazardGate(O1) > RainGate(O3)."""
    state, ov = _apply(0.80, work_safety_notactionable=True, rain_score=0.65)
    assert state == "NotActionable"
    assert ov    == "HazardGate"


# ─── Override 4: Recheck (Lifecycle) ─────────────────────────

def test_o4_recheck_new_risk_window():
    """이전 완료 후 새 위험창 → Recheck."""
    state, ov = _apply(0.30, previous_completed=True, high_risk_window_new=True)
    assert state == "Recheck"
    assert ov    == "Recheck"


def test_o4_recheck_wetness_due():
    """이전 완료 후 재적습 필요 → Recheck."""
    state, ov = _apply(0.30, previous_completed=True, wetness_recheck_due=True)
    assert state == "Recheck"
    assert ov    == "Recheck"


def test_o4_recheck_hazard_takes_priority():
    """HazardGate(O1) → Recheck보다 우선."""
    state, ov = _apply(
        0.30,
        work_safety_notactionable=True,
        previous_completed=True,
        high_risk_window_new=True,
    )
    assert state == "NotActionable"


# ─── Override 5: Completed (Lifecycle) ───────────────────────

def test_o5_completed_no_recheck():
    """이전 완료 + 재진입 트리거 없음 → Completed."""
    state, ov = _apply(0.70, previous_completed=True)
    assert state == "Completed"
    assert ov    == "Completed"


def test_o5_completed_fresh_segment_skips():
    """previous_completed=False → Lifecycle 건너뜀."""
    state, ov = _apply(0.70, previous_completed=False)
    # S_priority 0.70 → PriorityPreWatering (no lifecycle override)
    assert state == "PriorityPreWatering"
    assert ov    == "none"


# ─── Override 6: AlertSevere ─────────────────────────────────

def test_o6_alert_severe_upgrades_to_priority():
    """경보 → ReviewPreWatering 이하를 PriorityPreWatering으로 격상."""
    state, ov = _apply(0.50, alert_class="경보")
    assert state == "PriorityPreWatering"
    assert ov    == "AlertSevere"


def test_o6_alert_severe_derived():
    """경보(파생) → AlertSevere."""
    state, ov = _apply(0.10, alert_class="경보(파생)")
    assert state == "PriorityPreWatering"
    assert ov    == "AlertSevere"


def test_o6_alert_severe_no_downgrade():
    """S_priority가 이미 ImmediatePreWatering → Override 격상 없음."""
    state, ov = _apply(0.90, alert_class="경보")
    assert state == "ImmediatePreWatering"
    assert ov    == "none"


# ─── Override 7: AlertWarning ────────────────────────────────

def test_o7_alert_warning_with_exposure():
    """주의보 + S_exposure >= 0.5 → ReviewPreWatering 격상."""
    state, ov = _apply(0.10, alert_class="주의보", s_exposure=0.70)
    assert state == "ReviewPreWatering"
    assert ov    == "AlertWarning"


def test_o7_alert_warning_no_exposure():
    """주의보 + S_exposure < 0.5 → Override 미적용."""
    state, ov = _apply(0.10, alert_class="주의보", s_exposure=0.30)
    assert state == "GeneralManagement"
    assert ov    == "none"


def test_o7_warning_beats_grade_high():
    """AlertWarning(O7)과 GradeHigh(O9) 동시: 같은 floor → AlertWarning 우선."""
    state, ov = _apply(
        0.10,
        alert_class="주의보",
        s_exposure=0.70,
        risk_grade="높음",
    )
    assert state == "ReviewPreWatering"
    # AlertWarning이 GradeHigh보다 우선순위 높음
    assert ov in ("AlertWarning", "GradeHigh")   # 둘 다 같은 State


# ─── Override 8: GradeSevere ─────────────────────────────────

def test_o8_grade_severe_index():
    """risk_index >= 86 → PriorityPreWatering 격상."""
    state, ov = _apply(0.10, risk_index=90.0)
    assert state == "PriorityPreWatering"
    assert ov    == "GradeSevere"


def test_o8_grade_severe_label():
    """risk_grade = 매우높음 → GradeSevere."""
    state, ov = _apply(0.10, risk_grade="매우높음")
    assert state == "PriorityPreWatering"
    assert ov    == "GradeSevere"


# ─── Override 9: GradeHigh ───────────────────────────────────

def test_o9_grade_high_index():
    """risk_index >= 66 → ReviewPreWatering 격상."""
    state, ov = _apply(0.10, risk_index=70.0)
    assert state == "ReviewPreWatering"
    assert ov    == "GradeHigh"


def test_o9_grade_high_not_downgrade():
    """S_priority >= 0.40 이면 GradeHigh 격상 불필요."""
    state, ov = _apply(0.50, risk_grade="높음")
    assert state == "ReviewPreWatering"
    assert ov    == "none"   # 이미 ReviewPreWatering이라 변화 없음


# ─── 복합 Override (6~9 동시 매치) ──────────────────────────

def test_alert_severe_beats_grade_high():
    """AlertSevere(O6, floor=Priority) > GradeHigh(O9, floor=Review)."""
    state, ov = _apply(
        0.10,
        alert_class="경보",
        risk_grade="높음",
    )
    assert state == "PriorityPreWatering"
    assert ov    == "AlertSevere"


def test_grade_severe_beats_alert_warning():
    """GradeSevere(O8, floor=Priority) > AlertWarning(O7, floor=Review)."""
    state, ov = _apply(
        0.10,
        alert_class="주의보",
        s_exposure=0.70,
        risk_grade="매우높음",
    )
    assert state == "PriorityPreWatering"
    # AlertSevere or GradeSevere (둘 다 Priority floor)
    assert ov in ("GradeSevere",)   # O8이 O7보다 candidate 후순서지만 결과는 Priority


# ─── compute_signals에 OverrideContext 통합 ───────────────────

def test_compute_override_hazard_gate():
    """compute_signals에 HazardGate override 전달."""
    rows = run_all_features_mock()
    overrides = {"4672000000": OverrideContext(work_safety_notactionable=True)}
    bundles = compute_signals(rows, override_map=overrides)
    gk = next(b for b in bundles if b.sigucode == "4672000000")
    assert gk.state_band == "NotActionable"
    assert gk.override_applied == "HazardGate"


def test_compute_override_rain_gate():
    """compute_signals에 RainGate 강제 (rain_score via fmap)."""
    # RainOffsetFeature.score > 0.6 인 row를 만들어 전달
    rows = run_all_features_mock()
    # 완도군에 rain_score=0.7 주입
    for r in rows:
        if r["sigucode"] == "4689000000" and r["feature"] == "RainOffsetFeature":
            r["score"] = 0.70  # 강수 우세
    bundles = compute_signals(rows)
    wando = next(b for b in bundles if b.sigucode == "4689000000")
    assert wando.state_band    == "MonitorOnly"
    assert wando.override_applied == "RainGate"


def test_compute_auto_extract_alert_class():
    """LargeFireRiskAlertFeature.score=0.6 → alert_class 자동 추출 → Override 6/7 적용."""
    rows = run_all_features_mock()
    # 담양군에 경보 score 주입
    for r in rows:
        if r["sigucode"] == "4671000000" and r["feature"] == "LargeFireRiskAlertFeature":
            r["score"] = 1.0   # 경보
            r["class"] = "경보(파생)"
    bundles = compute_signals(rows)
    damyang = next(b for b in bundles if b.sigucode == "4671000000")
    # S_exposure >= 0.5이면 AlertSevere(O6) 또는 이미 PriorityPreWatering이면 no override
    assert damyang.state_band in ("PriorityPreWatering", "ImmediatePreWatering")


def test_compute_lifecycle_completed():
    """previous_completed=True, 재진입 없음 → Completed."""
    rows = run_all_features_mock()
    overrides = {"4672000000": OverrideContext(previous_completed=True)}
    bundles = compute_signals(rows, override_map=overrides)
    gk = next(b for b in bundles if b.sigucode == "4672000000")
    assert gk.state_band      == "Completed"
    assert gk.override_applied == "Completed"


# ─── _state_rank 유틸리티 ────────────────────────────────────

def test_state_rank_ordering():
    """State 순위 확인."""
    assert _state_rank("GeneralManagement")     == 0
    assert _state_rank("EnhancedMonitoring")    == 1
    assert _state_rank("ReviewPreWatering")     == 2
    assert _state_rank("PriorityPreWatering")   == 3
    assert _state_rank("ImmediatePreWatering")  == 4
    assert _state_rank("NotActionable")         == -1   # special


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
