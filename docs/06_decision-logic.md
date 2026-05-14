# Decision Logic

## 역할

이 문서는 Feature, Signal, State, Decision, Action의 v0 계산 규칙을 정의한다. 모든 weight와 threshold는 domain heuristic이며, 운영 검증 후 calibration 대상이다.

## 공통 원칙

- 모든 score는 `[0, 1]` 범위다.
- score 방향은 "예비주수 우선순위가 높을수록 1"로 통일한다.
- mock 여부와 confidence는 score에 곱하지 않는다.
- mock과 confidence는 Decision 단계에서만 manual review gate로 사용한다.

## 보조 함수

| 함수 | 정의 |
|---|---|
| `norm(x, [a, b])` | `clip(x, a, b)`를 `[0,1]`로 선형 정규화 |
| `inv(F)` | `1 - F` |
| `lookup(x, MAP)` | enum to numeric 또는 enum to enum |
| `level5(s)` | 낮음, 다소낮음, 보통, 다소높음, 높음 |
| `clip(x, a, b)` | x를 `[a, b]`로 잘라낸 값 |

## Confidence Ordinal

| confidence | factor | 의미 |
|---|---|---|
| `high` | 1.00 | 모든 입력 REAL, 가용성 안정 |
| `medium-high` | 0.92 | 주요 입력 REAL, 보조 입력 일부 mock 또는 derivation/proxy 의존 |
| `medium` | 0.85 | 핵심 입력 일부 mock 또는 derivation 비용 큼 |
| `medium-low` | 0.70 | 핵심 입력 mock 또는 partial coverage / EXCLUDE로 의미 일부 축소 |
| `low` | 0.50 | mock-dominant 또는 EXCLUDE로 의미 크게 축소 |

`factor`는 score 식에 곱하지 않는다. Decision 단계 manual review gate(§Decision Gate)의 분기 기준에만 사용된다.

## Canonical Mock Enum Catalog

mock CSV에 실제로 존재하는 canonical 영문 enum을 Feature 공식의 MAP key로 사용한다. raw → canonical 변환은 Derived 단계에서 수행한다. real source 한국어 등급(예: `OFFICIAL_FIRE_RISK_FORECAST.std`)은 그대로 사용한다.

| source_id | field | canonical values |
|---|---|---|
| `SOURCE_OFFICIAL_FIRE_RISK_FORECAST` | `std` (risk_grade) | `정상`, `낮음`, `다소높음`, `높음`, `매우높음` (산림청 5단계) |
| | `maxi`/`meanavg` (risk_index) | numeric `[0, 100]`; 등급 임계 50 / 65 / 85 |
| `SOURCE_LARGE_FIRE_RISK_FORECAST` | `등급` (large_fire_alert_level) | `없음`, `주의보`, `경보` |
| `SOURCE_MUNICIPAL_FIRE_WATER_FACILITIES` | `facility_type` | `hydrant`, `emergency_fire_device`, `water_tower`, `water_tank` |
| | `usable_status` | `usable`, `limited`, `unknown` |
| | `supply_capacity_class` | `high`, `medium`, `low` |
| `SOURCE_SURFACE_FUEL_CONDITION` | `surface_fuel_type` | `leaf_litter`, `dry_grass`, `conifer_understory`, `shrub`, `roadside_fuel` |
| | `surface_fuel_load_class` | `high`, `medium`, `low` |
| | `wetting_response_class` | `high`, `medium`, `low` |
| `SOURCE_ROAD_ACCESS_CONSTRAINTS` | `road_class` | `arterial`, `local`, `residential`, `mountain_access`, `forest_track` |
| | `access_constraint_class` | `accessible`, `limited_turnaround`, `restricted` |
| | `firetruck_accessible`, `turnaround_available`, `narrow_road_flag`, `paved_flag` | `True`, `False` |
| | `road_width_m` (numeric, 관측 2.6~6.8) / `slope_percent` (numeric, 관측 1.0~11.8) | numeric |
| `SOURCE_WORKSITE_HAZARD_CONDITIONS` | `hazard_severity` | `high`, `medium`, `low` |
| | `rockfall_risk_flag`, `smoke_exposure_possible`, `night_operation_flag`, `access_constraint_flag`, `wind_hazard_flag` | `True`, `False` |
| `SOURCE_FIRE_RESOURCE_AVAILABILITY` | `resource_status` | `available`, `limited`, `unavailable` |
| `SOURCE_PREWATERING_EQUIPMENT_CAPACITY` | `equipment_type` | `engine`, `water_tanker`, `portable_pump`, `small_vehicle` |

Derived class enum도 canonical을 명시한다.

| derived field | values |
|---|---|
| `DERIVED_TERRAIN_TOWARD_ASSET.forest_to_asset_bearing_class` | `정면`, `사면-가까움`, `사면-먼`, `외면` |
| `DERIVED_FUEL_CONTINUITY.forest_continuity_class` | `연속`, `부분단절`, `단절` |
| `DERIVED_FUEL_CONTINUITY.forest_density_class` | `조밀`, `보통`, `성긴`, `미입목` (FOREST_STAND_MAP DNST_NM 기반) |

## Feature Formulas

### OfficialRiskSignal

```text
# 산림청 5단계 등급 기준 (KFS DFFRI):
# - 정상      : 산불 위험이 거의 없음
# - 낮음      (index ≤ 50)  : 산불 발생 위험이 상대적으로 낮음
# - 다소높음   (51 ≤ index ≤ 65) : 평소보다 높음. 건조·강풍 시 주의
# - 높음      (66 ≤ index ≤ 85) : 산불 발생 위험이 높아 대형 산불 주의
# - 매우높음   (index ≥ 86) : 즉각적 대응이 필요한 상황

risk_grade_score(g) = lookup(g, {
  정상:0.00, 낮음:0.20, 다소높음:0.55, 높음:0.75, 매우높음:1.00
})

risk_index_score(x) = piecewise_linear(x, breakpoints=[
  (0,0.00), (50,0.20), (65,0.55), (85,0.75), (100,1.00)
])
# 임계점에서 grade 기반 score와 정확히 일치한다.

F_official_level = max(
  risk_grade_score(risk_grade),
  risk_index_score(risk_index_max)
)

# horizon score (d1..d4 또는 임의 forecast time t)
risk_grade_score_t = risk_grade_score(grade_at(t))
peak_grade_score    = max_t(risk_grade_score_t)   # over horizon d1..d4
current_grade_score = risk_grade_score(grade_now)

F_official_trend = clip(0.5 + (peak_grade_score - current_grade_score) * 1.5, 0, 1)

# Primary: 산림청이 발령한 published 등급
F_official_alert = lookup(large_fire_alert_level, {없음:0.0, 주의보:0.6, 경보:1.0})

# Fallback: published 등급이 비어 있을 때 산림청 발령 기준으로 재유도
# 입력은 SOURCE_OFFICIAL_FIRE_RISK_FORECAST + SOURCE_KMA_OBSERVED_WEATHER 조합
derived_alert(risk_index, 실효습도, 풍속, persistence_days) =
  경보   if risk_index ≥ 51 ∧ 실효습도 < 30        ∧ 풍속 ≥ 11  ∧ persistence_days ≥ 2
  주의보 if risk_index ≥ 51 ∧ 30 ≤ 실효습도 ≤ 45  ∧ 7 ≤ 풍속 < 11 ∧ persistence_days ≥ 2
  없음   otherwise
# fallback 사용 시 LargeFireRiskAlertFeature.confidence는 한 단계 격하한다 (high → medium-high).
# fallback_flag = true는 mock_input 전파와 별개로 §Decision Gate가 advisory 처리에 사용한다.
```

### ExposureSignal

```text
F_exposure_residential =
    0.40 * norm(residential_population, [0, 30000])
  + 0.20 * norm(residential_household_count, [0, 12000])
  + 0.15 * norm(residential_building_count, [0, 5000])
  + 0.25 * inv(norm(forest_to_residence_distance_m, [0, 2000]))

F_exposure_critical =
    0.45 * weighted_class_mix(critical_asset_class_mix, CLASS_WEIGHT, max_count_cap=20)
  + 0.20 * norm(critical_asset_count, [0, 20])
  + 0.35 * inv(norm(critical_asset_min_distance_m, [0, 2000]))

CLASS_WEIGHT = {
  문화재: 1.00,
  요양시설: 0.95,
  병원: 0.90,
  공공시설: 0.55
}

weighted_class_mix(mix, w, max_count_cap) =
  clip(sum_c(w[c] * mix[c]) / max_count_cap, 0, 1)
# mix[c] = segment buffer 안의 class c 개수
# max_count_cap = 20 → 단일 segment 주변 보호대상 20개 이상은 동일 1.0 처리

F_exposure_interface =
    0.55 * inv(norm(forest_asset_distance_m, [0, 2000]))
  + 0.45 * norm(forest_asset_interface_length_m, [0, 1000])
```

### SpreadToAssetSignal

```text
F_spread_wind =
    0.45 * wind_toward_asset_flag * norm(max(WSD, observed_wind_speed), [0, 20])
  + 0.25 * gust_toward_asset_flag * norm(observed_gust_speed, [0, 25])
  + 0.30 * norm(max(WSD, observed_wind_speed), [0, 20])

F_spread_terrain = lookup(forest_to_asset_bearing_class, {
  정면: 1.00,
  사면-가까움: 0.65,
  사면-먼: 0.35,
  외면: 0.00
})

F_spread_fuel =
    0.40 * lookup(forest_continuity_class, {연속:1.0, 부분단절:0.5, 단절:0.0})
  + 0.25 * inv(norm(disconnect_count, [0, 10]))
  + 0.35 * lookup(forest_density_class, {조밀:1.0, 보통:0.6, 성긴:0.3, 미입목:0.0})
```

`F_spread_terrain`은 DEM exclusion 때문에 slope/aspect/elevation을 포함하지 않는 축소 정의다.

### WateringActionabilitySignal

mock CSV의 raw 영문 enum을 그대로 lookup MAP key로 쓴다. derived flag(`forest_road_present`, `night_flag`)는 raw 또는 derived 단계에서 산출한다.

```text
firetruck_factor = 1.0 if firetruck_accessible else 0.2
turnaround_factor = 1.0 if turnaround_available else 0.3
narrow_penalty = 0.30 if narrow_road_flag else 0.0
forest_road_attr_score = norm(FRRD_FCLTW, [3, 7]) if forest_road_present else 0.0

F_action_vehicle = firetruck_factor * clip(
    0.40 * lookup(access_constraint_class, {accessible:1.0, limited_turnaround:0.5, restricted:0.15})
  + 0.25 * norm(road_width_m, [2.5, 6.5])
  + 0.20 * turnaround_factor
  + 0.15 * forest_road_attr_score
  - narrow_penalty,
  0, 1
)

usable_factor = lookup(usable_status, {usable:1.0, limited:0.5, unknown:0.3})
remote_bonus = 0.10 if 원격제어 else 0.0

F_action_water = clip(
  ( 0.50 * inv(norm(nearest_water_source_distance_m, [0, 1500]))
  + 0.30 * lookup(supply_capacity_class, {high:1.0, medium:0.6, low:0.3})
  + 0.20 * lookup(facility_type, {hydrant:1.0, emergency_fire_device:0.9, water_tower:0.85, water_tank:0.75})
  ) * usable_factor + remote_bonus,
  0, 1
)

F_action_barrier =
    0.40 * lookup(wetting_response_class, {high:1.0, medium:0.6, low:0.2})
  + 0.30 * lookup(surface_fuel_type, {
      roadside_fuel:1.0,
      leaf_litter:0.9,
      dry_grass:0.85,
      shrub:0.7,
      conifer_understory:0.65
    })
  + 0.30 * barrier_effectiveness_class_score

severity_factor = lookup(hazard_severity, {high:0.9, medium:0.6, low:0.3})
hazard_factors = []
if rockfall_risk_flag: hazard_factors.append(severity_factor)
if smoke_exposure_possible: hazard_factors.append(severity_factor)
if access_constraint_flag: hazard_factors.append(0.4)
if narrow_road_flag: hazard_factors.append(0.4)
wind_warning_score = lookup((WRN, LVL), {
  (없음, *): 0.0,
  (강풍, 주의보): 0.5,
  (강풍, 경보): 0.9
})

hazard_max = max(hazard_factors + [wind_warning_score])
night_penalty = 0.20 if (night_operation_flag or sun_event_after_sunset) else 0.0

F_action_safety = clip(1 - hazard_max - night_penalty, 0, 1)
```

`forest_road_present`이 false인 segment(예: 광주 임도 0건)는 `forest_road_attr_score = 0.0` 처리한다. `FRRD_FCLTW`가 null인 row도 동일하게 0.0으로 둔다.

`F_action_vehicle`, `F_action_water`, `F_action_barrier`, `F_action_safety`는 mock 영향이 커서 hard gate 자동 실행에 쓰지 않는다.

### TimeUrgencySignal

```text
# risk_grade_score_t는 §OfficialRiskSignal의 동명 helper와 동일하다.
# horizon t의 산림청 등급(d1..d4 forecast)을 5단계 lookup으로 점수화한다.
# t에 등급이 없고 risk_index만 있으면 risk_index_score(x)를 사용한다.

danger_t =
    0.40 * risk_grade_score_t
  + 0.20 * inv(norm(REH_t, [20, 90]))
  + 0.20 * norm(WSD_t, [0, 20])
  + 0.20 * norm(TMP_t, [0, 35])

F_time_window = max_t(danger_t) * imminence(hours_to_peak)

imminence(h) =
  1.00 if h < 3
  0.85 if h < 12
  0.65 if h < 24
  0.40 if h < 48
  0.20 otherwise

window_remaining_min = max(hours_to_peak * 60 - 20, 1)
ratio = expected_travel_time_min / window_remaining_min

F_time_lead = clip(ratio, 0, 1)
infeasible_dispatch_flag = (ratio > 1.0)
# ratio가 1에 가까울수록 dispatch 시점 압력 증가 → urgency 양의 방향
# ratio > 1이면 도달 불가 → State override(NotActionable/Deferred)에서 처리

F_time_duration = norm(expected_watering_duration_min, [30, 240])

F_time_rain =
  norm(expected_rainfall_mm, [0, 30])
  * norm(rain_probability, [0, 100])
  * clip(norm(rain_duration_hr, [0, 12]) + 0.3, 0, 1)
```

Signal 단계에서는 강수가 주수 필요성을 낮추므로 `inv(F_time_rain)`을 사용한다.

## Signal Formulas

```text
S_official =
    0.40 * F_official_level
  + 0.20 * F_official_trend
  + 0.40 * F_official_alert

S_exposure =
    0.40 * F_exposure_residential
  + 0.35 * F_exposure_critical
  + 0.25 * F_exposure_interface

S_spread =
    0.40 * F_spread_wind
  + 0.25 * F_spread_terrain
  + 0.35 * F_spread_fuel

S_action =
    0.30 * F_action_vehicle
  + 0.30 * F_action_water
  + 0.15 * F_action_barrier
  + 0.25 * F_action_safety

S_time =
    0.35 * F_time_window
  + 0.25 * F_time_lead
  + 0.20 * F_time_duration
  + 0.20 * inv(F_time_rain)

S_priority =
    0.20 * S_official
  + 0.25 * S_exposure
  + 0.20 * S_spread
  + 0.20 * S_action
  + 0.15 * S_time
```

전파 규칙:

```text
mock_input(S) = OR(feature.mock_input)
mock_input(S_priority) = OR(signal.mock_input)

# confidence는 weight × factor의 가중평균 후 ordinal 매핑
# (단순 min은 약한 보조 입력 하나가 Signal 전체를 low로 떨어뜨려 운영 부정확)
confidence_factor(S) = sum_j (w_feature_j * factor(confidence(F_j)))
confidence_factor(S_priority) = sum_i (w_signal_i * factor(confidence(S_i)))

confidence(S | S_priority) =
  high         if factor >= 0.95
  medium-high  if 0.88 <= factor < 0.95
  medium       if 0.75 <= factor < 0.88
  medium-low   if 0.60 <= factor < 0.75
  low          if factor < 0.60
```

`factor()`는 §Confidence Ordinal의 factor 값이다. `mock_input` flag와 별개로 운영 단계에서 추가 격하 트리거(예: 입력 source의 partial coverage 발견)가 있을 때 `confidence`를 한 단계 낮출 수 있다. 격하는 §Calibration에 기록한다.

## State Transition

| State | 기본 조건 |
|---|---|
| `GeneralManagement` | `S_priority < 0.20` |
| `EnhancedMonitoring` | `0.20 <= S_priority < 0.40` |
| `ReviewPreWatering` | `0.40 <= S_priority < 0.60` |
| `PriorityPreWatering` | `0.60 <= S_priority < 0.80` |
| `ImmediatePreWatering` | `S_priority >= 0.80` |

Override는 순서대로 적용한다. **hazard gate가 lifecycle보다 먼저** 적용되어야 한다(완료된 segment라도 안전·접근 문제가 있으면 재방문 자체가 차단되어야 함). lifecycle 안에서는 `Recheck` 트리거를 `Completed`보다 먼저 평가한다.

| 순위 | 조건 | State | 비고 |
|---|---|---|---|
| 1 | `F_action_safety.class = 작업 불가` | `NotActionable` | hazard gate (항상 우선) |
| 2 | `infeasible_dispatch_flag = true` 또는 `F_action_vehicle.class = 불가` | `Deferred` | 접근/도달 gate |
| 3 | `F_time_rain > 0.6` | `MonitorOnly` | 강수 우세 (rain dominant) |
| 4 | 이전 `Completed` 이후 새 high risk window 발생 또는 wetness recheck due | `Recheck` | lifecycle 재진입 |
| 5 | 이전 `Completed` 존재 + 재진입 트리거 없음 | `Completed` | lifecycle 종료 유지 |
| 6 | `F_official_alert.class = 경보` | 최소 `PriorityPreWatering` | alert 격상 |
| 7 | `F_official_alert.class = 주의보` and `S_exposure >= 0.5` | 최소 `ReviewPreWatering` | alert + exposure 격상 |
| 8 | `risk_grade = 매우높음` 또는 `risk_index_max >= 86` | 최소 `PriorityPreWatering` | 등급 단독 격상 (산림청 즉각 대응 기준) |
| 9 | `risk_grade = 높음` 또는 `risk_index_max >= 66` | 최소 `ReviewPreWatering` | 등급 단독 격상 (대형 산불 주의 기준) |

순위 4·5는 lifecycle 트랙에 한정한다. 이전 `Completed` 기록이 없는 fresh segment는 4·5를 건너뛰고 6~9와 default `S_priority` 임계로 결정한다. 순위 6·7(alert)과 8·9(grade)가 동시에 매치되면 더 높은 State를 채택한다.

## Decision Gate

| Decision | Trigger | mock-aware gate |
|---|---|---|
| `SelectPreWateringSegment` | State가 `ReviewPreWatering` 이상 | 항상 advisory list 출력 가능 |
| `SchedulePreWatering` | segment selected + `S_time` | `F_time_lead` 또는 `F_time_duration` low면 `advisory_only` |
| `AssignResourcePackage` | schedule 완료 + actionability 입력 | vehicle, water, duration 중 둘 이상 low면 `RequestManualReview` |
| `DeferOrMonitor` | `MonitorOnly`, `NotActionable`, `Deferred` | safety 또는 vehicle low면 자동 defer 금지 |
| `RequestManualReview` | mock dominant, exclude dependency, join/geocode failure | 항상 허용 |

EXCLUDE로 인한 manual review:

- critical infrastructure proximity가 결정 분기점일 가능성
- large fire risk name join 실패가 alert 분기점일 때
- public/vulnerable/station geocoding 실패가 결정 분기점일 때

## Action Mapping

| State | 기본 Action |
|---|---|
| `ImmediatePreWatering` | dispatch, use water source, wet surface fuel, record completion, schedule recheck |
| `PriorityPreWatering` | scheduled dispatch, use water source, wet surface fuel, record completion |
| `ReviewPreWatering` | notify local authority, schedule daily recheck |
| `EnhancedMonitoring` | schedule twice-daily recheck |
| `GeneralManagement` | no action |
| `MonitorOnly` | schedule recheck after rain end |
| `NotActionable` | notify unsafe, recheck after hazard clears |
| `Deferred` | notify access blocked, recheck after access restored |
| `Completed` | schedule recheck after risk window |
| `Recheck` | dispatch recheck or record field completion |

## Calibration

v0 weight와 threshold는 다음 순서로 보정한다.

1. 운영 시뮬레이션에서 `S_priority` 분포를 만들고 25/50/75/90 percentile boundary를 검토한다.
2. Wind, exposure, actionability weight A/B를 도메인 전문가가 비교한다.
3. confidence threshold가 너무 보수적이거나 공격적인지 평가한다.
4. Action sequence와 recipient/severity를 실제 운영 매뉴얼과 맞춘다.
5. 변경 시 이 문서의 weight, threshold, 근거를 함께 갱신한다.
