# C-1 / C-2: 5 Signal 종합 + S_priority + 9 Override 풀버전
# 출처: docs/06_decision-logic.md §Signal Formulas, §State Transition, §Confidence Ordinal
#
# C-1 구현 범위:
#   ✅ S_official / S_exposure / S_spread — B-1~B-3 Feature
#   ⚠  S_action — WateringActionability 미구현 → stub(0.5, low)
#   ⚠  S_time   — 가용 weight 0.55 → 재조정 + confidence 격하
#   ✅ S_priority / State Band / Override 8-9
#
# C-2 추가 구현:
#   ✅ Override 1: HazardGate   (F_action_safety.class = 작업불가)
#   ✅ Override 2: AccessGate   (infeasible_dispatch or vehicle_not_accessible)
#   ✅ Override 3: RainGate     (F_time_rain > 0.6)
#   ✅ Override 4: Recheck      (lifecycle: 완료 후 새 위험창/재적습)
#   ✅ Override 5: Completed    (lifecycle: 완료 후 재진입 없음)
#   ✅ Override 6: AlertSevere  (F_official_alert = 경보 → min PriorityPreWatering)
#   ✅ Override 7: AlertWarning (F_official_alert = 주의보 + S_exposure >= 0.5)
#   (8/9 C-1에서 이미 구현)
from __future__ import annotations
from dataclasses import dataclass, field


# ─── Confidence Ordinal ──────────────────────────────────────
# 출처: docs/06_decision-logic.md §Confidence Ordinal

_CONF_FACTOR: dict[str, float] = {
    "high":        1.00,
    "medium-high": 0.92,
    "medium":      0.85,
    "medium-low":  0.70,
    "low":         0.50,
}

_CONF_ORDER = ["high", "medium-high", "medium", "medium-low", "low"]


def _factor_to_confidence(f: float) -> str:
    """numeric factor → confidence ordinal."""
    if f >= 0.95: return "high"
    if f >= 0.88: return "medium-high"
    if f >= 0.75: return "medium"
    if f >= 0.60: return "medium-low"
    return "low"


def _downgrade(conf: str, steps: int = 1) -> str:
    """confidence 한 단계 격하 (partial coverage 보정용)."""
    idx = _CONF_ORDER.index(conf) if conf in _CONF_ORDER else len(_CONF_ORDER) - 1
    return _CONF_ORDER[min(idx + steps, len(_CONF_ORDER) - 1)]


# ─── State 비교 테이블 ────────────────────────────────────────
# 출처: §State Transition — 격상 Override(6~9) 비교용

_STATE_ORDER = [
    "GeneralManagement",
    "EnhancedMonitoring",
    "ReviewPreWatering",
    "PriorityPreWatering",
    "ImmediatePreWatering",
]


def _state_rank(s: str) -> int:
    """State → 순위 (높을수록 심각). Special state는 -1."""
    try:
        return _STATE_ORDER.index(s)
    except ValueError:
        return -1


# ─── Override Context ─────────────────────────────────────────
# 출처: docs/06_decision-logic.md §State Transition Override 1-9

@dataclass
class OverrideContext:
    """Override 1~9 결정에 필요한 per-segment 컨텍스트.

    Override 1/2에 필요한 WateringActionability Features는 C-2 단계에서
    mock=False로 채워짐. 기본값 False → 해당 Override 미적용(safe default).
    """
    # Override 1: HazardGate — F_action_safety.class = 작업 불가
    work_safety_notactionable: bool = False

    # Override 2: AccessGate — infeasible_dispatch 또는 vehicle 불가
    infeasible_dispatch_flag: bool = False
    vehicle_not_accessible: bool = False

    # Override 3: RainGate — F_time_rain > 0.6 (auto-extracted from fmap)
    rain_score: float = 0.0

    # Override 4/5: Lifecycle — 이전 완료 기록
    previous_completed: bool = False
    high_risk_window_new: bool = False   # 완료 후 새 위험창 발생
    wetness_recheck_due: bool = False    # 재적습 확인 필요

    # Override 6/7: Alert — auto-extracted from LargeFireRiskAlertFeature.class
    alert_class: str = "없음"
    s_exposure: float = 0.0             # C-1 계산값 (Override 7 조건)

    # Override 8/9: Grade (C-1에서 이미 사용, 여기서도 동일 처리)
    risk_grade: str = ""
    risk_index: float = 0.0


# ─── 9 Override 적용 함수 ─────────────────────────────────────
# 출처: docs/06_decision-logic.md §State Transition

def apply_overrides(s_priority: float, ctx: OverrideContext) -> tuple[str, str]:
    """
    S_priority + OverrideContext → (state_band, override_applied).

    적용 순서:
      1~3: Hard gate  — 완전 대체 (우선 종료)
      4~5: Lifecycle  — previous_completed인 경우만
      6~9: Floor 격상 — 여러 개 동시 매치 시 더 높은 State 채택
    """
    # ── 기본 State Band ──
    if s_priority >= 0.80:   base = "ImmediatePreWatering"
    elif s_priority >= 0.60: base = "PriorityPreWatering"
    elif s_priority >= 0.40: base = "ReviewPreWatering"
    elif s_priority >= 0.20: base = "EnhancedMonitoring"
    else:                    base = "GeneralManagement"

    # ── Override 1: HazardGate (항상 최우선) ──
    if ctx.work_safety_notactionable:
        return "NotActionable", "HazardGate"

    # ── Override 2: AccessGate ──
    if ctx.infeasible_dispatch_flag or ctx.vehicle_not_accessible:
        return "Deferred", "AccessGate"

    # ── Override 3: RainGate ──
    if ctx.rain_score > 0.6:
        return "MonitorOnly", "RainGate"

    # ── Override 4/5: Lifecycle (previous_completed인 segment만) ──
    if ctx.previous_completed:
        if ctx.high_risk_window_new or ctx.wetness_recheck_due:
            return "Recheck", "Recheck"
        return "Completed", "Completed"

    # ── Override 6~9: Floor 격상 (동시 매치 → 더 높은 State 채택) ──
    # 격상 후보 목록 [(target_state, override_name)] — 우선순위 순서 유지
    candidates: list[tuple[str, str]] = [(base, "none")]

    # Override 6: AlertSevere — 경보(파생) 포함
    if "경보" in ctx.alert_class:
        candidates.append(("PriorityPreWatering", "AlertSevere"))

    # Override 7: AlertWarning + S_exposure >= 0.5
    if "주의보" in ctx.alert_class and ctx.s_exposure >= 0.5:
        candidates.append(("ReviewPreWatering", "AlertWarning"))

    # Override 8: GradeSevere
    if ctx.risk_grade == "매우높음" or ctx.risk_index >= 86.0:
        candidates.append(("PriorityPreWatering", "GradeSevere"))

    # Override 9: GradeHigh
    if ctx.risk_grade == "높음" or ctx.risk_index >= 66.0:
        candidates.append(("ReviewPreWatering", "GradeHigh"))

    # 가장 높은 State 선택 (순위 동일이면 리스트 앞쪽 = 높은 우선순위)
    best_state, best_ov = max(
        candidates,
        key=lambda x: (_state_rank(x[0]), -candidates.index(x)),
    )
    return best_state, best_ov


# ─── 출력 dataclass ───────────────────────────────────────────

@dataclass
class SignalBundle:
    """시군구별 5 Signal + S_priority + State Band 결과."""
    sigucode: str
    sigun: str
    # 5 Signals
    s_official: float
    s_exposure: float
    s_spread: float
    s_action: float
    s_time: float
    # S_priority
    s_priority: float
    # State Band + Override
    state_band: str
    override_applied: str
    # Confidence
    confidence: str
    mock_input: bool
    # 발표/디버깅용
    signal_details: list[dict] = field(default_factory=list)


# ─── Signal 가중합 헬퍼 ───────────────────────────────────────

def _weighted_signal(
    feature_map: dict[str, dict],
    weights: dict[str, float],
    inv_keys: frozenset[str] = frozenset(),
) -> tuple[float, str, bool]:
    """
    가용 Feature만 사용해 가중합 계산. 누락 Feature는 weight 재조정.
    반환: (score, confidence_str, mock_input)
    """
    available = {k: v for k, v in weights.items() if k in feature_map}
    if not available:
        return 0.5, "low", True

    total_w  = sum(available.values())
    score    = 0.0
    cf_sum   = 0.0
    any_mock = False

    for fname, w in available.items():
        row    = feature_map[fname]
        raw_s  = row["score"]
        s      = (1.0 - raw_s) if fname in inv_keys else raw_s
        w_norm = w / total_w

        score    += w_norm * s
        cf_sum   += w_norm * _CONF_FACTOR.get(row["confidence"], _CONF_FACTOR["low"])
        any_mock  = any_mock or row["mock_input"]

    conf = _factor_to_confidence(cf_sum)
    if total_w < 0.80:
        conf = _downgrade(conf)

    return round(score, 4), conf, any_mock


# ─── 5 Signal 함수 ───────────────────────────────────────────

_W_OFFICIAL = {"FireRiskLevelFeature": 0.40, "FireRiskTrendFeature": 0.20, "LargeFireRiskAlertFeature": 0.40}
_W_EXPOSURE = {"ResidentialExposureFeature": 0.40, "CriticalAssetFeature": 0.35, "ForestInterfaceFeature": 0.25}
_W_SPREAD   = {"WindTowardAssetFeature": 0.40, "TerrainTowardAssetFeature": 0.25, "FuelContinuityFeature": 0.35}
_W_TIME     = {"HighRiskTimeWindowFeature": 0.35, "RainOffsetFeature": 0.20}
_INV_TIME   = frozenset({"RainOffsetFeature"})

_W_PRIORITY = {"S_official": 0.20, "S_exposure": 0.25, "S_spread": 0.20, "S_action": 0.20, "S_time": 0.15}


def _s_official(fmap): return _weighted_signal(fmap, _W_OFFICIAL)
def _s_exposure(fmap): return _weighted_signal(fmap, _W_EXPOSURE)
def _s_spread(fmap):   return _weighted_signal(fmap, _W_SPREAD)
def _s_action(_fmap):  return 0.50, "low", True   # C-1 stub
def _s_time(fmap):     return _weighted_signal(fmap, _W_TIME, inv_keys=_INV_TIME)


# ─── alert_class 보조 함수 ────────────────────────────────────

def _alert_class_from_score(score: float) -> str:
    """LargeFireRiskAlertFeature score → alert_class 문자열."""
    if score >= 1.0: return "경보(파생)"
    if score >= 0.5: return "주의보(파생)"
    return "없음"


# ─── 메인 집계 함수 ───────────────────────────────────────────

def compute_signals(
    feature_rows: list[dict],
    override_map: dict[str, OverrideContext] | None = None,
) -> list[SignalBundle]:
    """
    Feature 결과 dict 목록 → 시군구별 SignalBundle (S_priority 내림차순).

    feature_rows : run_all_features_mock() 또는 실데이터 Feature rows
    override_map : sigucode → OverrideContext (없으면 auto-extract 기본값만 사용)
                   Override 1/2/4/5에 필요한 값을 callers가 채워 넣는다.
                   Override 3/6/7은 fmap에서 자동 추출.
                   Override 8/9는 OverrideContext.risk_grade/risk_index 사용.
    """
    override_map = override_map or {}

    # sigucode별 Feature map 구성
    by_sgu: dict[str, dict[str, dict]] = {}
    sgu_name: dict[str, str] = {}
    for row in feature_rows:
        sc = row["sigucode"]
        by_sgu.setdefault(sc, {})[row["feature"]] = row
        sgu_name[sc] = row["sigun"]

    results: list[SignalBundle] = []

    for sc, fmap in by_sgu.items():
        sn = sgu_name[sc]

        # ── 5 Signal 계산 ──
        so, so_conf, so_mock = _s_official(fmap)
        se, se_conf, se_mock = _s_exposure(fmap)
        ss, ss_conf, ss_mock = _s_spread(fmap)
        sa, sa_conf, sa_mock = _s_action(fmap)
        st, st_conf, st_mock = _s_time(fmap)

        # ── S_priority ──
        sp = round(
            _W_PRIORITY["S_official"] * so
          + _W_PRIORITY["S_exposure"] * se
          + _W_PRIORITY["S_spread"]   * ss
          + _W_PRIORITY["S_action"]   * sa
          + _W_PRIORITY["S_time"]     * st,
            4,
        )

        # ── S_priority confidence ──
        sp_cf = sum(
            _W_PRIORITY[k] * _CONF_FACTOR.get(c, _CONF_FACTOR["low"])
            for k, c in [
                ("S_official", so_conf), ("S_exposure", se_conf),
                ("S_spread",   ss_conf), ("S_action",   sa_conf),
                ("S_time",     st_conf),
            ]
        )
        sp_conf = _factor_to_confidence(sp_cf)
        sp_mock = so_mock or se_mock or ss_mock or sa_mock or st_mock

        # ── Override Context 구성 (auto + caller 제공) ──
        base_ctx = override_map.get(sc, OverrideContext())

        # Override 3 자동 추출: RainOffsetFeature.score
        if "RainOffsetFeature" in fmap:
            rain_score = fmap["RainOffsetFeature"]["score"]
        else:
            rain_score = base_ctx.rain_score

        # Override 6/7 자동 추출: LargeFireRiskAlertFeature.class
        if "LargeFireRiskAlertFeature" in fmap:
            alert_row   = fmap["LargeFireRiskAlertFeature"]
            alert_class = alert_row.get("class", "없음")
            # class="mock" → score로 파생
            if alert_class in ("mock", ""):
                alert_class = _alert_class_from_score(alert_row["score"])
        else:
            alert_class = base_ctx.alert_class

        ctx = OverrideContext(
            work_safety_notactionable = base_ctx.work_safety_notactionable,
            infeasible_dispatch_flag  = base_ctx.infeasible_dispatch_flag,
            vehicle_not_accessible    = base_ctx.vehicle_not_accessible,
            rain_score                = rain_score,
            previous_completed        = base_ctx.previous_completed,
            high_risk_window_new      = base_ctx.high_risk_window_new,
            wetness_recheck_due       = base_ctx.wetness_recheck_due,
            alert_class               = alert_class,
            s_exposure                = se,          # C-1 계산값
            risk_grade                = base_ctx.risk_grade,
            risk_index                = base_ctx.risk_index,
        )

        band, override = apply_overrides(sp, ctx)

        results.append(SignalBundle(
            sigucode=sc, sigun=sn,
            s_official=so, s_exposure=se, s_spread=ss,
            s_action=sa, s_time=st,
            s_priority=sp,
            state_band=band, override_applied=override,
            confidence=sp_conf, mock_input=sp_mock,
            signal_details=[
                {"kind": "S_official", "score": so, "confidence": so_conf},
                {"kind": "S_exposure", "score": se, "confidence": se_conf},
                {"kind": "S_spread",   "score": ss, "confidence": ss_conf},
                {"kind": "S_action",   "score": sa, "confidence": sa_conf},
                {"kind": "S_time",     "score": st, "confidence": st_conf},
            ],
        ))

    results.sort(key=lambda x: x.s_priority, reverse=True)
    return results


# ─── State Band 한국어 레이블 ─────────────────────────────────

_STATE_KO: dict[str, str] = {
    "ImmediatePreWatering":  "즉시예비주수",
    "PriorityPreWatering":   "우선예비주수",
    "ReviewPreWatering":     "검토예비주수",
    "EnhancedMonitoring":    "강화모니터링",
    "GeneralManagement":     "일반관리",
    "NotActionable":         "작업불가(안전)",
    "Deferred":              "유예(접근불가)",
    "MonitorOnly":           "모니터전용(강수)",
    "Recheck":               "재점검",
    "Completed":             "완료",
}


def state_ko(state: str) -> str:
    return _STATE_KO.get(state, state)
