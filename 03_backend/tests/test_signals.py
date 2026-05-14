# C-1 검증: 5 Signal 종합 + S_priority + State Band
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.features import run_all_features_mock
from app.services.reasoning import SignalBundle, compute_signals, _factor_to_confidence, _downgrade

VALID_SIGNALS    = {"S_official", "S_exposure", "S_spread", "S_action", "S_time"}
VALID_STATES     = {
    "ImmediatePreWatering", "PriorityPreWatering", "ReviewPreWatering",
    "EnhancedMonitoring", "GeneralManagement",
    "NotActionable", "Deferred", "MonitorOnly", "Recheck", "Completed",
}
VALID_CONFIDENCE = {"high", "medium-high", "medium", "medium-low", "low"}


# ─── Confidence Ordinal ───────────────────────────────────────

def test_factor_to_confidence():
    assert _factor_to_confidence(1.00) == "high"
    assert _factor_to_confidence(0.95) == "high"
    assert _factor_to_confidence(0.92) == "medium-high"
    assert _factor_to_confidence(0.88) == "medium-high"
    assert _factor_to_confidence(0.85) == "medium"
    assert _factor_to_confidence(0.75) == "medium"
    assert _factor_to_confidence(0.70) == "medium-low"
    assert _factor_to_confidence(0.60) == "medium-low"
    assert _factor_to_confidence(0.50) == "low"
    assert _factor_to_confidence(0.00) == "low"


def test_downgrade():
    assert _downgrade("high")        == "medium-high"
    assert _downgrade("medium-high") == "medium"
    assert _downgrade("low")         == "low"          # 더 이상 내려갈 수 없음
    assert _downgrade("medium", 2)   == "low"


# ─── compute_signals 기본 ────────────────────────────────────

def test_compute_signals_returns_bundles():
    """전체 mock Feature → SignalBundle 목록 생성."""
    rows   = run_all_features_mock()
    bundles = compute_signals(rows)
    assert len(bundles) > 0
    for b in bundles:
        assert isinstance(b, SignalBundle)
        assert 0.0 <= b.s_priority <= 1.0, f"s_priority 범위 초과: {b.sigucode}"
        assert b.state_band in VALID_STATES,     f"잘못된 state_band: {b.state_band}"
        assert b.confidence in VALID_CONFIDENCE, f"잘못된 confidence: {b.confidence}"
        for sig in b.signal_details:
            assert sig["kind"] in VALID_SIGNALS
            assert 0.0 <= sig["score"] <= 1.0


def test_compute_signals_sorted_by_priority():
    """S_priority 내림차순 정렬 확인."""
    bundles = compute_signals(run_all_features_mock())
    scores  = [b.s_priority for b in bundles]
    assert scores == sorted(scores, reverse=True)


def test_compute_signals_all_sigucode_covered():
    """27개 시군구 모두 SignalBundle 출력."""
    bundles = compute_signals(run_all_features_mock())
    sigucodes = {b.sigucode for b in bundles}
    assert len(sigucodes) == 27, f"시군구 수 불일치: {len(sigucodes)}"


# ─── 곡성군 시나리오 회고 검증 ─────────────────────────────────

def test_gokseong_scenario():
    """
    곡성군(4672000000) — 2025-01-22 산불 회고.
    기대: S_priority >= 0.60 (PriorityPreWatering 이상)
    """
    bundles = compute_signals(run_all_features_mock())
    gk = next((b for b in bundles if b.sigucode == "4672000000"), None)
    assert gk is not None, "곡성군 SignalBundle 없음"

    # S_priority 임계
    assert gk.s_priority >= 0.60, f"곡성군 S_priority 낮음: {gk.s_priority:.4f}"

    # State Band: PriorityPreWatering 이상
    assert gk.state_band in ("PriorityPreWatering", "ImmediatePreWatering"), \
        f"곡성군 state_band 예상 외: {gk.state_band}"

    # 개별 Signal 확인
    sig = {s["kind"]: s["score"] for s in gk.signal_details}
    assert sig["S_official"] >= 0.60,  f"S_official: {sig['S_official']:.4f}"
    assert sig["S_exposure"] >= 0.55,  f"S_exposure: {sig['S_exposure']:.4f}"
    assert sig["S_spread"]   >= 0.70,  f"S_spread: {sig['S_spread']:.4f}"
    assert sig["S_time"]     >= 0.55,  f"S_time: {sig['S_time']:.4f}"


def test_gokseong_top_ranked():
    """곡성군이 전체 시군구 중 S_priority 1위여야 함 (산불 시나리오 일관성)."""
    bundles = compute_signals(run_all_features_mock())
    assert bundles[0].sigucode == "4672000000", \
        f"1위 예상 곡성군, 실제: {bundles[0].sigun} ({bundles[0].s_priority:.4f})"


# ─── S_action stub ───────────────────────────────────────────

def test_s_action_stub():
    """S_action은 C-1 stub → 모든 시군구 0.5, mock_input=True."""
    bundles = compute_signals(run_all_features_mock())
    for b in bundles:
        sig = {s["kind"]: s for s in b.signal_details}
        assert sig["S_action"]["score"] == 0.50, f"{b.sigun} S_action != 0.5"
        assert sig["S_action"]["confidence"] == "low"
    # mock_input flag는 S_action stub 때문에 항상 True
    assert all(b.mock_input for b in bundles)


# ─── S_time partial coverage ─────────────────────────────────

def test_s_time_partial_coverage():
    """S_time: 55% weight coverage → confidence medium 이하."""
    bundles = compute_signals(run_all_features_mock())
    for b in bundles:
        sig = {s["kind"]: s for s in b.signal_details}
        # medium-low 이하 (격하 적용됨)
        assert sig["S_time"]["confidence"] in ("medium-low", "low"), \
            f"{b.sigun} S_time confidence 높음: {sig['S_time']['confidence']}"


# ─── State Band 임계 검증 (C-2: apply_overrides로 교체) ──────

def test_state_band_thresholds():
    """S_priority → State Band 임계 매핑 검증."""
    from app.services.reasoning import apply_overrides, OverrideContext
    ctx = OverrideContext()
    assert apply_overrides(0.85, ctx)[0] == "ImmediatePreWatering"
    assert apply_overrides(0.70, ctx)[0] == "PriorityPreWatering"
    assert apply_overrides(0.50, ctx)[0] == "ReviewPreWatering"
    assert apply_overrides(0.30, ctx)[0] == "EnhancedMonitoring"
    assert apply_overrides(0.10, ctx)[0] == "GeneralManagement"


def test_override_grade_severe():
    """Override 8: GradeSevere → 최소 PriorityPreWatering."""
    from app.services.reasoning import apply_overrides, OverrideContext
    band, ov = apply_overrides(0.10, OverrideContext(risk_grade="매우높음"))
    assert band == "PriorityPreWatering"
    assert ov   == "GradeSevere"


def test_override_grade_high():
    """Override 9: GradeHigh → 최소 ReviewPreWatering."""
    from app.services.reasoning import apply_overrides, OverrideContext
    band, ov = apply_overrides(0.10, OverrideContext(risk_grade="높음"))
    assert band == "ReviewPreWatering"
    assert ov   == "GradeHigh"


def test_override_does_not_downgrade():
    """Override는 격상만, 격하 없음."""
    from app.services.reasoning import apply_overrides, OverrideContext
    band, ov = apply_overrides(0.85, OverrideContext(risk_grade="높음"))
    assert band == "ImmediatePreWatering"
    assert ov   == "none"


# ─── OverrideContext 전달 테스트 ─────────────────────────────

def test_risk_override_applied_to_compute():
    """compute_signals에 OverrideContext 전달 → 등급 Override 반영."""
    from app.services.reasoning import OverrideContext
    rows      = run_all_features_mock()
    overrides = {"4691000000": OverrideContext(risk_grade="매우높음", risk_index=95.0)}
    bundles   = compute_signals(rows, override_map=overrides)
    sinan = next(b for b in bundles if b.sigucode == "4691000000")
    assert sinan.state_band in ("PriorityPreWatering", "ImmediatePreWatering")
    assert sinan.override_applied == "GradeSevere"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
