# 행정동 주민등록 인구통계 로더
# 출처: docs/source_inventory.json SOURCE_POPULATION_STATISTICS
# 파일: data/raw/SOURCE_POPULATION_STATISTICS/snapshots/population_202604.csv
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent.parent / \
    "data/raw/SOURCE_POPULATION_STATISTICS/snapshots/population_202604.csv"

TARGET_PREFIXES = ("29", "46")  # 광주, 전남


@dataclass(frozen=True)
class PopRecord:
    sigucode: str    # 10자리 행정기관코드
    name: str        # 행정기관명 (시군구 또는 읍면동)
    population: int  # 총인구수
    households: int  # 세대수
    level: str       # "sigungu" | "dong"


def _parse_int(s: str) -> int:
    return int(s.replace(",", "").strip()) if s.strip() else 0


def _extract_code_name(field: str) -> tuple[str, str] | None:
    m = re.match(r"(.+?)\s*\((\d{10})\)", field.strip())
    return (m.group(2), m.group(1).strip()) if m else None


def load(path: Path = DATA_PATH) -> list[PopRecord]:
    """population_202604.csv → 광주·전남 PopRecord 리스트."""
    records: list[PopRecord] = []
    with open(path, encoding="euc-kr") as f:
        reader = csv.reader(f)
        next(reader)  # 헤더 건너뜀
        for row in reader:
            if not row:
                continue
            parsed = _extract_code_name(row[0])
            if not parsed:
                continue
            code, name = parsed
            if code[:2] not in TARGET_PREFIXES:
                continue
            pop = _parse_int(row[1])
            hh  = _parse_int(row[2])
            # 뒤 5자리가 00000 → 시군구 레벨, 아니면 읍면동
            level = "sigungu" if code[5:] == "00000" else "dong"
            records.append(PopRecord(sigucode=code, name=name,
                                     population=pop, households=hh, level=level))
    return records


def sigungu_population(path: Path = DATA_PATH) -> dict[str, PopRecord]:
    """sigucode(10자리) → PopRecord (시군구 레벨만)."""
    return {r.sigucode: r for r in load(path) if r.level == "sigungu"}


def dong_population(path: Path = DATA_PATH) -> dict[str, PopRecord]:
    """sigucode(10자리) → PopRecord (읍면동 레벨만)."""
    return {r.sigucode: r for r in load(path) if r.level == "dong"}
