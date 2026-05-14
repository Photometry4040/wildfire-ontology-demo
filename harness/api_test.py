"""
api_test.py — FastAPI 엔드포인트 회귀 테스트

실행: python3 harness/api_test.py
전제: FastAPI 서버 localhost:8001 기동 중 + onto-fire-dol DB 로드 완료
"""

import sys
import requests

API = "http://localhost:8001"
PASS = "✅"
FAIL = "❌"

SEG_IDS = ["SEG-GJ-A", "SEG-GJ-B", "SEG-JN-C"]


def check(label, cond, detail=""):
    print(f"  {PASS if cond else FAIL}  {label}")
    if detail:
        print(f"       {detail}")
    return cond


def main():
    print("\n" + "=" * 60)
    print("  API REGRESSION TEST")
    print("=" * 60 + "\n")

    failures = 0

    # ── 1. Health ──────────────────────────────────────────
    print("【 GET /api/health 】")
    try:
        r = requests.get(f"{API}/api/health", timeout=3)
        if not check("200 OK", r.status_code == 200):
            failures += 1
            return failures
        body = r.json()
        if not check("status=ok", body.get("status") == "ok"):
            failures += 1
        if not check("typedb=connected", body.get("typedb") == "connected"):
            failures += 1
        if not check("db_name 필드 존재", "db_name" in body):
            failures += 1
    except Exception as e:
        check("health endpoint", False, str(e))
        return 1

    # ── 2. 구간 목록 ───────────────────────────────────────
    print("\n【 GET /api/segments 】")
    r = requests.get(f"{API}/api/segments")
    segments = r.json() if r.status_code == 200 else []
    if not check("200 OK", r.status_code == 200):
        failures += 1
    if not check("3 segments 반환", len(segments) == 3, f"실제: {len(segments)}"):
        failures += 1

    if segments:
        first = segments[0]
        for field in ["segment_id", "segment_name", "s_priority", "state_band", "override_applied"]:
            if not check(f"필드 '{field}' 존재", field in first):
                failures += 1

    # ── 3. 구간 상세 ───────────────────────────────────────
    print("\n【 GET /api/segments/{id} 】")
    for seg_id in SEG_IDS:
        r = requests.get(f"{API}/api/segments/{seg_id}")
        ok = r.status_code == 200
        if not check(f"{seg_id} 200 OK", ok, f"status={r.status_code}"):
            failures += 1
            continue
        body = r.json()
        for field in ["segment_id", "segment_name", "state_band", "s_priority",
                      "override_applied", "hazard_flag", "risk_grade", "risk_index",
                      "features", "signals"]:
            if not check(f"  {seg_id}: '{field}' 필드", field in body):
                failures += 1
        if not check(f"  {seg_id}: features 3개", len(body.get("features", [])) == 3,
                     f"실제: {len(body.get('features', []))}"):
            failures += 1
        if not check(f"  {seg_id}: signals 2개", len(body.get("signals", [])) == 2,
                     f"실제: {len(body.get('signals', []))}"):
            failures += 1
        if body.get("signals"):
            sig = body["signals"][0]
            if not check(f"  {seg_id}: signal.kind 필드", "kind" in sig):
                failures += 1
            if not check(f"  {seg_id}: signal.score 필드", "score" in sig):
                failures += 1

    # ── 4. Lineage ──────────────────────────────────────────
    print("\n【 GET /api/segments/SEG-JN-C/lineage 】")
    r = requests.get(f"{API}/api/segments/SEG-JN-C/lineage")
    if not check("200 OK", r.status_code == 200, f"status={r.status_code}"):
        failures += 1
    elif r.status_code == 200:
        items = r.json()
        if not check("리스트 형태", isinstance(items, list)):
            failures += 1
        elif items:
            item = items[0]
            for field in ["segment_id", "segment_name", "state_band", "s_priority",
                          "override_applied", "feature_kind", "feature_score",
                          "signal_kind", "signal_score"]:
                if not check(f"  lineage item '{field}' 필드", field in item):
                    failures += 1

    # ── 5. 404 정상 처리 ────────────────────────────────────
    print("\n【 GET /api/segments/non-existent 】")
    r = requests.get(f"{API}/api/segments/non-existent")
    if not check("404 응답", r.status_code == 404, f"실제: {r.status_code}"):
        failures += 1

    # ── 6. 추론 재실행 ──────────────────────────────────────
    print("\n【 POST /api/inference/run 】")
    r = requests.post(f"{API}/api/inference/run", timeout=30)
    if not check("200 OK", r.status_code == 200, f"status={r.status_code}"):
        failures += 1
    elif r.status_code == 200:
        body = r.json()
        if not check("success=True", body.get("success") is True):
            failures += 1
        if not check("segments_processed=3", body.get("segments_processed") == 3,
                     f"실제: {body.get('segments_processed')}"):
            failures += 1
        if not check("message 필드 존재", "message" in body):
            failures += 1

    # ── 7. CORS ─────────────────────────────────────────────
    print("\n【 CORS 헤더 】")
    r = requests.options(
        f"{API}/api/segments",
        headers={"Origin": "http://localhost:3000"},
    )
    cors_ok = "access-control-allow-origin" in {k.lower() for k in r.headers}
    if not check("Access-Control-Allow-Origin 헤더 존재", cors_ok):
        failures += 1

    # ── 결과 ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if failures == 0:
        print("  ✅ All API checks passed")
    else:
        print(f"  ⚠️  {failures}개 실패")
    print("=" * 60 + "\n")
    return failures


if __name__ == "__main__":
    sys.exit(main())
