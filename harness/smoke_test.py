"""
smoke_test.py — 전체 파이프라인 E2E 검증

실행: python3 harness/smoke_test.py
전제: TypeDB localhost:1729 기동 중 + FastAPI localhost:8001 기동 중

체크 항목:
  1. TypeDB 서버 연결 + onto-fire-dol DB 존재 + 3 segment
  2. FastAPI health 200 OK
  3. 5개 엔드포인트 200 OK
  4. 프론트엔드 정적 파일 응답
  5. 비즈니스 로직 — SEG-JN-C GradeSevere override 검증
"""

import sys
import requests
from typedb.driver import TypeDB, TransactionType, Credentials, DriverOptions

API = "http://localhost:8001"
DB  = "onto-fire-dol"
PASS = "✅"
FAIL = "❌"


def check(label, cond, detail=""):
    icon = PASS if cond else FAIL
    print(f"  {icon}  {label}")
    if detail:
        print(f"       {detail}")
    return cond


def main():
    print("\n" + "=" * 60)
    print("  E2E SMOKE TEST")
    print("=" * 60 + "\n")

    failures = 0

    # ── 1. TypeDB ──────────────────────────────────────────
    print("【 1. TypeDB 】")
    try:
        creds  = Credentials("admin", "password")
        opts   = DriverOptions(is_tls_enabled=False)
        driver = TypeDB.driver("localhost:1729", credentials=creds, driver_options=opts)
        check("TypeDB 연결 성공", True)

        dbs = [db.name for db in driver.databases.all()]
        if not check(f"DB '{DB}' 존재", DB in dbs, f"발견된 DB: {dbs}"):
            failures += 1
            driver.close()
            return failures

        with driver.transaction(DB, TransactionType.READ) as tx:
            result = tx.query(
                "match $s isa pre-watering-segment; select $s;"
            ).resolve()
            count = len(list(result))
            if not check("segment 3개 로드됨", count == 3, f"실제: {count}"):
                failures += 1

        driver.close()
    except Exception as e:
        check("TypeDB 검증", False, str(e))
        failures += 1
        return failures

    # ── 2. FastAPI ─────────────────────────────────────────
    print("\n【 2. FastAPI 】")
    try:
        r = requests.get(f"{API}/api/health", timeout=3)
        if not check("Health check 200 OK", r.status_code == 200, f"status={r.status_code}"):
            failures += 1
            return failures
        body = r.json()
        if not check("status=ok", body.get("status") == "ok"):
            failures += 1
        if not check("typedb=connected", body.get("typedb") == "connected"):
            failures += 1
    except Exception as e:
        check("FastAPI 연결", False, str(e))
        failures += 1
        return failures

    # ── 3. Endpoints ───────────────────────────────────────
    print("\n【 3. Endpoints 】")
    endpoints = [
        ("GET",  "/api/segments"),
        ("GET",  "/api/segments/SEG-GJ-A"),
        ("GET",  "/api/segments/SEG-GJ-B"),
        ("GET",  "/api/segments/SEG-JN-C"),
        ("GET",  "/api/segments/SEG-JN-C/lineage"),
        ("POST", "/api/inference/run"),
    ]
    for method, path in endpoints:
        try:
            r = requests.request(method, f"{API}{path}", timeout=30)
            ok = r.status_code == 200
            if not check(f"{method} {path}", ok, f"status={r.status_code}"):
                failures += 1
        except Exception as e:
            check(f"{method} {path}", False, str(e))
            failures += 1

    # ── 4. Frontend 정적 ────────────────────────────────────
    print("\n【 4. Frontend 】")
    try:
        r = requests.get(f"{API}/", timeout=3)
        if not check("index.html 응답", r.status_code == 200, f"status={r.status_code}"):
            failures += 1
        if not check("HTML 본문 포함", "<html" in r.text.lower()):
            failures += 1
    except Exception as e:
        check("Frontend", False, str(e))
        failures += 1

    # ── 5. 비즈니스 로직 ────────────────────────────────────
    print("\n【 5. 비즈니스 로직 】")
    try:
        # SEG-JN-C: GradeSevere override → PriorityPreWatering 격상
        r = requests.get(f"{API}/api/segments/SEG-JN-C")
        seg_c = r.json()
        check(
            "SEG-JN-C state_band = PriorityPreWatering (GradeSevere 격상)",
            seg_c.get("state_band") == "PriorityPreWatering",
            f"실제: {seg_c.get('state_band')}",
        )
        check(
            "SEG-JN-C override_applied = GradeSevere",
            seg_c.get("override_applied") == "GradeSevere",
            f"실제: {seg_c.get('override_applied')}",
        )
        sp_c = seg_c.get("s_priority", 0)
        check(
            f"SEG-JN-C S_priority 0.40~0.60 (sp={sp_c:.3f}, 기본 ReviewPreWatering 구간)",
            0.40 <= sp_c <= 0.60,
            f"실제: {sp_c:.4f}",
        )

        # SEG-GJ-A: 저위험 → EnhancedMonitoring
        r = requests.get(f"{API}/api/segments/SEG-GJ-A")
        seg_a = r.json()
        check(
            "SEG-GJ-A state_band = EnhancedMonitoring",
            seg_a.get("state_band") == "EnhancedMonitoring",
            f"실제: {seg_a.get('state_band')}",
        )

        # Lineage — override 값이 GradeSevere로 기록되어 있어야 함
        r = requests.get(f"{API}/api/segments/SEG-JN-C/lineage")
        items = r.json()
        if isinstance(items, list) and items:
            ov = items[0].get("override_applied", "")
            check(
                "Lineage override_applied = GradeSevere",
                ov == "GradeSevere",
                f"실제: {ov}",
            )
        else:
            check("Lineage 항목 존재", False, f"반환: {items}")
            failures += 1

    except Exception as e:
        check("비즈니스 로직", False, str(e))
        failures += 1

    # ── 결과 ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if failures == 0:
        print("  🎉 ALL PASSED — 발표 데모 준비 완료!")
    else:
        print(f"  ⚠️  {failures}개 실패 — 발표 전 반드시 해결")
    print("=" * 60 + "\n")

    return failures


if __name__ == "__main__":
    sys.exit(main())
