# 산불 예방·진압 온톨로지 TypeDB 실행 가이드 (Console 기준)

이 문서는 TypeDB **Console 명령 체계(3.x)** 를 기준으로 작성되었습니다.  
`typedb --help`, `typedb version` 출력이 환경에 따라 다를 수 있으므로, **실행 가능 여부는 `typedb server` / `typedb console` 동작으로 판단**합니다.

참고 문서:
- [TypeDB CE 설치](https://typedb.com/docs/home/install/ce/)
- [TypeDB Console](https://typedb.com/docs/tools/console/)

---

## 의사결정 질문(CQ)

초기 설계에서 정의한 의사결정 질문은 아래 10개입니다.

- `CQ01` 오늘 특정 산림구역의 산불 발생 위험도를 상·중·하로 어떻게 분류할 것인가?
- `CQ02` 입산 통제와 등산로 폐쇄를 발령해야 하는가, 발령 범위와 기간은 얼마인가?
- `CQ03` 신고 접수 직후 최초 출동 규모(인력·장비)는 어느 수준으로 배치해야 하는가?
- `CQ04` 산림청·소방·지자체 간 지휘 주도권과 자원 조정 방식은 무엇인가?
- `CQ05` 진화 불가 위험 구역에서 철수선과 방어선을 어디에 설정해야 하는가?
- `CQ06` 주간 진화에서 야간 방어 중심으로 전환할 시점은 언제인가?
- `CQ07` 인접 마을과 핵심 시설에 선제 대피 경보를 발령해야 하는가?
- `CQ08` 주불 진압 후 상황 종료와 잔불 감시 전환 기준은 무엇인가?
- `CQ09` 재발 방지를 위한 연료 정리와 감시 강화 자원은 어디에 우선 배치해야 하는가?
- `CQ10` 사후 원인·피해 데이터를 어떻게 구조화해 다음 예방 정책에 반영할 것인가?

질문 원본은 `ontology/competency_questions.json`에서 관리합니다.

### CQ를 주술목(S-P-O) 구조로 해석하는 방법

의사결정 질문은 자연어 그대로 다루기보다, 아래처럼 **주어(Subject) - 술어(Predicate) - 목적어(Object)** 단위로 쪼개면
TypeDB 질의(`match`)와 결과 문장(`select` 기반 보고)으로 연결하기 쉽습니다.

- **주어(S)**: 판단 대상 엔티티(예: `forest-zone`, `fire-incident`, `settlement`)
- **술어(P)**: 관계/상태/행위(예: `has risk-level`, `requires evacuation`, `assigned dispatch-scale`)
- **목적어(O)**: 술어가 가리키는 값 또는 연결 대상(예: `"high"`, `evacuation-decision`, `initial-dispatch-level`)

예시 해석:
- `CQ01` "특정 산림구역의 위험도를 어떻게 분류할 것인가?"
  - S: `forest-zone`
  - P: `has risk-level`
  - O: `"high" | "medium" | "low"`
- `CQ07` "인접 마을에 선제 대피 경보를 발령해야 하는가?"
  - S: `settlement`(incident 인접)
  - P: `is target of`
  - O: `evacuation-decision`

실무 적용 팁:
- CQ 1개를 **핵심 SPO 1~3개**로 먼저 정리한 뒤 쿼리를 작성하면, 필수 출력 필드(`select`)를 빠뜨리지 않습니다.
- 술어(P)는 가능하면 스키마의 관계 타입/속성명과 동일한 용어를 사용해 CQ-스키마-쿼리 간 추적성을 유지하세요.

---

## 1) 준비물

- 프로젝트 루트: `~/projects/wildfire-ontology` (클론한 경로로 대체)
- 파일:
  - `schema/wildfire_schema.tql`
  - `schema/functions.tql`
  - `data/mock_insert.tql`
  - `queries/q01_risk_classification.tql` ~ `queries/q10_post_incident_policy_feedback.tql`
  - `queries/inference/i01_insert_access_control_by_function.tql`
  - `queries/inference/i02_insert_watch_evacuation_by_function.tql`
  - `queries/inference/i03_insert_dispatch_by_ready_resources_function.tql`
  - `queries/inference/i04_insert_policy_recommendation_by_function.tql`
  - `queries/inference/v01_verify_access_control_inference.tql`
  - `queries/inference/v02_verify_watch_evacuation_inference.tql`
  - `queries/inference/v03_verify_dispatch_inference.tql`
  - `queries/inference/v04_verify_policy_recommendation_inference.tql`

---

## 2) TypeDB 설치

### Windows

```powershell
iwr https://typedb.com/install.ps1 -useb | iex
```

### macOS

설치 스크립트:

```bash
curl -sSL https://typedb.com/install.sh | sh && export PATH="$HOME/.typedb:$PATH"
```

또는 Homebrew:

```bash
brew install typedb/tap/typedb
```

설치 확인(권장):

```bash
typedb console --version
```

`--version`이 실패해도 `typedb server`, `typedb console`이 실행되면 진행 가능합니다.

---

## 3) 서버 실행

별도 터미널에서 서버를 먼저 켭니다.

```bash
typedb server
```

서버는 포그라운드로 실행됩니다. 검증 작업은 다른 터미널에서 진행하세요.

---

## 4) Console 접속

프로젝트 루트로 이동 후 Console 접속:

### Windows

```powershell
cd <프로젝트_루트>
typedb console --address=localhost:1729 --username=admin --tls-disabled
```

### macOS

```bash
cd <프로젝트_루트>
typedb console --address=localhost:1729 --username=admin --tls-disabled
```

기본 계정은 `admin / password` 입니다(최초 환경 기준).

---

## 5) DB 재생성 (Server level REPL)

Console 프롬프트 `>>` 에서 실행:

```text
database delete wildfire
database create wildfire
database list
```

---

## 6) 스키마 적용 (Transaction level REPL)

Console에서 아래 순서로 실행:

### Windows 경로

```text
transaction schema wildfire
source .\schema\wildfire_schema.tql
commit

transaction schema wildfire
source .\schema\functions.tql
commit
```

### macOS/Linux 경로

```text
transaction schema wildfire
source ./schema/wildfire_schema.tql
commit

transaction schema wildfire
source ./schema/functions.tql
commit
```

### 스키마/함수 적용 확인

`commit` 이후 아래 읽기 검증을 실행하면 스키마와 함수 적용 여부를 빠르게 확인할 수 있습니다.

#### 스키마(타입) 확인

```text
transaction read wildfire
match
  $z isa forest-zone, has name $zone-name;
select $zone-name;
close
```

- 결과가 1건 이상이면 `forest-zone` 타입/속성 정의가 정상 반영된 상태입니다.

#### 함수 확인

```text
transaction read wildfire
match
  let $zone in high_risk_zones();
  $zone has name $zone-name;
select $zone-name;
close
```

- 에러 없이 결과가 나오면 `schema/functions.tql`의 함수가 정상 로드된 상태입니다.
- 결과가 0건이면 함수 미적용이 아니라 데이터 조건(예: `risk-level "높음"`) 불일치일 수 있으니 데이터를 함께 점검하세요.

참고: 현재 환경(TypeDB 3.x)에서는 `rule ... when ... then ...` 구문이 `define` 스키마 문법으로 수용되지 않습니다.  
따라서 규칙 추론은 애플리케이션 레이어 또는 3.x 함수/쿼리 파이프라인으로 구현해야 합니다(본 프로젝트는 함수 방식 적용).

---

## 7) 데이터 적재

Console에서 실행:

### Windows 경로

```text
transaction write wildfire
source .\data\mock_insert.tql
commit
```

### macOS/Linux 경로

```text
transaction write wildfire
source ./data/mock_insert.tql
commit
```

### `mock_insert` 실제 적재 확인

적재 직후 아래 확인 쿼리를 실행해 실제 데이터 반영 여부를 점검하세요.

```text
transaction read wildfire
match $zone isa forest-zone; select $zone;
match $incident isa fire-incident; select $incident;
match $risk isa risk-assessment; select $risk;
close
```

- `forest-zone`은 최소 3건, `fire-incident`는 최소 2건, `risk-assessment`는 최소 3건이 조회되면 정상 적재로 판단할 수 있습니다.

### 목업 데이터 설명

`data/mock_insert.tql`은 의사결정 시뮬레이션을 위한 최소 시나리오 데이터입니다.

- **공간/행정 기본축**: `administrative-region`, `forest-zone`, `trail`, `settlement`, `critical-facility`
- **관측/위험**: 기상 관측(`weather-observation`), 연료 수분(`fuel-moisture-measurement`), 위험평가(`risk-assessment`)
- **사건/대응**: 산불 사건(`fire-incident`), 출동(`dispatch-decision`), 지휘(`incident-command`), 자원요청(`resource-request`)
- **전술/안전**: 위험구역(`hazard-zone`), 철수계획(`retreat-plan`), 전술전환(`tactic-switch-decision`), 대피결정(`evacuation-decision`)
- **종결/사후**: 진화상태(`containment-status`), 순찰계획(`patrol-plan`), 예방조치(`prevention-action`), 사후보고(`post-incident-report`)

시나리오 의도:
- 저위험/고위험 구역을 함께 넣어 CQ01, CQ02, CQ09 판단이 가능하도록 구성
- 진행 중 사건(incident) + 인접 정착지를 넣어 CQ03~CQ08 판단이 가능하도록 구성
- 사후 보고/권고 데이터를 넣어 CQ10 정책 피드백 검증이 가능하도록 구성

주의:
- 목업 데이터는 데모용이므로 실제 운영 데이터 모델(코드 체계, 시간 정합성, 공간 정밀도)과는 차이가 있을 수 있습니다.
- inference insert 쿼리를 여러 번 실행하면 의사결정 인스턴스가 중복될 수 있으니 운영 전 멱등 조건을 추가하세요.

---

## 8) q01 ~ q10 검증 실행

`source`는 Transaction level에서 사용합니다. 읽기 트랜잭션에서 순서대로 실행:

### Windows 경로

```text
transaction read wildfire
source .\queries\q01_risk_classification.tql
source .\queries\q02_access_control_decision.tql
source .\queries\q03_initial_dispatch_scale.tql
source .\queries\q04_command_and_coordination.tql
source .\queries\q05_retreat_and_defense_line.tql
source .\queries\q06_tactic_switch_timing.tql
source .\queries\q07_preemptive_evacuation.tql
source .\queries\q08_termination_and_patrol.tql
source .\queries\q09_prevention_priority.tql
source .\queries\q10_post_incident_policy_feedback.tql
close
```

### macOS/Linux 경로

```text
transaction read wildfire
source ./queries/q01_risk_classification.tql
source ./queries/q02_access_control_decision.tql
source ./queries/q03_initial_dispatch_scale.tql
source ./queries/q04_command_and_coordination.tql
source ./queries/q05_retreat_and_defense_line.tql
source ./queries/q06_tactic_switch_timing.tql
source ./queries/q07_preemptive_evacuation.tql
source ./queries/q08_termination_and_patrol.tql
source ./queries/q09_prevention_priority.tql
source ./queries/q10_post_incident_policy_feedback.tql
close
```

---

## 9) 함수 기반 추론 실행 (3.x 대체안)

규칙(rule) 대신 함수 + write 파이프라인으로 의사결정을 생성합니다.

### 9-1) 추론 결과 생성

### Windows 경로

```text
transaction write wildfire
source .\queries\inference\i01_insert_access_control_by_function.tql
source .\queries\inference\i02_insert_watch_evacuation_by_function.tql
source .\queries\inference\i03_insert_dispatch_by_ready_resources_function.tql
source .\queries\inference\i04_insert_policy_recommendation_by_function.tql
commit
```

### macOS/Linux 경로

```text
transaction write wildfire
source ./queries/inference/i01_insert_access_control_by_function.tql
source ./queries/inference/i02_insert_watch_evacuation_by_function.tql
source ./queries/inference/i03_insert_dispatch_by_ready_resources_function.tql
source ./queries/inference/i04_insert_policy_recommendation_by_function.tql
commit
```

### 9-2) 추론 결과 검증

### Windows 경로

```text
transaction read wildfire
source .\queries\inference\v01_verify_access_control_inference.tql
source .\queries\inference\v02_verify_watch_evacuation_inference.tql
source .\queries\inference\v03_verify_dispatch_inference.tql
source .\queries\inference\v04_verify_policy_recommendation_inference.tql
close
```

### macOS/Linux 경로

```text
transaction read wildfire
source ./queries/inference/v01_verify_access_control_inference.tql
source ./queries/inference/v02_verify_watch_evacuation_inference.tql
source ./queries/inference/v03_verify_dispatch_inference.tql
source ./queries/inference/v04_verify_policy_recommendation_inference.tql
close
```

### 9-3) 출입통제 필요 구역 추론 과정(예시)

아래 흐름으로 `출입통제-필요` 의사결정이 생성됩니다.

1. **고위험 구역 선별**  
   - `high_risk_zones()` 함수가 `risk-level = "높음"`인 평가와 연결된 `forest-zone`을 반환
2. **의사결정 인스턴스 생성**  
   - `i01_insert_access_control_by_function.tql`에서 반환된 구역마다  
     `control-decision (action-type: "출입통제-필요")`를 insert
3. **검증 쿼리로 결과 확인**  
   - `v01_verify_access_control_inference.tql`에서 최종 대상 구역명(`$zone-name`) 조회

핵심 쿼리(3.x 문법):

```typeql
// 1) 함수: 고위험 구역 선별
fun high_risk_zones() -> { forest-zone }:
  match
    $zone isa forest-zone;
    $assessment isa risk-assessment, has risk-level "높음";
    (assessment: $assessment, zone: $zone) isa risk-assessment-for-zone;
  return { $zone };
```

```typeql
// 2) 추론 결과 생성
match
  let $zone in high_risk_zones();
insert
  $decision isa control-decision, has action-type "출입통제-필요";
  (decision: $decision, zone: $zone) isa control-decision-for-zone;
```

```typeql
// 3) 추론 결과 검증
match
  $decision isa control-decision, has action-type "출입통제-필요";
  $zone isa forest-zone, has name $zone-name;
  (decision: $decision, zone: $zone) isa control-decision-for-zone;
select $zone-name;
```

### 결과 행이 콘솔에 안 보일 때

`source` 실행은 환경에 따라 `Finished executing 1 queries.` 같은 실행 로그만 보이고,
실제 결과 행(row)이 생략될 수 있습니다. 결과 값을 눈으로 확인하려면 `read` 트랜잭션에서
검증 쿼리를 직접 붙여 실행하세요.

예시 1) 출입 통제 결정 확인:

```text
transaction read wildfire
match
  $decision isa control-decision, has action-type "출입통제-필요";
  $zone isa forest-zone, has name $zone-name;
  (decision: $decision, zone: $zone) isa control-decision-for-zone;
select $zone-name;
close
```

예시 2) 선제 대피 결정(정착지) 확인:

```text
transaction read wildfire
match
  $decision isa evacuation-decision;
  $settlement isa settlement, has name $settlement-name;
  (decision: $decision, settlement-role: $settlement) isa evacuation-targets-settlement;
select $settlement-name;
close
```

예시 3) 최초 출동 자원(대응반) 확인:

```text
transaction read wildfire
match
  $dispatch isa dispatch-decision;
  $crew isa crew, has name $crew-name;
  (dispatch: $dispatch, assigned-crew: $crew) isa dispatch-assigns-crew;
select $crew-name;
close
```

예시 4) 사후 정책 권고 연결 확인:

```text
transaction read wildfire
match
  $recommendation isa policy-recommendation;
  $report isa post-incident-report, has cause-type $cause-type;
  (recommendation: $recommendation, report: $report) isa policy-recommendation-derived-from-report;
select $cause-type;
close
```

예상 출력 형태(예시 1):

```text
Finished read query validation and compilation...
Streaming rows...
   ----------------
    $zone-name | isa name "산림구역-브라보"
   ----------------
    $zone-name | isa name "산림구역-찰리"
   ----------------
Finished. Total answers: 2
```

주의:
- 위 추론 insert 쿼리는 재실행 시 중복 의사결정 인스턴스를 만들 수 있습니다.
- 운영에서는 중복 방지 키/검증 조건을 추가하거나, 애플리케이션 레이어에서 멱등 처리하세요.

### 함수 선별 적용 기준 (재사용성/복잡도 기반)

이 프로젝트는 CQ01~CQ10을 전부 함수화하지 않고, 아래 기준으로 선별 적용합니다.

- **함수로 승격**: 여러 CQ에서 반복되는 필터/타깃 추출 로직
  - `high_risk_zones()` (CQ01/CQ02/CQ09)
  - `watch_targets()` (CQ07)
  - `ready_crews()`, `ready_engines()`, `ready_aircraft()` (CQ03)
  - `incidents_requiring_patrol()` (CQ08)
  - `incidents_with_post_report()` (CQ10)
- **쿼리 유지**: 단발성 리포팅/조회 성격이 강한 질의(q01~q10)
- **애플리케이션 레이어**: 정책 임계값, 우선순위 스코어링, 중복 방지(멱등) 등 운영 로직

---

## 10) 자주 나는 오류와 해결

- `Invalid argument: database`  
  - 원인: 콘솔 밖에서 `typedb database ...` 실행
  - 해결: `typedb console` 진입 후 `database create wildfire`

- `typedb --help` / `typedb version` 이상
  - 원인: 배포본/래퍼 차이
  - 해결: `typedb server`, `typedb console` 실행 가능하면 계속 진행

- `source` 실패
  - 원인: Transaction level이 아님 / 경로 구분자 불일치
  - 해결: `transaction schema|write|read wildfire` 후 `source` 실행

- 쿼리 결과 0건
  - `data/mock_insert.tql` 적재 성공 여부 확인
  - `ontology/iteration_loop.json` 절차대로 데이터/스키마/쿼리 역추적

---

## 11) 실행 순서 요약

`install -> typedb server -> typedb console -> database create -> transaction schema + source(schema/functions) -> transaction write + source(data) -> transaction read + source(q01~q10) -> transaction write + source(inference i01~i04) -> transaction read + source(inference v01~v04)`

---

## 12) q01~q10 쿼리 문법 해설 및 결과 대응

### 12-1) 기본 문법

현재 `queries/q01~q10`은 공통적으로 아래 구조를 사용합니다.

```typeql
match
  ...조건 패턴...
select ...출력 변수...;
```

- `match`: 조건을 만족하는 엔티티/관계/속성 패턴을 탐색
- `isa`: 인스턴스의 타입 제약 (예: `$incident isa fire-incident`)
- `has`: 속성 제약/추출 (예: `$incident has name $incident-name`)
- `(role: $a, role2: $b) isa relation`: 관계 조인 패턴
- `select`: 의사결정에 필요한 출력 변수만 반환

### 12-2) 결과 해석 기준

- **실행 메시지 `Finished executing 1 queries.`**
  - 쿼리 문법이 실행되었음을 의미
  - 결과 행 수/값 품질까지 보장하지는 않음

- **결과 1건 이상**
  - 질문에 대한 근거 데이터 존재
  - CQ 판단 문장으로 변환 가능

- **결과 0건**
  - 데이터 누락, 관계 연결 누락, 조건 과도함 가능성
  - 타입 -> 관계 -> 속성 조건 순으로 역추적 점검

- **필수 필드 누락**
  - `select` 항목 부족 또는 데이터 `has` 누락 가능성
  - 질문별 필수 필드 목록 기준으로 보강 필요

### 12-3) 값 품질(상식 범위) 점검

아래 항목은 쿼리 성공과 별개로 품질 검증이 필요합니다.

- `humidity-percent`: 0~100
- `contained-percent`: 0~100
- `hotspot-count`: 0 이상
- `patrol-cycle-hours`: 1 이상
- `wind-speed-ms`: 0 이상
- `burned-area-ha`: 0 이상
- `injury-count`: 0 이상
- 시간값: `start-time <= end-time`

이상치가 발견되면:
1. `data/mock_insert.tql` 정정
2. 입력 파이프라인 검증 로직 보강
3. 운영 레이어에서 멱등/품질 가드 적용

### 12-4) CQ별 검증 체크리스트

각 `q01~q10` 실행 후 아래를 기록하면 온톨로지 답변 가능 여부를 체계적으로 확인할 수 있습니다.

- `row_count`: 0건 여부
- `required_fields_ok`: 필수 출력 필드 충족 여부
- `range_check_ok`: 값 범위 정상 여부
- `decision_sentence_ready`: 결과를 실제 의사결정 문장으로 변환 가능 여부
- `status`: `PASS` / `PARTIAL` / `FAIL`

### 12-5) 자동 점검 쿼리(`queries/validation`)

아래 검증 쿼리는 이상치/누락만 반환합니다.

- 결과 **0건**: PASS
- 결과 **1건 이상**: 데이터 보정 필요

실행 예시(Windows):

```text
transaction read wildfire
source .\queries\validation\v01_missing_zone_name.tql
source .\queries\validation\v02_missing_incident_name.tql
source .\queries\validation\v03_missing_risk_fields.tql
source .\queries\validation\v04_invalid_humidity_range.tql
source .\queries\validation\v05_invalid_contained_percent.tql
source .\queries\validation\v06_negative_hotspot_count.tql
source .\queries\validation\v07_invalid_patrol_cycle_hours.tql
source .\queries\validation\v08_negative_wind_speed.tql
source .\queries\validation\v09_negative_damage_values.tql
source .\queries\validation\v10_invalid_time_window_control_decision.tql
close
```
