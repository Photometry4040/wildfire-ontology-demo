# Feature Contract

## 역할

Feature contract는 17개 Feature가 어떤 입력 field와 Derived Dataset을 읽고, mock/exclude 영향을 어떻게 confidence로 전파하는지 정의한다. 점수 공식은 [06_decision-logic.md](06_decision-logic.md)에 둔다.

## 공통 출력

모든 Feature는 다음 record를 출력한다.

```text
{
  score: [0, 1],
  class: categorical label,
  mock_input: bool,
  confidence: high | medium-high | medium | medium-low | low
}
```

원칙:

- mock 여부는 score에 반영하지 않는다.
- mock 여부와 EXCLUDE 영향은 `mock_input`과 `confidence`로만 전파한다.
- Decision 단계에서만 confidence가 `RequestManualReview` 또는 `advisory_only` gating에 사용된다.

## Feature Summary

| # | Feature | Signal | 주 입력 | mock 영향 | EXCLUDE 영향 | confidence |
|---|---|---|---|---|---|---|
| 1 | `FireRiskLevelFeature` | OfficialRisk | `DERIVED_FIRE_RISK_TIMESERIES` | 없음 | 없음 | high |
| 2 | `FireRiskTrendFeature` | OfficialRisk | official risk horizon `d1..d4` | 없음 | 없음 | high |
| 3 | `LargeFireRiskAlertFeature` | OfficialRisk | `DERIVED_LARGE_FIRE_ALERT` | fallback 산식 사용 시 KMA 관측(REH/WS) 의존 | 없음 | high (primary) / medium-high (fallback) |
| 4 | `ResidentialExposureFeature` | Exposure | building, population, admin, forest | 없음 | settlement boundary 제거 | medium-high |
| 5 | `CriticalAssetFeature` | Exposure | heritage, public facility, vulnerable facility | 전남 vulnerable 일부 | critical infrastructure detail 제거 | medium-high |
| 6 | `ForestInterfaceFeature` | Exposure | forest and asset geometry | 전남 vulnerable 일부 | 없음 | medium |
| 7 | `WindTowardAssetFeature` | SpreadToAsset | KMA forecast/observed wind, asset bearing | asset 측 일부 | 없음 | medium |
| 8 | `TerrainTowardAssetFeature` | SpreadToAsset | forest to asset bearing | asset 측 일부 | DEM 제거 | medium-low |
| 9 | `FuelContinuityFeature` | SpreadToAsset | forest, road, forest road | 없음 | natural barriers 제거 | medium-high |
| 10 | `VehicleAccessFeature` | WateringActionability | road geometry, road access mock | 폭/회차/포장/경사 mock | DEM 제거 | low |
| 11 | `WaterSourceFeature` | WateringActionability | municipal fire water mock, forest-fire facilities | mock dominant | natural water 제거 | low |
| 12 | `WettableBarrierFeature` | WateringActionability | surface fuel mock, forest/building/road geometry | 지표연료 mock | natural barriers 제거 | low |
| 13 | `WorkSafetyFeature` | WateringActionability | road access mock, worksite hazard mock, warning, sun event | mock dominant | DEM 제거 | medium-low |
| 14 | `HighRiskTimeWindowFeature` | TimeUrgency | official risk, KMA weather grid | 없음 | 없음 | medium |
| 15 | `DispatchLeadTimeFeature` | TimeUrgency | station geocoding, road network, access mock | 접근성 일부 | 없음 | medium-low |
| 16 | `WateringDurationFeature` | TimeUrgency | equipment/resource/access mock, segment metrics | 거의 전적 mock | 없음 | low |
| 17 | `RainOffsetFeature` | TimeUrgency | KMA precipitation grid | 없음 | 없음 | medium |

## Field-Level Contract by Signal

### OfficialRiskSignal

| Feature | 직접 입력 | raw lineage | 주요 한계 |
|---|---|---|---|
| `FireRiskLevelFeature` | `DERIVED_FIRE_RISK_TIMESERIES.{sigucode,forecast_time,risk_index_mean,risk_index_max,risk_grade}` | `SOURCE_OFFICIAL_FIRE_RISK_FORECAST.{sigucode,analdate,meanavg,maxi,std}` | 시군구 grain. 읍면동 fan-out 금지 |
| `FireRiskTrendFeature` | `DERIVED_FIRE_RISK_TIMESERIES.{d1_grade,d2_grade,d3_grade,d4_grade,trend_delta}` | `SOURCE_OFFICIAL_FIRE_RISK_FORECAST.{d1,d2,d3,d4,meanavg}` | historical trend가 아니라 single horizon 내부 trend |
| `LargeFireRiskAlertFeature` | `DERIVED_LARGE_FIRE_ALERT.{legal_emd_code,forecast_time,large_fire_alert_level,humidity,wind_speed,risk_index_at_emd,persistence_days,fallback_flag}` | primary: `SOURCE_LARGE_FIRE_RISK_FORECAST.{시도명,시군구명,읍면동명,예보일시,등급,실효습도,풍속}` / fallback: `SOURCE_OFFICIAL_FIRE_RISK_FORECAST.{sigucode,maxi}` + `SOURCE_KMA_OBSERVED_WEATHER.{REH,WS}` (시군구→읍면동 inheritance, 2-day persistence window) | 행정코드 없음. name-based join 실패 가능. fallback 사용 시 sigungu inheritance + 2-day rolling window 필요 |

### ExposureSignal

| Feature | 직접 입력 | raw lineage | 주요 한계 |
|---|---|---|---|
| `ResidentialExposureFeature` | `DERIVED_RESIDENTIAL_EXPOSURE.{residential_building_count,residential_population,residential_household_count,forest_to_residence_distance_m}` | `SOURCE_BUILDING_FOOTPRINTS`, `SOURCE_POPULATION_STATISTICS`, `SOURCE_ADMIN_BOUNDARIES`, `SOURCE_REGION_CODE_TABLE`, `SOURCE_FOREST_STAND_MAP` | settlement boundary 없음. building+admin proxy |
| `CriticalAssetFeature` | `DERIVED_CRITICAL_ASSET_EXPOSURE.{critical_asset_count,critical_asset_class_mix,critical_asset_min_distance_m}` | `SOURCE_HERITAGE_SPATIAL`, `SOURCE_PUBLIC_FACILITIES`, `SOURCE_VULNERABLE_FACILITIES` | public/vulnerable real address geocoding 필요. 전남 일부 mock 좌표 |
| `ForestInterfaceFeature` | `DERIVED_FOREST_INTERFACE.{forest_asset_distance_m,forest_asset_interface_length_m}` | forest geometry + building/heritage/public/vulnerable geometry | 모든 거리와 접점 길이는 derived |

### SpreadToAssetSignal

| Feature | 직접 입력 | raw lineage | 주요 한계 |
|---|---|---|---|
| `WindTowardAssetFeature` | `DERIVED_WIND_TOWARD_ASSET.{bearing_to_asset_deg,wind_toward_asset_flag,gust_toward_asset_flag}` and weather fields | `SOURCE_KMA_SHORT_TERM_FORECAST.{VEC,WSD,UUU,VVV}`, `SOURCE_KMA_OBSERVED_WEATHER.{WD,WS,GST_WD,GST_WS}` | KMA forecast recent-3-day. station interpolation 없음 |
| `TerrainTowardAssetFeature` | `DERIVED_TERRAIN_TOWARD_ASSET.forest_to_asset_bearing_class` | `SOURCE_FOREST_STAND_MAP.geometry`, asset geometry | DEM 제외로 slope/aspect/elevation 없음 |
| `FuelContinuityFeature` | `DERIVED_FUEL_CONTINUITY.{forest_continuity_class,disconnect_count,forest_density_class}` | `SOURCE_FOREST_STAND_MAP`, `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK` | natural barrier 없음. 광주 임도 0 |

### WateringActionabilitySignal

| Feature | 직접 입력 | raw lineage | 주요 한계 |
|---|---|---|---|
| `VehicleAccessFeature` | `DERIVED_VEHICLE_ACCESS.{vehicle_accessible_flag,road_width_class,road_surface_constraint_class,turnaround_class}` | `SOURCE_ROAD_ACCESS_CONSTRAINTS`, `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK` | 핵심 접근성 attribute는 mock |
| `WaterSourceFeature` | `DERIVED_WATER_SOURCE_ACCESS.{nearest_water_source_distance_m,water_source_capacity_class}` | `SOURCE_MUNICIPAL_FIRE_WATER_FACILITIES`, `SOURCE_FOREST_FIRE_EXTINGUISHING_FACILITIES` | 광주는 사실상 mock-only |
| `WettableBarrierFeature` | `DERIVED_WETTABLE_BARRIER.{surface_fuel_class,barrier_effectiveness_class}` | `SOURCE_SURFACE_FUEL_CONDITION`, forest/building/road geometry | 지표연료 100% mock |
| `WorkSafetyFeature` | `DERIVED_WORK_SAFETY.{narrow_road_class,rockfall_risk_class,smoke_risk_class,wind_warning_class,night_flag}` | `SOURCE_ROAD_ACCESS_CONSTRAINTS`, `SOURCE_WORKSITE_HAZARD_CONDITIONS`, `SOURCE_KMA_WEATHER_WARNINGS`, `SOURCE_SUN_EVENT_CALENDAR` | 강풍특보/일출일몰만 real |

### TimeUrgencySignal

| Feature | 직접 입력 | raw lineage | 주요 한계 |
|---|---|---|---|
| `HighRiskTimeWindowFeature` | `DERIVED_HIGH_RISK_TIME_WINDOW.risk_window_class` | official risk + KMA TMP/REH/WSD | 시군구 risk를 segment로 inheritance |
| `DispatchLeadTimeFeature` | `DERIVED_ROUTE_TRAVEL_TIME.{expected_travel_time_min,route_method}` | station address, road network, forest road, road access mock | station geocoding 필수 |
| `WateringDurationFeature` | `DERIVED_WATERING_DURATION.{expected_watering_duration_min,equipment_combo_class}` | equipment capacity mock, resource availability mock, road access mock, segment metrics | mock dominant |
| `RainOffsetFeature` | `DERIVED_RAIN_OFFSET.{expected_rainfall_mm,rain_start_at,rain_probability,rain_duration_hr}` | KMA PCP/POP/PTY | recent forecast window 제약 |

## Confidence Closure

| closure type | 의미 | 자동 실행 영향 |
|---|---|---|
| `closed` | raw/derived path가 실제 source로 닫힘 | score 사용 가능 |
| `closed with gap` | path는 닫혔지만 grain/time/category limitation 존재 | confidence 격하 |
| `closed mock dominant` | definition은 닫혔지만 핵심 입력이 mock | hard gate 자동 실행 금지 |
| `meaning reduced` | EXCLUDE 때문에 원래 의미를 좁혀 사용 | manual review 사유로 보존 |
| `unavailable` | 해당 contribution을 계산하지 않음 | score 식에서 제거 |

현재 mock dominant Feature는 `VehicleAccessFeature`, `WaterSourceFeature`, `WettableBarrierFeature`, `WorkSafetyFeature`, `WateringDurationFeature`다. 이들은 판단 score 산출에는 들어가지만 자동 배정이나 자동 보류 같은 hard gate의 단독 근거로 쓰지 않는다.
