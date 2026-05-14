# FireRiskForecast → TypeDB INSERT TypeQL 변환
# 출처: docs/04_data-lineage.md §OfficialRiskSignal
#
# 아래 스키마 정의가 TypeDB에 추가되어야 함 (Phase B에서 02_dol_schema/schema/에 추가 예정):
#
#   attribute risk-d1,    value long;
#   attribute risk-d2,    value long;
#   attribute risk-d3,    value long;
#   attribute risk-d4,    value long;
#   attribute risk-maxi,  value long;
#   attribute is-mock,    value boolean;
#   entity fire-risk-forecast,
#     owns sigucode @key,
#     owns uplocalcd,
#     owns analdate,
#     owns risk-d1, owns risk-d2, owns risk-d3, owns risk-d4, owns risk-maxi,
#     owns is-mock;
from __future__ import annotations

try:
    from .client import FireRiskForecast
except ImportError:
    from client import FireRiskForecast  # type: ignore


def to_typeql_insert(forecasts: list[FireRiskForecast]) -> str:
    """FireRiskForecast 리스트 → TypeQL INSERT 문자열."""
    if not forecasts:
        return "# (데이터 없음)"
    lines = ["insert"]
    for i, f in enumerate(forecasts):
        mock_val = "true" if f.is_mock else "false"
        lines.append(
            f"  $frf{i} isa fire-risk-forecast, "
            f'has sigucode "{f.sigucode}", '
            f'has uplocalcd "{f.uplocalcd}", '
            f'has analdate "{f.analdate}", '
            f"has risk-d1 {f.d1}, "
            f"has risk-d2 {f.d2}, "
            f"has risk-d3 {f.d3}, "
            f"has risk-d4 {f.d4}, "
            f"has risk-maxi {f.maxi}, "
            f"has is-mock {mock_val};"
        )
    return "\n".join(lines)


def to_records(forecasts: list[FireRiskForecast]) -> list[dict]:
    """Python dict 리스트로 변환 (JSON 직렬화, 중간 처리용)."""
    return [
        {
            "sigucode":  f.sigucode,
            "sigun":     f.sigun,
            "uplocalcd": f.uplocalcd,
            "analdate":  f.analdate,
            "d1": f.d1, "d2": f.d2, "d3": f.d3, "d4": f.d4,
            "maxi":      f.maxi,
            "is_mock":   f.is_mock,
        }
        for f in forecasts
    ]
