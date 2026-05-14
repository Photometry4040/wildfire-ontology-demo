# routes/baseline.py
# 역할: 01_baseline demo_pipeline.py TypeQL 쿼리를 REST API로 노출
# DB: onto-fire (baseline wildfire DB — DOL DB "onto-fire-dol"과 독립)

from pathlib import Path
from fastapi import APIRouter, HTTPException
from typedb.driver import TypeDB, TransactionType, Credentials, DriverOptions

router = APIRouter()

# ── TypeDB 접속 (baseline 전용 — onto-fire DB) ──
_BASELINE_DB = "onto-fire"
_ADDRESS     = "localhost:1729"
_creds       = Credentials("admin", "password")
_opts        = DriverOptions(is_tls_enabled=False)

BASE = Path(__file__).parent.parent.parent.parent / "01_baseline"


def _driver():
    return TypeDB.driver(_ADDRESS, credentials=_creds, driver_options=_opts)


def _gv(concept):
    """ConceptRow 값 추출 헬퍼."""
    if concept is None:
        return None
    for method in ("as_double", "as_string", "as_boolean", "get_value"):
        try:
            return getattr(concept, method)()
        except Exception:
            pass
    return str(concept)


# ── POST /api/baseline/init — Phase 0: DB 재생성 + 스키마·데이터 로드 ──
@router.post("/baseline/init")
def baseline_init():
    try:
        with _driver() as driver:
            if driver.databases.contains(_BASELINE_DB):
                driver.databases.get(_BASELINE_DB).delete()
            driver.databases.create(_BASELINE_DB)

            with driver.transaction(_BASELINE_DB, TransactionType.SCHEMA) as tx:
                tx.query((BASE / "schema/wildfire_schema.tql").read_text()).resolve()
                tx.commit()

            with driver.transaction(_BASELINE_DB, TransactionType.SCHEMA) as tx:
                tx.query((BASE / "schema/functions.tql").read_text()).resolve()
                tx.commit()

            with driver.transaction(_BASELINE_DB, TransactionType.WRITE) as tx:
                tx.query((BASE / "data/mock_insert.tql").read_text()).resolve()
                tx.commit()

        return {"status": "ok", "db": _BASELINE_DB, "message": "스키마·데이터 로드 완료"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"초기화 실패: {e}")


# ── GET /api/baseline/trigger — Phase 1: 고위험 구역 + 기상 조건 ──
@router.get("/baseline/trigger")
def baseline_trigger():
    try:
        zones, weather = [], []
        with _driver() as driver:
            with driver.transaction(_BASELINE_DB, TransactionType.READ) as tx:
                # 고위험 구역 (risk-level = 높음)
                rows = list(tx.query("""
                    match
                      $z isa forest-zone, has name $n;
                      $a isa risk-assessment, has risk-level $rl, has risk-index-value $v;
                      (assessment: $a, zone: $z) isa risk-assessment-for-zone;
                    select $n, $rl, $v;
                """).resolve())
                for r in rows:
                    v = float(_gv(r.get("v")) or 0)
                    zones.append({
                        "zone":     _gv(r.get("n")),
                        "risk_level": _gv(r.get("rl")),
                        "risk_index": round(v, 2),
                        "critical": v >= 0.85,
                    })

                # 기상 조건
                rows = list(tx.query("""
                    match
                      $z isa forest-zone, has name $zn;
                      $w isa weather-observation,
                            has humidity-percent $h,
                            has wind-speed-ms $ws;
                      (observation: $w, zone: $z) isa weather-observed-in-zone;
                    select $zn, $h, $ws;
                """).resolve())
                for r in rows:
                    h  = float(_gv(r.get("h"))  or 0)
                    ws = float(_gv(r.get("ws")) or 0)
                    weather.append({
                        "zone":       _gv(r.get("zn")),
                        "humidity":   round(h, 1),
                        "wind_speed": round(ws, 1),
                        "dry":        h < 30,
                        "strong_wind": ws > 7,
                        "status": ("건조+강풍" if h < 30 and ws > 7
                                   else "건조" if h < 30
                                   else "강풍" if ws > 7
                                   else "정상"),
                    })

        return {"high_risk_zones": zones, "weather": weather}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Trigger 조회 실패: {e}")


# ── POST /api/baseline/infer — Phase 2: i01~i04 추론 INSERT ──
@router.post("/baseline/infer")
def baseline_infer():
    queries = [
        ("i01", "접근통제 결정", "queries/inference/i01_insert_access_control_by_function.tql"),
        ("i02", "대피경보 결정", "queries/inference/i02_insert_watch_evacuation_by_function.tql"),
        ("i03", "출동 결정",    "queries/inference/i03_insert_dispatch_by_ready_resources_function.tql"),
        ("i04", "정책권고 생성","queries/inference/i04_insert_policy_recommendation_by_function.tql"),
    ]
    results = {}
    try:
        with _driver() as driver:
            for code, label, path in queries:
                with driver.transaction(_BASELINE_DB, TransactionType.WRITE) as tx:
                    tx.query((BASE / path).read_text()).resolve()
                    tx.commit()
                results[code] = {"label": label, "done": True}
        return {"status": "ok", "steps": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"추론 INSERT 실패: {e}")


# ── GET /api/baseline/actions — Phase 3: v01~v04 결정 결과 조회 ──
@router.get("/baseline/actions")
def baseline_actions():
    try:
        access_control, evacuation, dispatch, policy = [], [], [], []
        with _driver() as driver:
            with driver.transaction(_BASELINE_DB, TransactionType.READ) as tx:

                # v01 접근통제
                for r in tx.query((BASE / "queries/inference/v01_verify_access_control_inference.tql").read_text()).resolve():
                    access_control.append({"zone": _gv(r.get("zone-name"))})

                # v02 대피경보
                seen = set()
                for r in tx.query((BASE / "queries/inference/v02_verify_watch_evacuation_inference.tql").read_text()).resolve():
                    inc  = _gv(r.get("incident-name"))
                    stl  = _gv(r.get("settlement-name"))
                    if (inc, stl) not in seen:
                        seen.add((inc, stl))
                        evacuation.append({"incident": inc, "settlement": stl})

                # v03 출동결정
                seen = set()
                for r in tx.query((BASE / "queries/inference/v03_verify_dispatch_inference.tql").read_text()).resolve():
                    key = (_gv(r.get("incident-name")), _gv(r.get("crew-name")))
                    if key not in seen:
                        seen.add(key)
                        dispatch.append({
                            "incident": _gv(r.get("incident-name")),
                            "crew":     _gv(r.get("crew-name")),
                            "engine":   _gv(r.get("engine-name")),
                            "aircraft": _gv(r.get("aircraft-name")),
                        })

                # v04 정책권고
                for r in tx.query((BASE / "queries/inference/v04_verify_policy_recommendation_inference.tql").read_text()).resolve():
                    policy.append({
                        "incident":   _gv(r.get("incident-name")),
                        "report_at":  str(_gv(r.get("report-at")))[:10],
                    })

        return {
            "access_control": access_control,
            "evacuation":     evacuation,
            "dispatch":       dispatch,
            "policy":         policy,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Action 조회 실패: {e}")


# ── GET /api/baseline/lineage — Phase 4: 접근통제 결정 근거 역추적 ──
@router.get("/baseline/lineage")
def baseline_lineage():
    try:
        results = []
        with _driver() as driver:
            with driver.transaction(_BASELINE_DB, TransactionType.READ) as tx:
                rows = list(tx.query("""
                    match
                      $z isa forest-zone, has name $zn;
                      $a isa risk-assessment,
                            has risk-level $rl,
                            has risk-index-value $rv;
                      $w isa weather-observation,
                            has humidity-percent $h,
                            has wind-speed-ms $ws;
                      $f isa fuel-moisture-measurement,
                            has fuel-moisture-percent $fm;
                      (assessment: $a, zone: $z) isa risk-assessment-for-zone;
                      (observation: $w, zone: $z) isa weather-observed-in-zone;
                      (measurement: $f, zone: $z) isa fuel-moisture-observed-in-zone;
                    select $zn, $rl, $rv, $h, $ws, $fm;
                """).resolve())
                for r in rows:
                    h  = float(_gv(r.get("h"))  or 0)
                    ws = float(_gv(r.get("ws")) or 0)
                    fm = float(_gv(r.get("fm")) or 0)
                    rv = float(_gv(r.get("rv")) or 0)
                    results.append({
                        "zone":        _gv(r.get("zn")),
                        "risk_level":  _gv(r.get("rl")),
                        "risk_index":  round(rv, 2),
                        "humidity":    round(h, 1),
                        "wind_speed":  round(ws, 1),
                        "fuel_moisture": round(fm, 1),
                        "triggers": {
                            "dry":         h < 30,
                            "strong_wind": ws > 7,
                            "low_fuel_moisture": fm < 10,
                        },
                        "decision": "접근통제 발령" if rv >= 0.85 else "모니터링",
                    })

        return {"lineage": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Lineage 조회 실패: {e}")


# ── POST /api/baseline/pipeline — 원클릭 Phase 0~4 전체 실행 ──
@router.post("/baseline/pipeline")
def baseline_pipeline():
    try:
        baseline_init()
        trigger  = baseline_trigger()
        infer    = baseline_infer()
        actions  = baseline_actions()
        lineage  = baseline_lineage()
        return {
            "status":  "ok",
            "trigger": trigger,
            "infer":   infer,
            "actions": actions,
            "lineage": lineage,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"파이프라인 실행 실패: {e}")
