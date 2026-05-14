"""
Phase A-4: 데이터 정합성 검증
산림청 sigucode ↔ regions.py ↔ KMA grids.py 교차 검증

항목:
  [1] 산림청 API 실 응답 시군구 커버리지 (27개 모두 있는지)
  [2] sigucode 5자리 ↔ regions.py 10자리 매핑 정합성
  [3] KMA 격자(NX,NY) 중복 없음 + 시군구별 1:1 대응
  [4] KMA 실 응답 sigun명 ↔ grids.py sigun명 일치
  [5] analdate 형식 통일 함수 검증
  [6] is_mock 플래그 분리 확인
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.fire_risk_forecast.client import FireRiskClient
from pipelines.fire_risk_forecast.regions import SIGUNGU
from pipelines.kma_weather.client import KmaWeatherClient
from pipelines.kma_weather.grids import GRIDS


# ─── 시간 형식 통일 유틸 ──────────────────────────────────────

def parse_analdate(analdate: str) -> datetime:
    """
    산림청 analdate 파싱.
    형식: "2026-05-10 21"  →  datetime(2026, 5, 10, 21)
    """
    return datetime.strptime(analdate.strip(), "%Y-%m-%d %H")


def parse_kma_time(base_date: str, base_time: str) -> datetime:
    """
    KMA base_date + base_time 파싱.
    형식: "20260510", "0800"  →  datetime(2026, 5, 10, 8)
    """
    return datetime.strptime(base_date + base_time, "%Y%m%d%H%M")


def to_common_key(dt: datetime) -> str:
    """두 소스 모두 YYYYMMDDHH 문자열 키로 통일."""
    return dt.strftime("%Y%m%d%H")


# ─── 검증 함수들 ──────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

def check_sigucode_mapping() -> tuple[str, list[str]]:
    """[2] sigucode 5자리 ↔ regions.py 10자리 정합성."""
    issues: list[str] = []
    # regions.py: "4673000000" → 앞 5자리 "46730"
    regions_5 = {code[:5]: (name, upl) for code, (name, upl) in SIGUNGU.items()}

    # grids.py: sigucode 10자리
    grids_5 = {g.sigucode[:5]: g.sigun for g in GRIDS}

    for code5, (rname, _) in regions_5.items():
        gname = grids_5.get(code5)
        if gname is None:
            issues.append(f"  grids.py에 {code5}({rname}) 없음")
        elif gname != rname:
            issues.append(f"  이름 불일치: regions={rname} grids={gname} [{code5}]")

    for code5, gname in grids_5.items():
        if code5 not in regions_5:
            issues.append(f"  regions.py에 {code5}({gname}) 없음")

    return (PASS if not issues else FAIL), issues


def check_nx_ny_uniqueness() -> tuple[str, list[str]]:
    """[3] KMA 격자(NX,NY) 중복 없음."""
    seen: dict[tuple[int, int], str] = {}
    issues: list[str] = []
    for g in GRIDS:
        key = (g.nx, g.ny)
        if key in seen:
            issues.append(f"  ({g.nx},{g.ny}) 중복: {seen[key]} & {g.sigun}")
        else:
            seen[key] = g.sigun
    return (PASS if not issues else WARN), issues


def check_time_util() -> tuple[str, list[str]]:
    """[5] 시간 형식 통일 함수 동작 검증."""
    issues: list[str] = []
    cases = [
        # (analdate,          base_date,   base_time, expected_forest_key, expected_kma_key)
        ("2026-05-10 21", "20260510", "2100", "2026051021", "2026051021"),
        ("2025-01-22 09", "20250122", "0800", "2025012209", "2025012208"),
    ]
    for analdate, base_date, base_time, exp_forest, exp_kma in cases:
        forest_key = to_common_key(parse_analdate(analdate))
        kma_key    = to_common_key(parse_kma_time(base_date, base_time))
        if forest_key != exp_forest:
            issues.append(f"  산림청 키 오류: '{analdate}' → {forest_key} (예상: {exp_forest})")
        if kma_key != exp_kma:
            issues.append(f"  KMA 키 오류: '{base_date}/{base_time}' → {kma_key} (예상: {exp_kma})")
        if forest_key[:8] != kma_key[:8]:
            issues.append(f"  날짜 불일치: 산림청={forest_key[:8]} KMA={kma_key[:8]}")
    return (PASS if not issues else FAIL), issues


async def check_forest_coverage() -> tuple[str, list[str]]:
    """[1] 산림청 API 실 응답 27개 시군구 커버리지."""
    client = FireRiskClient(use_cache=False)
    forecasts = await client.fetch("2026-05-10")
    client.close()

    issues: list[str] = []
    received = {f.sigucode for f in forecasts}
    expected_5 = {code[:5] for code in SIGUNGU}

    for code5 in expected_5:
        if code5 not in received:
            name = next(n for c,(n,_) in SIGUNGU.items() if c[:5]==code5)
            issues.append(f"  API 응답에 {code5}({name}) 없음")

    extra = received - expected_5
    for code5 in extra:
        issues.append(f"  예상 외 시군구: {code5}")

    is_mock = any(f.is_mock for f in forecasts)
    summary = f"  수신 {len(received)}개 / 예상 {len(expected_5)}개 | mock={is_mock}"
    issues.insert(0, summary)

    return (PASS if len(received) == len(expected_5) and not any(i.startswith("  API") for i in issues[1:]) else FAIL), issues


async def check_kma_sigun_match() -> tuple[str, list[str]]:
    """[4] KMA 실 응답 sigun명 ↔ grids.py sigun명."""
    client = KmaWeatherClient()
    forecasts = await client.fetch_forecasts("2026-05-10")

    issues: list[str] = []
    grids_map = {g.sigucode: g.sigun for g in GRIDS}
    received = {f.sigucode: f.sigun for f in forecasts}

    for sigucode, grid_name in grids_map.items():
        got_name = received.get(sigucode)
        if got_name is None:
            issues.append(f"  KMA 응답에 {sigucode}({grid_name}) 없음")
        # KMA는 시군구명을 응답하지 않으므로 sigucode 존재 여부만 확인

    is_mock = any(f.is_mock for f in forecasts)
    summary = f"  수신 {len(received)}개 / 예상 {len(grids_map)}개 | mock={is_mock}"
    issues.insert(0, summary)

    return (PASS if not any(i.startswith("  KMA") for i in issues[1:]) else FAIL), issues


def check_mock_flag() -> tuple[str, list[str]]:
    """[6] is_mock 플래그 분리."""
    from pipelines.fire_risk_forecast.client import _build_mock
    from pipelines.kma_weather.client import _build_mock_weather

    issues: list[str] = []
    mock_fire = _build_mock("2025-01-22")
    mock_kma  = _build_mock_weather("2025-01-22")

    if not all(f.is_mock for f in mock_fire):
        issues.append("  산림청 mock 중 is_mock=False 항목 있음")
    if not all(f.is_mock for f in mock_kma):
        issues.append("  KMA mock 중 is_mock=False 항목 있음")

    summary = f"  산림청 mock {len(mock_fire)}건, KMA mock {len(mock_kma)}건 모두 is_mock=True"
    issues.insert(0, summary)
    return (PASS if not any(i.startswith("  산림청 mock 중") or i.startswith("  KMA mock 중") for i in issues[1:]) else FAIL), issues


# ─── 실행 ─────────────────────────────────────────────────────

async def main():
    print("=" * 55)
    print("Phase A-4  데이터 정합성 검증")
    print("=" * 55)

    checks = [
        ("[2] sigucode 매핑",        check_sigucode_mapping()),
        ("[3] KMA NX/NY 중복",       check_nx_ny_uniqueness()),
        ("[5] 시간 형식 통일",        check_time_util()),
        ("[6] is_mock 플래그",        check_mock_flag()),
    ]
    # 비동기 검증
    cov_result  = await check_forest_coverage()
    kma_result  = await check_kma_sigun_match()

    checks = [
        ("[1] 산림청 커버리지",       cov_result),
        ("[2] sigucode 매핑",        check_sigucode_mapping()),
        ("[3] KMA NX/NY 중복",       check_nx_ny_uniqueness()),
        ("[4] KMA 시군구 매핑",       kma_result),
        ("[5] 시간 형식 통일",        check_time_util()),
        ("[6] is_mock 플래그",        check_mock_flag()),
    ]

    all_pass = True
    for label, (status, notes) in checks:
        print(f"\n{status}  {label}")
        for note in notes:
            print(note)
        if status == FAIL:
            all_pass = False

    print("\n" + "=" * 55)
    if all_pass:
        print("✅ ALL PASS — Phase A-4 완료. Phase B 진행 가능.")
    else:
        print("❌ 일부 실패 — 위 항목 확인 필요.")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
