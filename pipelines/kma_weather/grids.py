# 광주·전남 시군구 → 기상청 동네예보 격자(NX, NY) 매핑
# sigucode: 산림청 API 실 응답 기준 (2026-05-10 verificated)
# NX/NY: 기상청 동네예보 격자 좌표표 기준 시군구 중심점 근사값

from dataclasses import dataclass

@dataclass(frozen=True)
class GridInfo:
    sigucode: str    # 10자리 (API sigucode 5자리 + "00000")
    sigun: str
    uplocalcd: str
    nx: int          # 동네예보 격자 X
    ny: int          # 동네예보 격자 Y
    stn_id: str      # 기상특보 관측소 코드 (인근 관측소)

GRIDS: list[GridInfo] = [
    # 광주광역시 (uplocalcd=29)
    GridInfo("2911000000", "동구",   "29", 58, 74, "156"),
    GridInfo("2914000000", "서구",   "29", 57, 74, "156"),
    GridInfo("2915500000", "남구",   "29", 58, 73, "156"),
    GridInfo("2917000000", "북구",   "29", 59, 75, "156"),
    GridInfo("2920000000", "광산구", "29", 56, 74, "156"),
    # 전라남도 (uplocalcd=46) — sigucode API verificated
    GridInfo("4611000000", "목포시", "46", 50, 67, "165"),
    GridInfo("4613000000", "여수시", "46", 73, 66, "168"),
    GridInfo("4615000000", "순천시", "46", 70, 70, "192"),
    GridInfo("4617000000", "나주시", "46", 56, 71, "156"),
    GridInfo("4623000000", "광양시", "46", 74, 70, "192"),
    GridInfo("4671000000", "담양군", "46", 61, 78, "156"),
    GridInfo("4672000000", "곡성군", "46", 66, 73, "192"),  # ★ 2025-01-22 산불
    GridInfo("4673000000", "구례군", "46", 69, 72, "192"),
    GridInfo("4677000000", "고흥군", "46", 66, 62, "262"),
    GridInfo("4678000000", "보성군", "46", 62, 66, "262"),
    GridInfo("4679000000", "화순군", "46", 62, 72, "156"),
    GridInfo("4680000000", "장흥군", "46", 58, 64, "165"),
    GridInfo("4681000000", "강진군", "46", 57, 63, "165"),
    GridInfo("4682000000", "해남군", "46", 54, 61, "165"),
    GridInfo("4683000000", "영암군", "46", 56, 66, "165"),
    GridInfo("4684000000", "무안군", "46", 52, 70, "165"),
    GridInfo("4686000000", "함평군", "46", 54, 72, "165"),
    GridInfo("4687000000", "영광군", "46", 52, 77, "156"),
    GridInfo("4688000000", "장성군", "46", 57, 77, "156"),
    GridInfo("4689000000", "완도군", "46", 60, 57, "170"),
    GridInfo("4690000000", "진도군", "46", 48, 60, "165"),
    GridInfo("4691000000", "신안군", "46", 50, 65, "165"),
]

_BY_NX_NY: dict[tuple[int, int], GridInfo]  = {(g.nx, g.ny): g for g in GRIDS}
_BY_SIGUCODE: dict[str, GridInfo]            = {g.sigucode: g for g in GRIDS}
UNIQUE_STN_IDS: list[str]                    = sorted({g.stn_id for g in GRIDS})
