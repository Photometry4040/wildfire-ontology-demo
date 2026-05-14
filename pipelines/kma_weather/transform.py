# WeatherForecast / WeatherWarning → TypeDB INSERT TypeQL 변환
# 출처: docs/04_data-lineage.md §SpreadToAssetSignal §WateringActionabilitySignal
#
# 필요 스키마 (Phase B에서 02_dol_schema/schema/에 추가 예정):
#   attribute reh-pct,   value double;   # 상대습도 %
#   attribute wsd-ms,    value double;   # 풍속 m/s
#   attribute vec-deg,   value long;     # 풍향 °
#   attribute pcp-mm,    value double;   # 강수량 mm
#   attribute tmp-c,     value double;   # 기온 °C
#   attribute fcst-date, value string;
#   attribute fcst-time, value string;
#   attribute warn-var,  value string;   # 특보 종류
#   attribute is-dry-warn,  value boolean;
#   attribute is-wind-warn, value boolean;
#   entity kma-weather-forecast,
#     owns sigucode, owns fcst-date, owns fcst-time,
#     owns reh-pct, owns wsd-ms, owns vec-deg, owns pcp-mm, owns tmp-c,
#     owns is-mock;
#   entity kma-weather-warning,
#     owns stn-id, owns warn-var, owns warn-str,
#     owns is-dry-warn, owns is-wind-warn, owns is-mock;
from __future__ import annotations

try:
    from .client import WeatherForecast, WeatherWarning
except ImportError:
    from client import WeatherForecast, WeatherWarning  # type: ignore


def forecasts_to_typeql(forecasts: list[WeatherForecast]) -> str:
    if not forecasts:
        return "# (데이터 없음)"
    lines = ["insert"]
    for i, f in enumerate(forecasts):
        mock_val = "true" if f.is_mock else "false"
        lines.append(
            f'  $wf{i} isa kma-weather-forecast, '
            f'has sigucode "{f.sigucode}", '
            f'has fcst-date "{f.fcst_date}", '
            f'has fcst-time "{f.fcst_time}", '
            f'has reh-pct {f.reh}, '
            f'has wsd-ms {f.wsd}, '
            f'has vec-deg {f.vec}, '
            f'has pcp-mm {f.pcp}, '
            f'has tmp-c {f.tmp}, '
            f'has is-mock {mock_val};'
        )
    return "\n".join(lines)


def warnings_to_typeql(warnings: list[WeatherWarning]) -> str:
    if not warnings:
        return "# (특보 없음)"
    lines = ["insert"]
    for i, w in enumerate(warnings):
        mock_val = "true" if w.is_mock else "false"
        lines.append(
            f'  $ww{i} isa kma-weather-warning, '
            f'has stn-id "{w.stn_id}", '
            f'has warn-var "{w.warn_var}", '
            f'has is-dry-warn {"true" if w.is_dry else "false"}, '
            f'has is-wind-warn {"true" if w.is_wind else "false"}, '
            f'has is-mock {mock_val};'
        )
    return "\n".join(lines)


def forecasts_to_records(forecasts: list[WeatherForecast]) -> list[dict]:
    return [
        {"sigucode": f.sigucode, "sigun": f.sigun, "uplocalcd": f.uplocalcd,
         "fcst_date": f.fcst_date, "fcst_time": f.fcst_time,
         "reh": f.reh, "wsd": f.wsd, "vec": f.vec, "pcp": f.pcp, "tmp": f.tmp,
         "is_mock": f.is_mock}
        for f in forecasts
    ]
