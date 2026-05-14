#!/usr/bin/env python3
"""
load_dol.py
광주·전남 예비주수 DOL 온톨로지 일괄 로드 스크립트

발표 데모 파이프라인:
  예측DB 출력(RF mock) → DOL 추론 엔진(TypeDB) → LLM 자연어 변환

실행 방법:
  cd ~/dev/dol-ontology
  python3 02_dol_schema/load_dol.py

사전 요건: typedb server 실행 중 (localhost:1729)
"""

import os
import sys
from pathlib import Path

# 03_backend 패키지 경로 추가 (signals.py 공유)
sys.path.insert(0, str(Path(__file__).parent.parent / "03_backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from typedb.driver import TypeDB, TransactionType, Credentials, DriverOptions
from app.services.reasoning.signals import apply_overrides, OverrideContext

# ─── 접속 정보 (.env 또는 기본값) ───
ADDRESS  = os.getenv("TYPEDB_ADDRESS", "localhost:1729")
DB_NAME  = os.getenv("TYPEDB_DB", "onto-fire-dol")
USER     = os.getenv("TYPEDB_USER", "admin")
PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

BASE = Path(__file__).parent

# ─── 파일 경로 ───
SCHEMA_FILES = [
    BASE / "schema/01_entities.tql",
    BASE / "schema/02_features.tql",
    BASE / "schema/03_signals.tql",
    BASE / "schema/04_overrides.tql",
]

# ─── TypeDB 연결 ───
creds = Credentials(USER, PASSWORD)
opts  = DriverOptions(is_tls_enabled=False)


# ══════════════════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════════════════

def read_tql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_queries(tql: str) -> list[str]:
    """TQL 파일 내 여러 match-insert 블록을 개별 쿼리로 분리."""
    # 빈 줄 2개 이상으로 구분된 블록을 나눔
    import re
    blocks = re.split(r'\n{2,}', tql.strip())
    queries = []
    for block in blocks:
        block = block.strip()
        # 주석만 있는 블록 건너뜀
        lines = [l for l in block.splitlines() if not l.strip().startswith("#")]
        content = "\n".join(lines).strip()
        if content:
            queries.append(block)
    return queries


def run_schema(driver, tql: str, label: str):
    """schema 트랜잭션으로 TQL 실행."""
    with driver.transaction(DB_NAME, TransactionType.SCHEMA) as tx:
        tx.query(tql).resolve()
        tx.commit()
    print(f"  ✓ 스키마 적재: {label}")


def run_write(driver, tql: str, label: str = ""):
    """write 트랜잭션으로 TQL 실행."""
    with driver.transaction(DB_NAME, TransactionType.WRITE) as tx:
        tx.query(tql).resolve()
        tx.commit()
    if label:
        print(f"  ✓ 데이터 적재: {label}")


def run_write_queries(driver, queries: list[str], label: str):
    """여러 match-insert 쿼리를 각각 별도 write 트랜잭션으로 실행."""
    for i, q in enumerate(queries, 1):
        # 실질 내용 없는 블록 건너뜀
        stripped = "\n".join(
            l for l in q.splitlines() if not l.strip().startswith("#")
        ).strip()
        if not stripped:
            continue
        with driver.transaction(DB_NAME, TransactionType.WRITE) as tx:
            tx.query(stripped).resolve()
            tx.commit()
    print(f"  ✓ 완료: {label}")


def get_value(concept) -> float | str | bool | None:
    """ConceptRow에서 Python 기본값 추출 (TypeDB 3.x 드라이버 호환)."""
    if concept is None:
        return None
    # TypeDB 3.x: Value 객체는 .as_<type>() 또는 직접 float/str/bool
    try:
        return concept.as_double()
    except Exception:
        pass
    try:
        return concept.as_string()
    except Exception:
        pass
    try:
        return concept.as_boolean()
    except Exception:
        pass
    try:
        return concept.get_value()
    except Exception:
        pass
    return str(concept)


# ══════════════════════════════════════════════════════════
# 메인 파이프라인
# ══════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  DOL 추론 엔진 — 데이터 로드 시작")
    print("  DB:", DB_NAME, "| 주소:", ADDRESS)
    print("=" * 55)

    with TypeDB.driver(ADDRESS, credentials=creds, driver_options=opts) as driver:

        # ── STEP 1: DB 드롭·재생성 ──────────────────────────
        print("\n[STEP 1] DB 재생성")
        if driver.databases.contains(DB_NAME):
            driver.databases.get(DB_NAME).delete()
            print(f"  ✓ 기존 '{DB_NAME}' 삭제")
        driver.databases.create(DB_NAME)
        print(f"  ✓ '{DB_NAME}' 생성 완료")

        # ── STEP 2: 스키마 적재 ─────────────────────────────
        print("\n[STEP 2] 스키마 적재 (4개 파일)")
        for f in SCHEMA_FILES:
            run_schema(driver, read_tql(f), f.name)

        # ── STEP 3: 기본 데이터 적재 ────────────────────────
        print("\n[STEP 3] 데이터 적재")
        # sources.tql: 단일 insert 블록
        run_write(driver, read_tql(BASE / "data/sources.tql"), "sources.tql (segment 3개)")
        # prediction.tql: 3개 match-insert 블록을 분리 실행
        pred_queries = split_queries(read_tql(BASE / "data/prediction.tql"))
        run_write_queries(driver, pred_queries, "prediction.tql (Feature/Signal 점수 3개)")

        # ── STEP 4+5+6: 전체 추론 (Python 주도) ─────────────
        # TypeDB 3.x 타입 시스템: 속성 타입 간 변수 직접 재사용 불가
        # → Python이 속성값 읽기 + feature/signal/state INSERT 수행
        print("\n[STEP 4-6] 추론 파이프라인 (Python + TypeDB INSERT)")

        # 모든 segment 속성 읽기
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
                    "id":      get_value(row.get("id")),
                    "name":    get_value(row.get("nm")),
                    "hf":      get_value(row.get("hf")),
                    "grade":   get_value(row.get("rg")),
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
                raw["sp"] = (0.20 * raw["s_off"] + 0.25 * raw["re"]
                             + 0.20 * raw["s_spread"] + 0.20 * raw["s_action"]
                             + 0.15 * raw["s_time"])
                segments.append(raw)

        print(f"  ✓ {len(segments)}개 segment 읽기 완료")

        # STEP 4: feature-record INSERT (i01 로직)
        print("  [4] feature-record INSERT")
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
        print(f"  ✓ feature-record {len(segments)*3}개 완료")

        # STEP 5: signal-record INSERT (i02 로직)
        print("  [5] signal-record INSERT")
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
        print(f"  ✓ signal-record {len(segments)*2}개 완료")

        # Override 적용 후 decision-state INSERT (9 Override 전체 적용)
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

            ov_tag = f" [{ov}]" if ov != "none" else ""
            print(f"  ✓ {seg['id']} ({seg['name'][:12]}…) "
                  f"sp={sp:.3f} → {state}{ov_tag}")

        # ── STEP 7: Decision Lineage 검증 ──────────────────
        print("\n[STEP 7] Decision Lineage 검증 출력")
        print("-" * 55)

        lineage_q = read_tql(BASE / "inference/v01_decision_lineage.tql")
        with driver.transaction(DB_NAME, TransactionType.READ) as tx:
            rows = tx.query(lineage_q).resolve()
            # 구간별로 그룹핑해서 출력
            seen = set()
            for row in rows:
                seg_id   = get_value(row.get("seg-id"))
                state    = get_value(row.get("state"))
                override = get_value(row.get("override"))
                sp       = get_value(row.get("sp"))
                f_kind   = get_value(row.get("f-kind"))
                f_score  = get_value(row.get("f-score"))
                sig_kind = get_value(row.get("sig-kind"))
                sig_score= get_value(row.get("sig-score"))

                key = (seg_id, f_kind, sig_kind)
                if key in seen:
                    continue
                seen.add(key)

                ov_tag = f" [{override}]" if override != "none" else ""
                print(f"  {seg_id} | {state}{ov_tag} | sp={float(sp):.3f}")
                print(f"    Feature: {f_kind:<25} score={float(f_score):.3f}")
                print(f"    Signal:  {sig_kind:<25} score={float(sig_score):.3f}")

        print("-" * 55)
        print("\n✅ 모든 단계 완료!")
        print(f"   DB: {DB_NAME}")
        print("   발표 시연 준비 완료 — FastAPI 서버를 시작하세요:")
        print("   $ cd 03_backend && ./run.sh")
        print("=" * 55)


if __name__ == "__main__":
    main()
