# services/reasoning.py
# 역할: TypeDB 쿼리 로직 — 서비스 레이어
# 출처: load_dol.py (STEP 4-6 로직 재사용)
#        v01_decision_lineage.tql (lineage 쿼리 로직)

from datetime import datetime, timedelta

from typedb.driver import TransactionType

from app.typedb_client import get_driver, get_value, DB_NAME
from app.models import (
    SegmentSummary, SegmentDetail,
    FeatureItem, SignalItem, StatusStep,
    LineageItem, InferenceResult,
    TraceIO, TraceStep, InferenceTraceResponse,
    SegmentThresholdResult,
)
from app.services.reasoning.signals import apply_overrides, OverrideContext


# ── B-1: mock status_history 생성 ──
# TypeDB에 실행 이력이 없으므로 현재 시각 기준 역산 mock

_STATUS_META = [
    ("init",           "데이터 로드",    "구간 원본 속성 로드"),
    ("calc-features",  "Feature 계산",  "FireRiskLevel · ResidentialExposure · WindTowardAsset"),
    ("calc-signals",   "Signal 집계",   "S_official · S_exposure · S_spread · S_action · S_time"),
    ("apply-override", "Override 체크", "9 Override 우선순위 순서대로 체크"),
    ("decide",         "State 결정",    "S_priority → 5 Band + Override 격상"),
    ("audit",          "Lineage 저장",  "결정 근거 역추적 가능하게 저장"),
]

def _make_status_history() -> list[StatusStep]:
    base = datetime.now() - timedelta(seconds=len(_STATUS_META) * 1.2)
    return [
        StatusStep(
            name=name, label=label, completed=True,
            timestamp=(base + timedelta(seconds=i * 1.2)).strftime("%H:%M:%S"),
            description=desc,
        )
        for i, (name, label, desc) in enumerate(_STATUS_META)
    ]


# ══════════════════════════════════════════════════════════
# 공개 서비스 함수
# ══════════════════════════════════════════════════════════

def get_all_raw_signals() -> list[dict]:
    """몬테카를로 시뮬레이션용 — 모든 구간의 5개 Signal 원시값 반환."""
    query = """
    match
      $seg isa pre-watering-segment,
        has segment-id $id,
        has segment-name $nm,
        has s-official-score $s_off,
        has residential-exposure-score $re,
        has s-spread-mock $s_spread,
        has s-action-mock $s_action,
        has s-time-mock $s_time;
    select $id, $nm, $s_off, $re, $s_spread, $s_action, $s_time;
    """
    results = []
    with get_driver() as driver:
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            for row in tx.query(query).resolve():
                results.append({
                    "segment_id":   str(get_value(row.get("id"))),
                    "segment_name": str(get_value(row.get("nm"))),
                    "s_official":   float(get_value(row.get("s_off"))    or 0),
                    "s_exposure":   float(get_value(row.get("re"))        or 0),
                    "s_spread":     float(get_value(row.get("s_spread"))  or 0),
                    "s_action":     float(get_value(row.get("s_action"))  or 0),
                    "s_time":       float(get_value(row.get("s_time"))    or 0),
                })
    return results


def get_all_segments() -> list[SegmentSummary]:
    """
    GET /api/segments — 전체 구간 목록 (segment-decision JOIN)
    """
    query = """
    match
      $seg isa pre-watering-segment,
        has segment-id $id,
        has segment-name $nm;
      $r-dec isa segment-decision, links (subject: $seg, outcome: $ds);
      $ds has state-band $state,
           has s-priority $sp,
           has override-applied $ov;
    select $id, $nm, $state, $sp, $ov;
    """
    results = []
    with get_driver() as driver:
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = tx.query(query).resolve()
            for row in rows:
                results.append(SegmentSummary(
                    segment_id=str(get_value(row.get("id"))),
                    segment_name=str(get_value(row.get("nm"))),
                    state_band=str(get_value(row.get("state"))),
                    s_priority=float(get_value(row.get("sp")) or 0.0),
                    override_applied=str(get_value(row.get("ov"))),
                ))
    return results


def get_segment_detail(segment_id: str) -> SegmentDetail | None:
    """
    GET /api/segments/{id} — 구간 상세 (feature + signal 포함)
    """
    # 기본 속성 + decision-state 조회
    base_query = f"""
    match
      $seg isa pre-watering-segment,
        has segment-id "{segment_id}",
        has segment-name $nm,
        has hazard-flag $hf,
        has risk-grade $rg,
        has risk-index $ri;
      $r-dec isa segment-decision, links (subject: $seg, outcome: $ds);
      $ds has state-band $state,
           has s-priority $sp,
           has override-applied $ov;
    select $nm, $hf, $rg, $ri, $state, $sp, $ov;
    """
    # feature 조회
    feat_query = f"""
    match
      $seg isa pre-watering-segment, has segment-id "{segment_id}";
      $r-feat isa segment-feature, links (subject: $seg, result: $fr);
      $fr has feature-kind $fk,
           has feature-score $fs,
           has feature-class $fc;
    select $fk, $fs, $fc;
    """
    # signal 조회
    sig_query = f"""
    match
      $seg isa pre-watering-segment, has segment-id "{segment_id}";
      $r-sig isa segment-signal, links (subject: $seg, result: $sr);
      $sr has signal-kind $sk,
           has signal-score $ss;
    select $sk, $ss;
    """

    with get_driver() as driver:
        # 기본 정보
        base_row = None
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = list(tx.query(base_query).resolve())
            if not rows:
                return None
            base_row = rows[0]

        nm    = str(get_value(base_row.get("nm")))
        hf    = bool(get_value(base_row.get("hf")))
        rg    = str(get_value(base_row.get("rg")))
        ri    = float(get_value(base_row.get("ri")) or 0.0)
        state = str(get_value(base_row.get("state")))
        sp    = float(get_value(base_row.get("sp")) or 0.0)
        ov    = str(get_value(base_row.get("ov")))

        # feature 목록
        features = []
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = tx.query(feat_query).resolve()
            for row in rows:
                features.append(FeatureItem(
                    kind=str(get_value(row.get("fk"))),
                    score=float(get_value(row.get("fs")) or 0.0),
                    feature_class=str(get_value(row.get("fc"))),
                ))

        # signal 목록
        signals = []
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = tx.query(sig_query).resolve()
            for row in rows:
                signals.append(SignalItem(
                    kind=str(get_value(row.get("sk"))),
                    score=float(get_value(row.get("ss")) or 0.0),
                ))

    return SegmentDetail(
        segment_id=segment_id,
        segment_name=nm,
        state_band=state,
        s_priority=sp,
        override_applied=ov,
        hazard_flag=hf,
        risk_grade=rg,
        risk_index=ri,
        features=features,
        signals=signals,
        status_history=_make_status_history(),  # B-1 mock
    )


def get_segment_lineage(segment_id: str) -> list[LineageItem]:
    """
    GET /api/segments/{id}/lineage — v01_decision_lineage 로직
    Feature × Signal Cartesian 결과를 LineageItem 목록으로 반환
    """
    query = f"""
    match
      $seg isa pre-watering-segment,
        has segment-id "{segment_id}",
        has segment-name $seg-name;
      $r-dec isa segment-decision, links (subject: $seg, outcome: $ds);
      $ds has state-band $state,
           has s-priority $sp,
           has override-applied $override;
      $r-feat isa segment-feature, links (subject: $seg, result: $fr);
      $fr has feature-kind $f-kind,
           has feature-score $f-score;
      $r-sig isa segment-signal, links (subject: $seg, result: $sr);
      $sr has signal-kind $sig-kind,
           has signal-score $sig-score;
    select $seg-name, $state, $override, $sp, $f-kind, $f-score, $sig-kind, $sig-score;
    """
    results = []
    with get_driver() as driver:
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = tx.query(query).resolve()
            for row in rows:
                results.append(LineageItem(
                    segment_id=segment_id,
                    segment_name=str(get_value(row.get("seg-name"))),
                    state_band=str(get_value(row.get("state"))),
                    s_priority=float(get_value(row.get("sp")) or 0.0),
                    override_applied=str(get_value(row.get("override"))),
                    feature_kind=str(get_value(row.get("f-kind"))),
                    feature_score=float(get_value(row.get("f-score")) or 0.0),
                    signal_kind=str(get_value(row.get("sig-kind"))),
                    signal_score=float(get_value(row.get("sig-score")) or 0.0),
                ))
    return results


def run_inference() -> InferenceResult:
    """
    POST /api/inference/run — 추론 재실행
    기존 feature-record / signal-record / decision-state 삭제 후 재삽입
    (DB 재생성 없음 — 원본 segment 데이터 유지)
    """
    with get_driver() as driver:

        # ── 1단계: 기존 추론 결과 삭제 ──
        # 관계(relation)를 먼저 삭제하고 이후 엔티티 삭제
        # (TypeDB: 관계가 참조 중인 엔티티는 삭제 불가)
        delete_queries = [
            # 관계 먼저 삭제 (TypeDB: 관계가 참조 중인 엔티티 직접 삭제 불가)
            "match $r isa segment-feature; delete $r;",
            "match $r isa segment-signal; delete $r;",
            "match $r isa segment-decision; delete $r;",
            # 엔티티 삭제
            "match $x isa feature-record; delete $x;",
            "match $x isa signal-record; delete $x;",
            "match $x isa decision-state; delete $x;",
        ]
        for dq in delete_queries:
            with driver.transaction(DB_NAME, TransactionType.WRITE) as tx:
                tx.query(dq).resolve()
                tx.commit()

        # ── 2단계: 원본 segment 속성 읽기 ──
        fetch_q = """
        match
          $seg isa pre-watering-segment,
            has segment-id $id,
            has segment-name $nm,
            has hazard-flag $hf,
            has risk-grade $rg,
            has risk-index $ri,
            has fire-risk-level-score $fl,
            has residential-exposure-score $re,
            has wind-toward-asset-score $wa,
            has s-official-score $s_off,
            has s-spread-mock $s_spread,
            has s-action-mock $s_action,
            has s-time-mock $s_time;
        select $id, $nm, $hf, $rg, $ri, $fl, $re, $wa, $s_off, $s_spread, $s_action, $s_time;
        """
        segments = []
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = tx.query(fetch_q).resolve()
            for row in rows:
                raw = {
                    "id":      str(get_value(row.get("id"))),
                    "name":    str(get_value(row.get("nm"))),
                    "hf":      bool(get_value(row.get("hf"))),
                    "grade":   str(get_value(row.get("rg"))),
                    "idx":     float(get_value(row.get("ri")) or 0),
                    "fl":      float(get_value(row.get("fl")) or 0),
                    "re":      float(get_value(row.get("re")) or 0),
                    "wa":      float(get_value(row.get("wa")) or 0),
                    "s_off":   float(get_value(row.get("s_off")) or 0),
                    "s_spread":float(get_value(row.get("s_spread")) or 0),
                    "s_action":float(get_value(row.get("s_action")) or 0),
                    "s_time":  float(get_value(row.get("s_time")) or 0),
                }
                # S_priority 계산 (Python)
                # 출처: CLAUDE.md §발표 핵심 수식
                raw["sp"] = (
                    0.20 * raw["s_off"]
                    + 0.25 * raw["re"]
                    + 0.20 * raw["s_spread"]
                    + 0.20 * raw["s_action"]
                    + 0.15 * raw["s_time"]
                )
                segments.append(raw)

        if not segments:
            return InferenceResult(
                success=False,
                message="segment 데이터 없음 — load_dol.py를 먼저 실행해 주세요",
                segments_processed=0,
            )

        # ── 3단계: feature-record INSERT ──
        for seg in segments:
            q = f"""
            match $seg isa pre-watering-segment, has segment-id "{seg['id']}";
            insert
              $fr1 isa feature-record,
                has feature-kind "FireRiskLevel",
                has feature-score {seg['fl']:.4f},
                has feature-class "official-risk";
              (subject: $seg, result: $fr1) isa segment-feature;
              $fr2 isa feature-record,
                has feature-kind "ResidentialExposure",
                has feature-score {seg['re']:.4f},
                has feature-class "exposure";
              (subject: $seg, result: $fr2) isa segment-feature;
              $fr3 isa feature-record,
                has feature-kind "WindTowardAsset",
                has feature-score {seg['wa']:.4f},
                has feature-class "spread";
              (subject: $seg, result: $fr3) isa segment-feature;
            """
            with driver.transaction(DB_NAME, TransactionType.WRITE) as tx:
                tx.query(q).resolve()
                tx.commit()

        # ── 4단계: signal-record INSERT ──
        for seg in segments:
            q = f"""
            match $seg isa pre-watering-segment, has segment-id "{seg['id']}";
            insert
              $sr1 isa signal-record,
                has signal-kind "S_official",
                has signal-score {seg['s_off']:.4f};
              (subject: $seg, result: $sr1) isa segment-signal;
              $sr2 isa signal-record,
                has signal-kind "S_exposure",
                has signal-score {seg['re']:.4f};
              (subject: $seg, result: $sr2) isa segment-signal;
            """
            with driver.transaction(DB_NAME, TransactionType.WRITE) as tx:
                tx.query(q).resolve()
                tx.commit()

        # ── 5단계: decision-state INSERT (9 Override 전체 적용) ──
        for seg in segments:
            sp    = float(seg["sp"])
            re    = float(seg["re"])
            grade = str(seg["grade"])
            idx   = float(seg["idx"])
            ctx = OverrideContext(
                work_safety_notactionable=bool(seg["hf"]),
                risk_grade=grade,
                risk_index=idx,
                s_exposure=re,
            )
            state, ov = apply_overrides(sp, ctx)

            insert_q = f"""
            match $seg isa pre-watering-segment, has segment-id "{seg['id']}";
            insert
              $ds isa decision-state,
                has state-band "{state}",
                has s-priority {sp:.4f},
                has override-applied "{ov}";
              (subject: $seg, outcome: $ds) isa segment-decision;
            """
            with driver.transaction(DB_NAME, TransactionType.WRITE) as tx:
                tx.query(insert_q).resolve()
                tx.commit()

    return InferenceResult(
        success=True,
        message=f"추론 재실행 완료 — feature/signal/decision 재계산됨",
        segments_processed=len(segments),
    )


# ══════════════════════════════════════════════════════════
# B-4: 함수 추론 3단계 라이브 뷰
# GET /api/segments/{id}/inference-trace
# ══════════════════════════════════════════════════════════

_LEVEL5 = {
    (0.00, 0.20): "낮음", (0.20, 0.40): "다소낮음",
    (0.40, 0.60): "보통", (0.60, 0.80): "다소높음", (0.80, 1.01): "높음",
}

def _level5(s: float) -> str:
    for (lo, hi), label in _LEVEL5.items():
        if lo <= s < hi:
            return label
    return "높음"


_SNIPPET_FEATURES = """\
# i01_compute_features.tql
match
  $seg isa pre-watering-segment;
  $seg has fire-risk-level-score $fl;
  $seg has residential-exposure-score $re;
  $seg has wind-toward-asset-score $wa;
insert
  $fr1 isa feature-record,
    has feature-kind "FireRiskLevel",
    has feature-score $fl,
    has feature-class "official-risk";
  (subject: $seg, result: $fr1) isa segment-feature;
  $fr2 isa feature-record,
    has feature-kind "ResidentialExposure",
    has feature-score $re,
    has feature-class "exposure";
  (subject: $seg, result: $fr2) isa segment-feature;
  $fr3 isa feature-record,
    has feature-kind "WindTowardAsset",
    has feature-score $wa,
    has feature-class "spread";
  (subject: $seg, result: $fr3) isa segment-feature;"""

_SNIPPET_SIGNALS = """\
# 03_signals.tql — compute_s_priority()
fun compute_s_priority(
  $seg: pre-watering-segment
) -> double:
  match
    $seg has s-official-score $so;
    $seg has residential-exposure-score $re;
    $seg has s-spread-mock $ss;
    $seg has s-action-mock $sa;
    $seg has s-time-mock $st;
  return
    0.20 * $so + 0.25 * $re
    + 0.20 * $ss + 0.20 * $sa
    + 0.15 * $st;"""

_SNIPPET_DECIDE = """\
# i03_apply_state.tql — Override 8: GradeSevere
match
  $seg isa pre-watering-segment,
    has hazard-flag false;
  { $seg has risk-grade "매우높음"; } or
  { $seg has risk-index $idx; $idx >= 86.0; };
  let $sp = compute_s_priority($seg);
  $sp < 0.60;
insert
  $ds isa decision-state,
    has state-band "PriorityPreWatering",
    has s-priority $sp,
    has override-applied "GradeSevere";
  (subject: $seg, outcome: $ds) isa segment-decision;"""


def get_inference_trace(segment_id: str) -> InferenceTraceResponse | None:
    """
    GET /api/segments/{id}/inference-trace
    TypeDB에서 구간 원본 속성을 읽어 3단계 추론 trace를 구성.
    """
    query = f"""
    match
      $seg isa pre-watering-segment,
        has segment-id "{segment_id}",
        has segment-name $nm,
        has hazard-flag $hf,
        has risk-grade $rg,
        has risk-index $ri,
        has fire-risk-level-score $fl,
        has residential-exposure-score $re,
        has wind-toward-asset-score $wa,
        has s-official-score $s_off,
        has s-spread-mock $s_spread,
        has s-action-mock $s_action,
        has s-time-mock $s_time;
    select $nm, $hf, $rg, $ri, $fl, $re, $wa, $s_off, $s_spread, $s_action, $s_time;
    """
    with get_driver() as driver:
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = list(tx.query(query).resolve())

    if not rows:
        return None

    row = rows[0]
    nm       = str(get_value(row.get("nm")))
    hf       = bool(get_value(row.get("hf")))
    grade    = str(get_value(row.get("rg")))
    idx      = float(get_value(row.get("ri")) or 0)
    fl       = float(get_value(row.get("fl")) or 0)
    re       = float(get_value(row.get("re")) or 0)
    wa       = float(get_value(row.get("wa")) or 0)
    s_off    = float(get_value(row.get("s_off")) or 0)
    s_spread = float(get_value(row.get("s_spread")) or 0)
    s_action = float(get_value(row.get("s_action")) or 0)
    s_time   = float(get_value(row.get("s_time")) or 0)

    # S_priority 재계산 (Python)
    sp = round(0.20*s_off + 0.25*re + 0.20*s_spread + 0.20*s_action + 0.15*s_time, 4)

    # Override/State 결정 (9 Override 전체 적용)
    ctx = OverrideContext(
        work_safety_notactionable=hf,
        risk_grade=grade,
        risk_index=idx,
        s_exposure=re,
    )
    state, override = apply_overrides(sp, ctx)

    # Base State (Override 이전)
    if sp >= 0.80:   base = "ImmediatePreWatering"
    elif sp >= 0.60: base = "PriorityPreWatering"
    elif sp >= 0.40: base = "ReviewPreWatering"
    elif sp >= 0.20: base = "EnhancedMonitoring"
    else:            base = "GeneralManagement"

    # ── Step 1: Feature 계산 ──
    step1 = TraceStep(
        step=1, name="calc_features", label="① Feature 계산",
        inputs=[
            TraceIO(key="fire_risk_level_score",       value=round(fl, 4),  label="산림청 위험등급 점수"),
            TraceIO(key="residential_exposure_score",  value=round(re, 4),  label="주거지 노출도 점수"),
            TraceIO(key="wind_toward_asset_score",     value=round(wa, 4),  label="자산방향 풍속 점수"),
        ],
        outputs=[
            TraceIO(key="FireRiskLevel",       value=round(fl, 4), label=_level5(fl)),
            TraceIO(key="ResidentialExposure", value=round(re, 4), label=_level5(re)),
            TraceIO(key="WindTowardAsset",     value=round(wa, 4), label=_level5(wa)),
        ],
        typeql_snippet=_SNIPPET_FEATURES,
        formula_note="Raw 속성 점수 → feature-record 엔티티로 변환",
    )

    # ── Step 2: Signal 집계 ──
    step2 = TraceStep(
        step=2, name="calc_signals", label="② Signal 집계",
        inputs=[
            TraceIO(key="FireRiskLevel",       value=round(fl, 4),  label="공식지수 입력"),
            TraceIO(key="ResidentialExposure", value=round(re, 4),  label="노출지수 입력"),
            TraceIO(key="WindTowardAsset",     value=round(wa, 4),  label="확산지수 입력"),
        ],
        outputs=[
            TraceIO(key="S_official", value=round(s_off,    4), weight="×0.20",
                    label=f"{round(0.20*s_off,4):.4f} 기여"),
            TraceIO(key="S_exposure", value=round(re,       4), weight="×0.25",
                    label=f"{round(0.25*re,4):.4f} 기여"),
            TraceIO(key="S_spread",   value=round(s_spread, 4), weight="×0.20",
                    label=f"{round(0.20*s_spread,4):.4f} 기여"),
            TraceIO(key="S_action",   value=round(s_action, 4), weight="×0.20",
                    label=f"{round(0.20*s_action,4):.4f} 기여"),
            TraceIO(key="S_time",     value=round(s_time,   4), weight="×0.15",
                    label=f"{round(0.15*s_time,4):.4f} 기여"),
            TraceIO(key="S_priority", value=sp, label="최종 우선순위 점수"),
        ],
        typeql_snippet=_SNIPPET_SIGNALS,
        formula_note="S_priority = 0.20·S_official + 0.25·S_exposure + 0.20·S_spread + 0.20·S_action + 0.15·S_time",
    )

    # ── Step 3: 최종 결정 ──
    step3 = TraceStep(
        step=3, name="decide", label="③ 최종 결정",
        inputs=[
            TraceIO(key="S_priority",  value=sp,      label="우선순위 점수"),
            TraceIO(key="risk_grade",  value=grade,   label="산림청 위험등급"),
            TraceIO(key="hazard_flag", value=hf,      label="위험 차단 여부"),
        ],
        outputs=[
            TraceIO(key="base_state",  value=base,     label="기본 State Band"),
            TraceIO(key="override",    value=override, label="적용 Override"),
            TraceIO(key="final_state", value=state,    label="최종 State Band"),
        ],
        typeql_snippet=_SNIPPET_DECIDE,
        formula_note="Override 8(GradeSevere): 매우높음 + sp<0.60 → PriorityPreWatering 격상",
    )

    return InferenceTraceResponse(
        segment_id=segment_id,
        segment_name=nm,
        steps=[step1, step2, step3],
    )


# ══════════════════════════════════════════════════════════
# B-3: 가중치 시뮬레이터
# POST /api/inference/run-with-thresholds
# TypeDB 재쓰기 없음 — signal 점수 읽어 Python에서 재계산
# ══════════════════════════════════════════════════════════

_DEFAULT_WEIGHTS = {
    "S_official": 0.20, "S_exposure": 0.25, "S_spread": 0.20,
    "S_action": 0.20,   "S_time": 0.15,
}


def run_with_weights(weights: dict) -> list[SegmentThresholdResult]:
    """
    사용자 정의 가중치로 S_priority 재계산 후 Before/After 비교 반환.
    TypeDB에서 signal 점수만 읽고, 기존 decision-state는 건드리지 않음.
    """
    query = """
    match
      $seg isa pre-watering-segment,
        has segment-id $id,
        has segment-name $nm,
        has hazard-flag $hf,
        has risk-grade $rg,
        has risk-index $ri,
        has s-official-score $s_off,
        has residential-exposure-score $re,
        has s-spread-mock $s_spread,
        has s-action-mock $s_action,
        has s-time-mock $s_time;
    select $id, $nm, $hf, $rg, $ri, $s_off, $re, $s_spread, $s_action, $s_time;
    """
    rows = []
    with get_driver() as driver:
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            for row in tx.query(query).resolve():
                rows.append({
                    "id":       str(get_value(row.get("id"))),
                    "name":     str(get_value(row.get("nm"))),
                    "hf":       bool(get_value(row.get("hf"))),
                    "grade":    str(get_value(row.get("rg"))),
                    "idx":      float(get_value(row.get("ri")) or 0),
                    "s_off":    float(get_value(row.get("s_off")) or 0),
                    "re":       float(get_value(row.get("re")) or 0),
                    "s_spread": float(get_value(row.get("s_spread")) or 0),
                    "s_action": float(get_value(row.get("s_action")) or 0),
                    "s_time":   float(get_value(row.get("s_time")) or 0),
                })

    def _sp(seg: dict, w: dict) -> float:
        return round(
            w["S_official"] * seg["s_off"]
            + w["S_exposure"] * seg["re"]
            + w["S_spread"]   * seg["s_spread"]
            + w["S_action"]   * seg["s_action"]
            + w["S_time"]     * seg["s_time"],
            4,
        )

    results = []
    for seg in rows:
        before = _sp(seg, _DEFAULT_WEIGHTS)
        after  = _sp(seg, weights)
        ctx = OverrideContext(
            work_safety_notactionable=seg["hf"],
            risk_grade=seg["grade"],
            risk_index=seg["idx"],
            s_exposure=seg["re"],
        )
        b_state, _ = apply_overrides(before, ctx)
        a_state, _ = apply_overrides(after,  ctx)
        results.append(SegmentThresholdResult(
            segment_id=seg["id"],
            segment_name=seg["name"],
            before_sp=before,
            after_sp=after,
            delta=round(after - before, 4),
            before_state=b_state,
            after_state=a_state,
            state_changed=(b_state != a_state),
        ))

    return sorted(results, key=lambda x: x.after_sp, reverse=True)
