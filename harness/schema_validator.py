"""
schema_validator.py — DOL 스키마 정합성 검증

실행: python3 harness/schema_validator.py
전제: TypeDB localhost:1729 기동 중 + load_dol.py 실행 완료

체크 항목:
  1. onto-fire-dol DB 존재
  2. 4개 엔티티 타입 정의됨
  3. 3개 관계 타입 정의됨
  4. 3 segment 데이터 존재 (ID 확인)
  5. decision-state 3개 존재
  6. 각 segment의 S_priority 값이 명세 범위에 들어옴
"""

import sys
from typedb.driver import TypeDB, TransactionType, Credentials, DriverOptions

DB = "onto-fire-dol"

EXPECTED_SEGMENT_IDS = {
    "SEG-GJ-A": {"state": "EnhancedMonitoring",   "sp_min": 0.20, "sp_max": 0.40},
    "SEG-GJ-B": {"state": "ReviewPreWatering",     "sp_min": 0.40, "sp_max": 0.60},
    "SEG-JN-C": {"state": "PriorityPreWatering",   "sp_min": 0.40, "sp_max": 0.60},
}

PASS = "✅"
FAIL = "❌"


def check(label, cond, detail=""):
    print(f"  {PASS if cond else FAIL}  {label}")
    if detail:
        print(f"       {detail}")
    return cond


def try_query(tx, q):
    """쿼리 실행 후 결과 리스트 반환. 오류 시 None."""
    try:
        return list(tx.query(q).resolve())
    except Exception as e:
        return None


def main():
    print("\n" + "=" * 60)
    print("  SCHEMA VALIDATOR")
    print("=" * 60 + "\n")

    failures = 0
    creds = Credentials("admin", "password")
    opts  = DriverOptions(is_tls_enabled=False)

    try:
        driver = TypeDB.driver("localhost:1729", credentials=creds, driver_options=opts)
    except Exception as e:
        print(f"{FAIL} TypeDB 연결 실패: {e}")
        return 1

    # ── DB 존재 ────────────────────────────────────────────
    dbs = [db.name for db in driver.databases.all()]
    if not check(f"DB '{DB}' 존재", DB in dbs, f"발견된 DB: {dbs}"):
        driver.close()
        return 1

    # ── 1. 엔티티 타입 정의 확인 ───────────────────────────
    # TypeDB 3.x: 타입이 존재하면 쿼리가 빈 결과를 반환, 없으면 예외 발생
    print("\n【 Entity 타입 정의 】")
    entity_types = [
        "pre-watering-segment",
        "feature-record",
        "signal-record",
        "decision-state",
    ]
    with driver.transaction(DB, TransactionType.READ) as tx:
        for et in entity_types:
            rows = try_query(tx, f"match $x isa {et}; select $x; limit 1;")
            defined = rows is not None
            if not check(f"entity '{et}'", defined):
                failures += 1

    # ── 2. 관계 타입 정의 확인 ─────────────────────────────
    print("\n【 Relation 타입 정의 】")
    relation_types = [
        "segment-feature",
        "segment-signal",
        "segment-decision",
    ]
    with driver.transaction(DB, TransactionType.READ) as tx:
        for rt in relation_types:
            rows = try_query(tx, f"match $r isa {rt}; select $r; limit 1;")
            defined = rows is not None
            if not check(f"relation '{rt}'", defined):
                failures += 1

    # ── 3. Segment 데이터 ──────────────────────────────────
    print("\n【 Segment 데이터 (3개) 】")
    with driver.transaction(DB, TransactionType.READ) as tx:
        rows = try_query(
            tx,
            "match $s isa pre-watering-segment, "
            "has segment-id $id, has segment-name $nm; "
            "select $id, $nm;"
        )
        if rows is None:
            check("segment 쿼리 실행", False)
            failures += 1
        else:
            if not check("segment 3개 존재", len(rows) == 3, f"실제: {len(rows)}"):
                failures += 1
            found_ids = set()
            for row in rows:
                try:
                    sid  = row.get("id").get_value()
                    snm  = row.get("nm").get_value()
                    found_ids.add(sid)
                    print(f"       · {sid}: {snm}")
                except Exception:
                    pass
            for expected_id in EXPECTED_SEGMENT_IDS:
                if not check(f"'{expected_id}' 존재", expected_id in found_ids):
                    failures += 1

    # ── 4. Decision state (추론 결과) ──────────────────────
    print("\n【 Decision State (추론 결과) 】")
    with driver.transaction(DB, TransactionType.READ) as tx:
        rows = try_query(
            tx,
            "match $s isa pre-watering-segment, has segment-id $id; "
            "$r-dec isa segment-decision, links (subject: $s, outcome: $ds); "
            "$ds has state-band $state, has s-priority $sp, has override-applied $ov; "
            "select $id, $state, $sp, $ov;"
        )
        if rows is None:
            check("decision-state 쿼리 실행", False, "추론 미실행일 수 있음")
            failures += 1
        else:
            if not check("decision 3개 존재", len(rows) == 3, f"실제: {len(rows)}"):
                failures += 1
            for row in rows:
                try:
                    sid   = row.get("id").get_value()
                    state = row.get("state").get_value()
                    sp    = float(row.get("sp").get_value())
                    ov    = row.get("ov").get_value()
                    spec  = EXPECTED_SEGMENT_IDS.get(sid)
                    if spec:
                        state_ok = (state == spec["state"])
                        sp_ok    = (spec["sp_min"] <= sp <= spec["sp_max"])
                        ov_tag   = f" [{ov}]" if ov != "none" else ""
                        check(
                            f"{sid}: state={state}{ov_tag} sp={sp:.3f}",
                            state_ok and sp_ok,
                            f"기대: state={spec['state']} sp∈[{spec['sp_min']},{spec['sp_max']}]",
                        )
                        if not (state_ok and sp_ok):
                            failures += 1
                except Exception as e:
                    check(f"결과 파싱", False, str(e))
                    failures += 1

    driver.close()

    # ── 결과 ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if failures == 0:
        print("  ✅ Schema OK — 발표 데모 준비 완료")
    else:
        print(f"  ⚠️  {failures}개 실패 — 수정 후 재실행")
    print("=" * 60 + "\n")

    return failures


if __name__ == "__main__":
    sys.exit(main())
