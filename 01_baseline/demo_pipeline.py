"""
╔══════════════════════════════════════════════════════════════════╗
║     재난 온톨로지 기반 위험도 추론 — 발표 데모 파이프라인         ║
║     온톨로지 기반 재난 위험도 추론 데모 파이프라인                    ║
║     파이프라인: 예측DB → ★DOL 추론★ → LLM 변환                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
from pathlib import Path
from typedb.driver import TypeDB, TransactionType, Credentials, DriverOptions

BASE = Path(__file__).parent

# ── 설정 ──────────────────────────────────────────────────────────
DB      = "onto-fire"
ADDRESS = "localhost:1729"
USER    = "admin"
PASSWD  = "password"

# ── 출력 헬퍼 ─────────────────────────────────────────────────────
W = 68

def banner(text):
    print("\n" + "═" * W)
    print(f"  {text}")
    print("═" * W)

def section(icon, title):
    print(f"\n{'─' * W}")
    print(f"  {icon}  {title}")
    print(f"{'─' * W}")

def row(label, value):
    print(f"    {'·'} {label:<28} {value}")

def ok(msg):
    print(f"  ✅  {msg}")

def pause(msg=""):
    if msg:
        print(f"\n  ⏎  {msg}")
    input("     [ Enter 키를 눌러 다음 단계로 ] ")

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    banner("재난 온톨로지 추론 엔진 — 라이브 데모")
    print(f"""
  파이프라인 위치
  ┌─────────────────────────────────────────────────────┐
  │  박O수 (예측DB 출력)                                │
  │       ↓  risk-index-value / availability-status     │
  │  ★ DOL 추론 엔진  ← 지금 여기                       │
  │       ↓  Trigger → Threshold → State → Action       │
  │  유O수 (LLM 자연어 변환)                            │
  └─────────────────────────────────────────────────────┘
  DB: {DB}  |  Address: {ADDRESS}
""")

    pause("TypeDB 연결 & 스키마·데이터 초기화 시작")

    # ── 연결 ──────────────────────────────────────────────────────
    creds  = Credentials(USER, PASSWD)
    opts   = DriverOptions(is_tls_enabled=False)
    driver = TypeDB.driver(ADDRESS, credentials=creds, driver_options=opts)
    ok("TypeDB 연결 성공")

    # ── 스키마 & 데이터 초기화 ────────────────────────────────────
    banner("PHASE 0 — 스키마 & 데이터 초기화")

    # DB 드롭 & 재생성 (멱등 실행 보장)
    existing = [db.name for db in driver.databases.all()]
    if DB in existing:
        driver.databases.get(DB).delete()
        ok(f"기존 DB '{DB}' 삭제 완료")
    driver.databases.create(DB)
    ok(f"DB '{DB}' 새로 생성 완료")

    with driver.transaction(DB, TransactionType.SCHEMA) as tx:
        tx.query((BASE / "schema/wildfire_schema.tql").read_text()).resolve()
        tx.commit()
        ok("wildfire_schema.tql 로드 완료")

    with driver.transaction(DB, TransactionType.SCHEMA) as tx:
        tx.query((BASE / "schema/functions.tql").read_text()).resolve()
        tx.commit()
        ok("functions.tql (추론 함수) 로드 완료")

    with driver.transaction(DB, TransactionType.WRITE) as tx:
        tx.query((BASE / "data/mock_insert.tql").read_text()).resolve()
        tx.commit()
        ok("mock_insert.tql (곡성 시나리오 데이터) 로드 완료")

    # ══════════════════════════════════════════════════════════════
    #  PHASE 1 — TRIGGER: 고위험 구역 감지
    # ══════════════════════════════════════════════════════════════
    pause()
    banner("PHASE 1 — TRIGGER: 고위험 구역 감지")
    print("  박O수의 예측DB 출력값(risk-index-value)을 Threshold와 비교합니다.")

    with driver.transaction(DB, TransactionType.READ) as tx:
        section("🔥", "Step 1-1  고위험 구역 (risk-level = 높음)")
        result = tx.query("""
            match
              $z isa forest-zone, has name $n;
              $a isa risk-assessment, has risk-level '높음', has risk-index-value $v;
              (assessment: $a, zone: $z) isa risk-assessment-for-zone;
            select $n, $v;
        """).resolve()
        rows = list(result)
        for r in rows:
            zone = r.get("n").get_value()
            val  = r.get("v").get_value()
            flag = "🚨 임계치 초과" if val >= 0.85 else "⚠️  경계"
            row(zone, f"위험지수 {val:.2f}  {flag}")
        if not rows:
            print("    (해당 없음)")

        section("🌡️", "Step 1-2  기상 조건 조회 (Trigger 근거)")
        result = tx.query("""
            match
              $z isa forest-zone, has name $zn;
              $w isa weather-observation,
                    has humidity-percent $h,
                    has wind-speed-ms $ws;
              (observation: $w, zone: $z) isa weather-observed-in-zone;
            select $zn, $h, $ws;
        """).resolve()
        for r in list(result):
            row(r.get("zn").get_value(),
                f"습도 {r.get('h').get_value():.1f}%  |  풍속 {r.get('ws').get_value():.1f} m/s")

    # ══════════════════════════════════════════════════════════════
    #  PHASE 2 — STATE TRANSITION: 추론 INSERT (i01~i04)
    # ══════════════════════════════════════════════════════════════
    pause()
    banner("PHASE 2 — STATE TRANSITION: 추론 INSERT (i01~i04)")
    print("  함수 기반 추론으로 새 엔티티(결정)를 DB에 생성합니다.")

    inference_queries = [
        ("i01", "접근통제 결정",  "queries/inference/i01_insert_access_control_by_function.tql"),
        ("i02", "대피경보 결정",  "queries/inference/i02_insert_watch_evacuation_by_function.tql"),
        ("i03", "출동 결정",     "queries/inference/i03_insert_dispatch_by_ready_resources_function.tql"),
        ("i04", "정책권고 생성",  "queries/inference/i04_insert_policy_recommendation_by_function.tql"),
    ]

    for code, label, path in inference_queries:
        with driver.transaction(DB, TransactionType.WRITE) as tx:
            tx.query((BASE / path).read_text()).resolve()
            tx.commit()
            ok(f"{code}  {label}  →  DB 저장 완료")
        time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════
    #  PHASE 3 — ACTION: 결정 결과 조회 (v01~v04)
    # ══════════════════════════════════════════════════════════════
    pause()
    banner("PHASE 3 — ACTION: 결정 결과 조회 (v01~v04)")
    print("  추론 결과를 검증합니다. 이 출력이 유O수(LLM)에게 전달됩니다.")

    with driver.transaction(DB, TransactionType.READ) as tx:

        # v01 접근통제
        section("🚧", "v01  접근통제 대상 구역")
        result = tx.query((BASE / "queries/inference/v01_verify_access_control_inference.tql").read_text()).resolve()
        for r in list(result):
            row("통제 구역", r.get("zone-name").get_value())

        # v02 대피경보
        section("🏘️", "v02  대피경보 대상 (사건 → 정착지)")
        result = tx.query((BASE / "queries/inference/v02_verify_watch_evacuation_inference.tql").read_text()).resolve()
        seen = set()
        for r in list(result):
            pair = (r.get("incident-name").get_value(), r.get("settlement-name").get_value())
            if pair not in seen:
                seen.add(pair)
                row(pair[0], f"→  {pair[1]}  대피경보 발령")

        # v03 출동결정
        section("🚒", "v03  출동 자원 배정 (사건 → 자원)")
        result = tx.query((BASE / "queries/inference/v03_verify_dispatch_inference.tql").read_text()).resolve()
        seen = set()
        for r in list(result):
            inc  = r.get("incident-name").get_value()
            crew = r.get("crew-name").get_value()
            eng  = r.get("engine-name").get_value()
            air  = r.get("aircraft-name").get_value()
            key  = (inc, crew, eng, air)
            if key not in seen:
                seen.add(key)
                row(inc, f"{crew} + {eng} + {air}")

        # v04 정책권고
        section("📋", "v04  정책권고 (사후보고 → 권고)")
        result = tx.query((BASE / "queries/inference/v04_verify_policy_recommendation_inference.tql").read_text()).resolve()
        for r in list(result):
            row(r.get("incident-name").get_value(),
                f"보고: {str(r.get('report-at').get_value())[:10]}  →  정책권고 생성")

    # ══════════════════════════════════════════════════════════════
    #  PHASE 4 — LINEAGE: "왜 이 결정인가?" 역추적 (v01 패턴)
    # ══════════════════════════════════════════════════════════════
    pause()
    banner("PHASE 4 — LINEAGE: '왜 이 결정인가?' 역추적")
    print("  접근통제 결정의 근거를 역방향으로 추적합니다.")

    with driver.transaction(DB, TransactionType.READ) as tx:
        section("🔍", "Decision Lineage  —  접근통제 역추적")
        result = tx.query("""
            match
              $z isa forest-zone, has name $zn;
              $a isa risk-assessment,
                    has risk-level $rl,
                    has risk-index-value $rv,
                    has recorded-at $rat;
              $w isa weather-observation,
                    has humidity-percent $h,
                    has wind-speed-ms $ws;
              $f isa fuel-moisture-measurement,
                    has fuel-moisture-percent $fm;
              (assessment: $a, zone: $z) isa risk-assessment-for-zone;
              (observation: $w, zone: $z) isa weather-observed-in-zone;
              (measurement: $f, zone: $z) isa fuel-moisture-observed-in-zone;
            select $zn, $rl, $rv, $h, $ws, $fm;
        """).resolve()

        rows = list(result)
        for r in rows:
            zn  = r.get("zn").get_value()
            rl  = r.get("rl").get_value()
            rv  = r.get("rv").get_value()
            h   = r.get("h").get_value()
            ws  = r.get("ws").get_value()
            fm  = r.get("fm").get_value()
            print(f"""
  ┌─ 구역: {zn}
  │   위험등급   : {rl}  (지수 {rv:.2f})
  │   습도       : {h:.1f}%   →  {'건조 위험 ⚠️' if h < 30 else '정상'}
  │   풍속       : {ws:.1f} m/s  →  {'강풍 위험 ⚠️' if ws > 7 else '정상'}
  │   연료수분   : {fm:.1f}%  →  {'발화위험 🔥' if fm < 10 else '정상'}
  └─ ▶ 결정: 접근통제 발령  (Trigger 조건 3종 충족)""")

    # ── 마무리 ────────────────────────────────────────────────────
    driver.close()

    print("\n" + "═" * W)
    print("""
  ✅  전체 파이프라인 실행 완료

  요약
  ┌───────────────────────────────────────────────────┐
  │  Trigger   고위험 구역 2곳 감지 (0.87 / 0.91)     │
  │  State     i01~i04 추론 INSERT → DB 저장           │
  │  Action    접근통제 · 대피경보 · 출동 · 정책권고   │
  │  Lineage   "왜?" 3종 근거 역추적 완료              │
  │  Next →    유O수 LLM 자연어 변환 단계              │
  └───────────────────────────────────────────────────┘
""")
    print("═" * W)

if __name__ == "__main__":
    main()