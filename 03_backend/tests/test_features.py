# B-2 / B-3 / B-4 검증: Exposure + SpreadToAsset + TimeUrgency Feature
# 조건: 모든 Feature가 [0,1] score + 유효한 class label + 유효한 confidence 출력
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # 프로젝트 루트

from app.services.features import (
    # B-2
    ResidentialExposureInput,
    CriticalAssetInput,
    ForestInterfaceInput,
    residential_exposure,
    critical_asset,
    forest_interface,
    run_exposure,
    # B-3
    WindTowardAssetInput,
    TerrainTowardAssetInput,
    FuelContinuityInput,
    wind_toward_asset,
    terrain_toward_asset,
    fuel_continuity,
    wind_flags_from_bearing,
    run_spread,
    # B-4
    HorizonSnapshot,
    HighRiskTimeWindowInput,
    RainOffsetInput,
    high_risk_time_window,
    rain_offset,
    run_time_urgency,
    # base
    level5,
    norm,
    inv,
)

VALID_CLASSES    = {"낮음", "다소낮음", "보통", "다소높음", "높음"}
VALID_CONFIDENCE = {"high", "medium-high", "medium", "medium-low", "low"}

# ─── 공통 헬퍼 ───────────────────────────────────────────────

def assert_result(r, expected_feature: str) -> None:
    assert r.feature == expected_feature, f"feature mismatch: {r.feature}"
    assert 0.0 <= r.score <= 1.0,         f"score out of range: {r.score}"
    assert r.cls in VALID_CLASSES,         f"invalid class: {r.cls}"
    assert r.confidence in VALID_CONFIDENCE, f"invalid confidence: {r.confidence}"


# ─── base 헬퍼 ───────────────────────────────────────────────

def test_norm_clamp():
    assert norm(-10, 0, 100) == 0.0
    assert norm(110, 0, 100) == 1.0
    assert norm(50, 0, 100) == 0.5


def test_inv():
    assert inv(0.0) == 1.0
    assert inv(1.0) == 0.0
    assert abs(inv(0.4) - 0.6) < 1e-9


# ─── ResidentialExposureFeature ──────────────────────────────

def test_residential_basic():
    r = ResidentialExposureInput(
        sigucode="4672000000", sigun="곡성군",
        residential_building_count=1800,
        residential_population=25000,
        residential_household_count=10000,
        forest_to_residence_distance_m=150,
    )
    result = residential_exposure(r)
    assert_result(result, "ResidentialExposureFeature")
    assert result.mock_input is True
    assert result.confidence == "medium-high"
    # 곡성군 시나리오: 높은 인구 밀도 + 가까운 산림 → 다소높음~높음 기대
    assert result.score >= 0.65, f"곡성군 score 낮음: {result.score}"


def test_residential_zero():
    r = ResidentialExposureInput("0000000000", "테스트", 0, 0, 0, 2000)
    result = residential_exposure(r)
    assert result.score == 0.0
    assert result.cls == "낮음"


def test_residential_max():
    r = ResidentialExposureInput("0000000000", "테스트", 5000, 30000, 12000, 0)
    result = residential_exposure(r)
    assert result.score == 1.0
    assert result.cls == "높음"


# ─── CriticalAssetFeature ────────────────────────────────────

def test_critical_asset_basic():
    c = CriticalAssetInput(
        sigucode="4673000000", sigun="구례군",
        critical_asset_count=7,
        critical_asset_class_mix={"문화재": 4, "요양시설": 1, "병원": 0, "공공시설": 2},
        critical_asset_min_distance_m=100,
    )
    result = critical_asset(c)
    assert_result(result, "CriticalAssetFeature")
    # 화엄사 등 문화재 다수 + 매우 근접 → 보통 이상 기대
    # 문화재 4개 / max_count_cap=20 → weighted_mix 0.30 수준이 정상
    assert result.score >= 0.50, f"구례군 critical score 낮음: {result.score}"


def test_critical_asset_empty():
    c = CriticalAssetInput("0000000000", "테스트", 0, {}, 2000)
    result = critical_asset(c)
    assert result.score == 0.0


def test_critical_asset_class_weight():
    """문화재 가중치(1.00) > 공공시설(0.55) 확인."""
    c_heritage = CriticalAssetInput("x", "x", 5, {"문화재": 5}, 1000)
    c_public   = CriticalAssetInput("x", "x", 5, {"공공시설": 5}, 1000)
    r_h = critical_asset(c_heritage)
    r_p = critical_asset(c_public)
    assert r_h.score > r_p.score, "문화재 score가 공공시설보다 높아야 함"


# ─── ForestInterfaceFeature ──────────────────────────────────

def test_forest_interface_basic():
    fi = ForestInterfaceInput(
        sigucode="4672000000", sigun="곡성군",
        forest_asset_distance_m=50,
        forest_asset_interface_length_m=950,
    )
    result = forest_interface(fi)
    assert_result(result, "ForestInterfaceFeature")
    assert result.confidence == "medium"
    # 산림이 매우 가깝고 접경선 길이가 길다 → 높음 기대
    assert result.score >= 0.85, f"곡성군 interface score 낮음: {result.score}"


def test_forest_interface_far():
    fi = ForestInterfaceInput("0000000000", "테스트", 2000, 0)
    result = forest_interface(fi)
    assert result.score == 0.0


# ─── run_exposure 통합 ───────────────────────────────────────

def test_run_exposure_mock():
    """mock 데이터로 전 시군구 일괄 실행 — 모든 row가 유효해야 함."""
    results = run_exposure()
    assert len(results) > 0
    features_seen = set()
    for row in results:
        assert 0.0 <= row["score"] <= 1.0, f"score 범위 초과: {row}"
        assert row["class"] in VALID_CLASSES, f"잘못된 class: {row}"
        assert row["confidence"] in VALID_CONFIDENCE, f"잘못된 confidence: {row}"
        features_seen.add(row["feature"])
    # 3 Feature 모두 출력됐는지 확인
    assert "ResidentialExposureFeature" in features_seen
    assert "CriticalAssetFeature"       in features_seen
    assert "ForestInterfaceFeature"     in features_seen


def test_run_exposure_gokseong():
    """곡성군(4672000000) — S_exposure 시나리오 회고 검증용."""
    results = run_exposure()
    gokseong = [r for r in results if r["sigucode"] == "4672000000"]
    assert len(gokseong) == 3, "곡성군 3행 출력 필요"
    scores = {r["feature"]: r["score"] for r in gokseong}
    # 곡성군은 ExposureSignal이 모두 '보통' 이상이어야 함
    for feat, score in scores.items():
        assert score >= 0.40, f"곡성군 {feat} score 낮음: {score}"


# ─── WindTowardAssetFeature ──────────────────────────────────

def test_wind_toward_asset_gokseong():
    """곡성군 2025-01-22 시나리오 — 강한 북서풍, 자산 방향 정렬 → 높음."""
    w = WindTowardAssetInput(
        sigucode="4672000000", sigun="곡성군",
        wind_toward_asset_flag=True,
        gust_toward_asset_flag=True,
        wsd=14.0, observed_wind_speed=12.0, observed_gust_speed=18.0,
    )
    result = wind_toward_asset(w)
    assert_result(result, "WindTowardAssetFeature")
    assert result.confidence == "medium"
    # 강풍 + 자산 방향 → 다소높음 이상
    assert result.score >= 0.60, f"곡성군 wind score 낮음: {result.score}"


def test_wind_no_flag():
    """풍향 불일치 → 기본 풍속 항(0.30)만 남음."""
    w = WindTowardAssetInput("x", "x", False, False, 10.0, 10.0, 0.0)
    result = wind_toward_asset(w)
    # F = 0 + 0 + 0.30 * norm(10, 0, 20) = 0.30 * 0.5 = 0.15
    assert abs(result.score - 0.15) < 0.001, f"score 오차: {result.score}"


def test_wind_zero():
    """무풍 → score 0."""
    w = WindTowardAssetInput("x", "x", False, False, 0.0, 0.0, 0.0)
    assert wind_toward_asset(w).score == 0.0


def test_wind_flags_from_bearing():
    """북서풍(VEC=315) → 남동 방향(135°) 자산을 향함."""
    wf, gf = wind_flags_from_bearing(bearing_to_asset_deg=135.0, vec=315)
    assert wf is True, "북서풍은 남동 자산 방향"
    assert gf is True

    # 반대 방향 자산(북서 315°)에는 not toward
    wf2, gf2 = wind_flags_from_bearing(bearing_to_asset_deg=315.0, vec=315)
    assert wf2 is False, "북서풍은 북서 자산 방향 아님"


# ─── TerrainTowardAssetFeature ───────────────────────────────

def test_terrain_all_classes():
    """4개 방위 클래스 lookup 정확성 검증."""
    cases = [("정면", 1.00), ("사면-가까움", 0.65), ("사면-먼", 0.35), ("외면", 0.00)]
    for cls, expected in cases:
        t = TerrainTowardAssetInput("x", "x", cls)
        result = terrain_toward_asset(t)
        assert abs(result.score - expected) < 0.001, f"{cls}: {result.score} ≠ {expected}"
        assert result.confidence == "medium-low"


def test_terrain_gokseong():
    """곡성군 — 협곡 정면 노출 → score 1.0."""
    t = TerrainTowardAssetInput("4672000000", "곡성군", "정면")
    result = terrain_toward_asset(t)
    assert result.score == 1.0
    assert result.cls == "높음"


# ─── FuelContinuityFeature ───────────────────────────────────

def test_fuel_max():
    """연속·0단절·조밀 → 거의 1.0."""
    fc = FuelContinuityInput("x", "x", "연속", 0, "조밀")
    result = fuel_continuity(fc)
    # F = 0.40*1.0 + 0.25*inv(0) + 0.35*1.0 = 0.40+0.25+0.35 = 1.0
    assert result.score == 1.0


def test_fuel_min():
    """단절·10단절·미입목 → score 0."""
    fc = FuelContinuityInput("x", "x", "단절", 10, "미입목")
    result = fuel_continuity(fc)
    # F = 0.40*0 + 0.25*inv(1.0) + 0.35*0 = 0
    assert result.score == 0.0


def test_fuel_gokseong():
    """곡성군 — 연속·1단절·조밀 → 높음."""
    fc = FuelContinuityInput("4672000000", "곡성군", "연속", 1, "조밀")
    result = fuel_continuity(fc)
    assert result.confidence == "medium-high"
    assert result.score >= 0.85, f"곡성군 fuel score 낮음: {result.score}"


def test_fuel_urban():
    """광주 서구 — 단절·9단절·성긴 → 낮음."""
    fc = FuelContinuityInput("2914000000", "서구", "단절", 9, "성긴")
    result = fuel_continuity(fc)
    assert result.score < 0.20, f"서구 fuel score 너무 높음: {result.score}"


# ─── run_spread 통합 ─────────────────────────────────────────

def test_run_spread_mock():
    """mock 데이터로 전 시군구 일괄 실행 — 모든 row 유효."""
    results = run_spread()
    assert len(results) > 0
    features_seen = set()
    for row in results:
        assert 0.0 <= row["score"] <= 1.0, f"score 범위 초과: {row}"
        assert row["class"] in VALID_CLASSES, f"잘못된 class: {row}"
        assert row["confidence"] in VALID_CONFIDENCE, f"잘못된 confidence: {row}"
        features_seen.add(row["feature"])
    assert "WindTowardAssetFeature"    in features_seen
    assert "TerrainTowardAssetFeature" in features_seen
    assert "FuelContinuityFeature"     in features_seen


def test_run_spread_gokseong():
    """곡성군 — SpreadToAssetSignal 시나리오 회고 검증용."""
    results = run_spread()
    gokseong = [r for r in results if r["sigucode"] == "4672000000"]
    assert len(gokseong) == 3, "곡성군 3행 출력 필요"
    scores = {r["feature"]: r["score"] for r in gokseong}
    # 곡성군은 Spread 3 Feature 모두 '보통' 이상이어야 함
    for feat, score in scores.items():
        assert score >= 0.40, f"곡성군 {feat} score 낮음: {score}"
    # Wind + Terrain은 '다소높음' 이상 기대
    assert scores["WindTowardAssetFeature"]    >= 0.60
    assert scores["TerrainTowardAssetFeature"] >= 0.60


# ─── HighRiskTimeWindowFeature ───────────────────────────────

def test_time_window_gokseong():
    """곡성군 2025-01-22 — 건조·강풍·고위험, 2시간 후 최고조 → 높음."""
    inp = HighRiskTimeWindowInput(
        sigucode="4672000000", sigun="곡성군",
        horizons=[
            HorizonSnapshot(risk_grade_score=0.75, reh=25, wsd=14.0, tmp=8.0),
            HorizonSnapshot(risk_grade_score=0.75, reh=22, wsd=16.0, tmp=6.0),
        ],
        hours_to_peak=2.0,
    )
    result = high_risk_time_window(inp)
    assert_result(result, "HighRiskTimeWindowFeature")
    assert result.confidence == "medium"
    # imminence(2) = 1.0, danger 높음 → 다소높음 이상
    assert result.score >= 0.60, f"곡성군 time_window 낮음: {result.score}"


def test_time_window_imminence():
    """imminence 계수: 시간대별 decay 확인."""
    base_horizon = [HorizonSnapshot(0.80, 25, 14.0, 10.0)]
    scores = {}
    for h, label in [(1.0, "<3h"), (6.0, "<12h"), (18.0, "<24h"), (36.0, "<48h"), (72.0, "72h+")]:
        inp = HighRiskTimeWindowInput("x", "x", base_horizon, h)
        scores[label] = high_risk_time_window(inp).score
    # 시간이 길수록 score가 낮아야 함
    assert scores["<3h"] > scores["<12h"] > scores["<24h"] > scores["<48h"] > scores["72h+"]


def test_time_window_single_horizon():
    """단일 스냅샷 — 리스트 처리 정상."""
    inp = HighRiskTimeWindowInput(
        "x", "x",
        [HorizonSnapshot(0.50, 55, 5.0, 20.0)],
        hours_to_peak=24.0,
    )
    result = high_risk_time_window(inp)
    assert 0.0 <= result.score <= 1.0


def test_time_window_max_across_horizons():
    """여러 시점 중 최대 danger를 사용하는지 확인."""
    low  = HorizonSnapshot(0.20, 80, 2.0, 5.0)   # 낮은 위험
    high = HorizonSnapshot(0.80, 20, 18.0, 30.0) # 높은 위험

    inp_low_first  = HighRiskTimeWindowInput("x", "x", [low, high], 5.0)
    inp_high_first = HighRiskTimeWindowInput("x", "x", [high, low], 5.0)
    # 순서 관계없이 같은 score
    assert high_risk_time_window(inp_low_first).score == high_risk_time_window(inp_high_first).score


# ─── RainOffsetFeature ───────────────────────────────────────

def test_rain_offset_no_rain():
    """강수 없음 → score 0 → inv() = 1.0 → 주수 긴급성 최고."""
    inp = RainOffsetInput("4672000000", "곡성군", 0.0, 3.0, 0.0)
    result = rain_offset(inp)
    assert result.score == 0.0
    assert result.cls == "낮음"
    assert result.confidence == "medium"
    # S_time에서는 inv(0.0) = 1.0 사용됨


def test_rain_offset_heavy_rain():
    """강한 강수 → score 높음 → inv() 낮아 주수 필요성 감소."""
    inp = RainOffsetInput("x", "x",
        expected_rainfall_mm=25.0,
        rain_probability=90.0,
        rain_duration_hr=8.0,
    )
    result = rain_offset(inp)
    assert result.score >= 0.60, f"강수 score 낮음: {result.score}"
    assert result.cls in {"다소높음", "높음"}


def test_rain_offset_zero_probability():
    """강수 확률 0 → score 0 (확률 항이 0으로 곱함)."""
    inp = RainOffsetInput("x", "x", 20.0, 0.0, 5.0)
    result = rain_offset(inp)
    assert result.score == 0.0


def test_rain_offset_formula_components():
    """clip(norm(dur, [0,12]) + 0.3, 0, 1) 검증: dur=0 → 0.3 가중치."""
    # dur=0: clip(0+0.3, 0, 1) = 0.3
    # mm=15: norm(15, 0, 30) = 0.5
    # prob=80: norm(80, 0, 100) = 0.8
    # F = 0.5 * 0.8 * 0.3 = 0.12
    inp = RainOffsetInput("x", "x", 15.0, 80.0, 0.0)
    result = rain_offset(inp)
    assert abs(result.score - 0.12) < 0.001, f"score: {result.score}"


# ─── run_time_urgency 통합 ────────────────────────────────────

def test_run_time_urgency_mock():
    """mock 데이터로 전 시군구 일괄 실행 — 모든 row 유효."""
    results = run_time_urgency()
    assert len(results) > 0
    features_seen = set()
    for row in results:
        assert 0.0 <= row["score"] <= 1.0, f"score 범위 초과: {row}"
        assert row["class"] in VALID_CLASSES, f"잘못된 class: {row}"
        assert row["confidence"] in VALID_CONFIDENCE, f"잘못된 confidence: {row}"
        features_seen.add(row["feature"])
    assert "HighRiskTimeWindowFeature" in features_seen
    assert "RainOffsetFeature"         in features_seen


def test_run_time_urgency_gokseong():
    """곡성군 — TimeUrgency 시나리오 회고 검증."""
    results = run_time_urgency()
    gokseong = [r for r in results if r["sigucode"] == "4672000000"]
    assert len(gokseong) == 2, "곡성군 2행 출력 필요"
    scores = {r["feature"]: r["score"] for r in gokseong}
    # HighRiskTimeWindow: 다소높음 이상
    assert scores["HighRiskTimeWindowFeature"] >= 0.60
    # RainOffset: 강수 없음 → score 0
    assert scores["RainOffsetFeature"] == 0.0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
