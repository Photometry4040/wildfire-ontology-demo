# Data Lineage

## 역할

이 문서는 Source가 Derived Dataset, Feature, Signal로 어떻게 흐르는지 정의한다. 실제 field 단위 입력은 [05_feature-contract.md](05_feature-contract.md), score 계산식은 [06_decision-logic.md](06_decision-logic.md)에 둔다.

## Signal Map

```text
OfficialRiskSignal
ExposureSignal
SpreadToAssetSignal
WateringActionabilitySignal
TimeUrgencySignal
  -> PreWateringPrioritySignal
```

`PreWateringPrioritySignal`은 별도 Source를 요구하지 않고 위 5개 Signal을 종합한다.

## Feature to Source Map

### OfficialRiskSignal

| Feature | Source |
|---|---|
| `FireRiskLevelFeature` | `SOURCE_OFFICIAL_FIRE_RISK_FORECAST`, `SOURCE_REGION_CODE_TABLE` |
| `FireRiskTrendFeature` | `SOURCE_OFFICIAL_FIRE_RISK_FORECAST` |
| `LargeFireRiskAlertFeature` | `SOURCE_LARGE_FIRE_RISK_FORECAST` (primary), `SOURCE_OFFICIAL_FIRE_RISK_FORECAST` + `SOURCE_KMA_OBSERVED_WEATHER` (fallback derivation) |

### ExposureSignal

| Feature | Source |
|---|---|
| `ResidentialExposureFeature` | `SOURCE_BUILDING_FOOTPRINTS`, `SOURCE_POPULATION_STATISTICS`, `SOURCE_ADMIN_BOUNDARIES`, `SOURCE_REGION_CODE_TABLE`, `SOURCE_FOREST_STAND_MAP` |
| `CriticalAssetFeature` | `SOURCE_HERITAGE_SPATIAL`, `SOURCE_VULNERABLE_FACILITIES`, `SOURCE_PUBLIC_FACILITIES` |
| `ForestInterfaceFeature` | `SOURCE_FOREST_STAND_MAP`, `SOURCE_BUILDING_FOOTPRINTS`, `SOURCE_PUBLIC_FACILITIES`, `SOURCE_VULNERABLE_FACILITIES`, `SOURCE_HERITAGE_SPATIAL` |

### SpreadToAssetSignal

| Feature | Source |
|---|---|
| `WindTowardAssetFeature` | `SOURCE_KMA_SHORT_TERM_FORECAST`, `SOURCE_KMA_OBSERVED_WEATHER`, asset geometry sources |
| `TerrainTowardAssetFeature` | `SOURCE_FOREST_STAND_MAP`, asset geometry sources |
| `FuelContinuityFeature` | `SOURCE_FOREST_STAND_MAP`, `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK`, asset geometry sources |

### WateringActionabilitySignal

| Feature | Source |
|---|---|
| `VehicleAccessFeature` | `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK`, `SOURCE_ROAD_ACCESS_CONSTRAINTS` |
| `WaterSourceFeature` | `SOURCE_MUNICIPAL_FIRE_WATER_FACILITIES`, `SOURCE_FOREST_FIRE_EXTINGUISHING_FACILITIES` |
| `WettableBarrierFeature` | `SOURCE_SURFACE_FUEL_CONDITION`, `SOURCE_FOREST_STAND_MAP`, `SOURCE_BUILDING_FOOTPRINTS`, `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK` |
| `WorkSafetyFeature` | `SOURCE_ROAD_ACCESS_CONSTRAINTS`, `SOURCE_WORKSITE_HAZARD_CONDITIONS`, `SOURCE_KMA_WEATHER_WARNINGS`, `SOURCE_SUN_EVENT_CALENDAR`, `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK` |

### TimeUrgencySignal

| Feature | Source |
|---|---|
| `HighRiskTimeWindowFeature` | `SOURCE_OFFICIAL_FIRE_RISK_FORECAST`, `SOURCE_KMA_SHORT_TERM_FORECAST` |
| `DispatchLeadTimeFeature` | `SOURCE_FIRE_STATION_CENTERS`, `SOURCE_ROAD_NETWORK`, `SOURCE_FOREST_ROAD_NETWORK`, `SOURCE_ROAD_ACCESS_CONSTRAINTS` |
| `WateringDurationFeature` | `SOURCE_ROAD_ACCESS_CONSTRAINTS`, `SOURCE_PREWATERING_EQUIPMENT_CAPACITY`, `SOURCE_FIRE_RESOURCE_AVAILABILITY` |
| `RainOffsetFeature` | `SOURCE_KMA_SHORT_TERM_FORECAST` |

## Foundation Derived Datasets

| derived_dataset_id | 입력 | 처리 | 후속 |
|---|---|---|---|
| `DERIVED_ADMIN_CODE_HARMONIZED` | `SOURCE_REGION_CODE_TABLE`, `SOURCE_POPULATION_STATISTICS` | 법정동, 행정동, MOIS 행정기관 코드 namespace 정렬 | AOI, risk timeseries, residential exposure |
| `DERIVED_PROJECT_AOI` | `SOURCE_ADMIN_BOUNDARIES`, `DERIVED_ADMIN_CODE_HARMONIZED` | 광주·전남 geometry dissolve | 전체 spatial lineage |
| `DERIVED_FIRE_STATION_LOCATIONS` | `SOURCE_FIRE_STATION_CENTERS` | 주소 geocoding, CRS 통일, 행정구역 lookup | route travel time |
| `DERIVED_PUBLIC_FACILITY_LOCATIONS` | `SOURCE_PUBLIC_FACILITIES` | 파일별 name/address normalize, geocoding | critical asset, forest interface |
| `DERIVED_VULNERABLE_FACILITY_LOCATIONS` | `SOURCE_VULNERABLE_FACILITIES` | real address geocoding + mock point cast | critical asset, forest interface |
| `DERIVED_OBSERVED_WEATHER_AT_SEGMENT` | `SOURCE_KMA_OBSERVED_WEATHER`, segment candidates | nearest station mapping | wind toward asset |

## Active Derived Datasets

| derived_dataset_id | 주요 입력 | 사용 Feature |
|---|---|---|
| `DERIVED_PREWATERING_SEGMENT_CANDIDATES` | forest, building, admin, heritage, public/vulnerable facilities, road/forest road | 모든 segment Feature |
| `DERIVED_SEGMENT_GEOMETRY_METRICS` | segment geometry | `WateringDurationFeature`, `DispatchLeadTimeFeature`, `WorkSafetyFeature` |
| `DERIVED_FIRE_RISK_TIMESERIES` | official fire risk forecast, admin code | `FireRiskLevelFeature`, `FireRiskTrendFeature`, `HighRiskTimeWindowFeature` |
| `DERIVED_LARGE_FIRE_ALERT` | large fire risk forecast (primary), official fire risk forecast + KMA observed weather (fallback per 산림청 발령 기준), admin code | `LargeFireRiskAlertFeature` |
| `DERIVED_WEATHER_GRID_TO_SEGMENT` | KMA short-term forecast, segment geometry | `WindTowardAssetFeature`, `HighRiskTimeWindowFeature`, `RainOffsetFeature` |
| `DERIVED_WIND_TOWARD_ASSET` | weather grid, observed weather, asset geometry | `WindTowardAssetFeature` |
| `DERIVED_TERRAIN_TOWARD_ASSET` | forest geometry, asset geometry | `TerrainTowardAssetFeature` |
| `DERIVED_FUEL_CONTINUITY` | forest, road, forest road, asset geometry | `FuelContinuityFeature` |
| `DERIVED_RESIDENTIAL_EXPOSURE` | building, population, admin boundary/code, forest | `ResidentialExposureFeature` |
| `DERIVED_CRITICAL_ASSET_EXPOSURE` | heritage, public/vulnerable facility locations | `CriticalAssetFeature` |
| `DERIVED_FOREST_INTERFACE` | forest, building, public/vulnerable/heritage asset geometry | `ForestInterfaceFeature` |
| `DERIVED_VEHICLE_ACCESS` | road, forest road, road-access mock | `VehicleAccessFeature` |
| `DERIVED_WATER_SOURCE_ACCESS` | municipal fire water mock, forest-fire extinguishing facilities | `WaterSourceFeature` |
| `DERIVED_WETTABLE_BARRIER` | surface fuel mock, forest, building, road, forest road | `WettableBarrierFeature` |
| `DERIVED_WORK_SAFETY` | road-access mock, worksite hazard mock, KMA warnings, sun events | `WorkSafetyFeature` |
| `DERIVED_ROUTE_TRAVEL_TIME` | station locations, road network, road-access mock, segment geometry | `DispatchLeadTimeFeature` |
| `DERIVED_WATERING_DURATION` | equipment capacity mock, resource availability mock, road-access mock, segment metrics | `WateringDurationFeature` |
| `DERIVED_HIGH_RISK_TIME_WINDOW` | fire risk timeseries, weather grid | `HighRiskTimeWindowFeature` |
| `DERIVED_RAIN_OFFSET` | weather grid precipitation categories | `RainOffsetFeature` |

## Removed Inputs

| excluded source | removed contribution | current handling |
|---|---|---|
| `SOURCE_DEM_ELEVATION` | slope, aspect, elevation, road slope | unavailable or mock slope proxy only |
| `SOURCE_SETTLEMENT_BOUNDARIES` | settlement polygon interface | building + population + admin proxy |
| `SOURCE_NATURAL_WATER_SOURCES` | river/reservoir water source | municipal and forest-fire facilities only |
| `SOURCE_NATURAL_BARRIERS` | river/open-space barrier | road, forest road, building, forest interface proxy |
| `SOURCE_CRITICAL_INFRASTRUCTURE_DETAIL` | power/telecom detail exposure | manual review reason only |

## Transform Vocabulary

| transform | 의미 |
|---|---|
| `lookup` | code/name mapping |
| `cast/parse` | type conversion, time parse |
| `geocode` | address to point |
| `crs_unify` | common CRS conversion |
| `spatial_overlay` | intersect, buffer, distance, length |
| `temporal_align` | time grid normalization |
| `aggregate` | group by, sum, mean, count |
| `derive` | formula or categorical derivation |
| `category_pivot` | KMA long category rows to wide feature columns |
| `network_route` | road network based travel time or fallback |
