# `wildfire_schema.tql` TypeDB(TypeQL) 문법 설명

이 문서는 `schema/wildfire_schema.tql`를 기준으로, 현재 스키마에 사용된 TypeDB(TypeQL) 문법을 설명합니다.

---

## 1) 스키마 시작: `define`

TypeDB 스키마 파일은 보통 `define`으로 시작합니다.

```typeql
define
```

- 의미: 지금부터 **타입(속성/엔티티/관계)** 정의를 선언한다는 뜻입니다.
- 한글로 풀어쓰면: "이 아래부터 데이터베이스의 설계도(타입 규칙)를 정의하겠다"는 시작 선언입니다.

---

## 2) 속성 타입 정의: `attribute <name>, value <type>;`

예시:

```typeql
attribute name, value string;
attribute recorded-at, value datetime;
attribute risk-index-value, value double;
attribute hotspot-count, value integer;
```

한글 설명:
- `attribute name, value string;`는 "이름" 속성을 문자열 타입으로 정의한다는 뜻입니다.
- `attribute recorded-at, value datetime;`는 "기록 시각" 속성을 날짜+시간 타입으로 정의한다는 뜻입니다.
- `attribute risk-index-value, value double;`는 "위험지수 값"을 실수 타입으로 정의한다는 뜻입니다.
- `attribute hotspot-count, value integer;`는 "핫스팟 개수"를 정수 타입으로 정의한다는 뜻입니다.

- `attribute <name>`: 속성 타입 선언
- `value string|datetime|double|integer`: 속성 값의 데이터 타입
- 본 스키마에서는 관측값/지표/식별자 필드를 속성으로 정의했습니다.

---

## 3) 엔티티 타입 정의: `entity`

예시:

```typeql
entity forest-zone,
  owns name @key,
  owns slope-class,
  owns wind-exposure,
  owns access-intensity;
```

한글 설명:
- `forest-zone`은 **산림 구역 엔티티 타입**입니다.
- `owns name @key`는 산림 구역이 이름 속성을 가지며, 그 이름을 **고유 식별 키**로 사용한다는 뜻입니다.
- `owns slope-class`는 산림 구역이 **경사 등급** 속성을 소유한다는 뜻입니다.
- `owns wind-exposure`는 산림 구역이 **바람 노출도** 속성을 소유한다는 뜻입니다.
- `owns access-intensity`는 산림 구역이 **접근/이용 강도** 속성을 소유한다는 뜻입니다.

핵심 문법:
- `entity <name>`: 엔티티 타입 선언
- `owns <attribute-type>`: 이 엔티티가 해당 속성을 가질 수 있음
- `@key`: 고유 식별 속성(중복 방지 목적)

스키마 패턴:
- 공간: `administrative-region`, `forest-zone`, `trail`, `settlement`, `critical-facility`
- 상황/판단: `fire-incident`, `risk-assessment`, `control-decision` 등
- 자원/조직: `organization`, `crew`, `engine`, `aircraft`

---

## 4) 관계 타입 정의: `relation` + `relates`

예시:

```typeql
relation zone-located-in-region,
  relates zone,
  relates region;
```

한글 설명:
- `zone-located-in-region`은 "산림 구역이 특정 행정구역에 속한다"는 관계 타입입니다.
- `relates zone`은 이 관계에 "구역 역할" 참여자가 들어온다는 뜻입니다.
- `relates region`은 이 관계에 "행정구역 역할" 참여자가 들어온다는 뜻입니다.

- `relation <name>`: 관계 타입 선언
- `relates <role>`: 관계에 참여하는 역할(role) 선언

즉, 위 예시는 "`zone` 역할"과 "`region` 역할"을 가진 관계 타입입니다.

---

## 5) 역할 참여 선언: `plays`

관계를 정의한 뒤, 어떤 엔티티가 어떤 역할을 수행할지 연결합니다.

예시:

```typeql
forest-zone plays zone-located-in-region:zone;
administrative-region plays zone-located-in-region:region;
```

한글 설명:
- `forest-zone plays zone-located-in-region:zone;`는 산림 구역 엔티티가 `zone` 역할을 맡을 수 있다는 뜻입니다.
- `administrative-region plays zone-located-in-region:region;`는 행정구역 엔티티가 `region` 역할을 맡을 수 있다는 뜻입니다.
- 즉, "어떤 타입이 어떤 관계의 어떤 자리(역할)에 들어갈 수 있는지"를 문법으로 고정하는 선언입니다.

- `<entity-type> plays <relation-type>:<role>`
- 의미: 해당 엔티티 타입 인스턴스가 그 관계의 특정 role 자리에 들어갈 수 있음

이 `relates` + `plays` 조합이 TypeDB 관계 모델링의 핵심입니다.

---

## 6) 현재 스키마의 구조적 해석

`wildfire_schema.tql`은 아래 계층으로 구성됩니다.

1. **속성 사전**
   - `name`, `recorded-at`, `risk-level`, `contained-percent` 등
2. **도메인 엔티티**
   - 산불 사건, 구역, 자원, 조직, 의사결정 객체
3. **관계 타입**
   - 사건-구역, 지휘-조직, 출동-자원, 대피-정착지 등
4. **역할 제약**
   - 엔티티별 `plays` 선언으로 관계 참여 가능 역할 제한

---

## 7) 데이터 입력 시 문법 연결(왜 중요한가)

스키마의 `relates`/`plays`는 이후 `insert` 문법과 1:1 대응됩니다.

예:

```typeql
(incident: $incident-1, zone: $zone-bravo) isa incident-occurred-in-zone;
```

한글 설명:
- `$incident-1` 변수는 `incident` 역할에, `$zone-bravo` 변수는 `zone` 역할에 배치됩니다.
- 그리고 이 두 개를 묶어 `incident-occurred-in-zone`(사건 발생 구역 관계) 인스턴스를 만든다는 뜻입니다.
- 즉, "산불 사건 1은 브라보 구역에서 발생했다"라는 사실을 관계형으로 입력한 문장입니다.

- `incident`, `zone`은 스키마의 role 이름과 반드시 일치해야 합니다.
- role 이름이 다르면 데이터 적재 오류가 납니다.

---

## 8) 자주 헷갈리는 포인트

- **`entity` vs `relation`**
  - 객체 자체면 `entity`
  - 두 객체 이상 연결이면 `relation`

- **`owns` vs `plays`**
  - `owns`: 엔티티가 속성을 가짐
  - `plays`: 엔티티가 관계의 역할에 참여함

- **`@key` 사용**
  - `name @key`는 식별용으로 유용하지만, 실제 운영에서는 충돌 가능성이 있는 이름 대신 코드 기반 키를 병행하는 것이 안전합니다.

---

## 9) 스키마 확장 가이드 (이 프로젝트 기준)

새 요구사항이 생기면 보통 다음 순서로 확장합니다.

1. 속성 추가 (`attribute`)
2. 엔티티에 `owns` 연결
3. 필요한 관계 타입 추가 (`relation`, `relates`)
4. 참여 엔티티에 `plays` 추가
5. 데이터/쿼리 파일(`data/*.tql`, `queries/*.tql`) 동시 업데이트

---

## 10) 참고

- 본 문서는 `schema/wildfire_schema.tql`의 현재 상태를 기준으로 작성되었습니다.
- 공식 문서:
  - [TypeDB Console](https://typedb.com/docs/tools/console/)
  - [TypeDB Install CE](https://typedb.com/docs/home/install/ce/)

---

## 11) 영어 이름 한글 번역 설명

아래는 현재 스키마의 주요 영어 식별자에 대한 한글 의미입니다.

### 엔티티 타입 번역

- `administrative-region`: 행정구역
- `forest-zone`: 산림 구역
- `trail`: 등산로/탐방로
- `settlement`: 정착지(마을)
- `critical-facility`: 중요 시설
- `weather-observation`: 기상 관측
- `fuel-moisture-measurement`: 연료 수분 측정
- `fire-incident`: 산불 사건
- `risk-assessment`: 위험도 평가
- `control-decision`: 통제 의사결정
- `dispatch-decision`: 출동 의사결정
- `incident-command`: 현장 지휘
- `resource-request`: 자원 요청
- `hazard-zone`: 위험 구역
- `retreat-plan`: 철수 계획
- `control-line`: 통제선(방어선/철수선)
- `operational-period`: 작전 시간대
- `tactic-switch-decision`: 전술 전환 의사결정
- `evacuation-decision`: 대피 의사결정
- `containment-status`: 진화/포위 상태
- `patrol-plan`: 순찰 계획
- `prevention-action`: 예방 조치
- `post-incident-report`: 사후 보고서
- `policy-recommendation`: 정책 권고
- `organization`: 기관/조직
- `crew`: 대응 인력 팀
- `engine`: 소방차(엔진 유닛)
- `aircraft`: 항공 진화 자원(헬기 등)

### 속성 타입 번역

- `name`: 이름
- `code`: 코드
- `recorded-at`: 기록 시각
- `temperature-c`: 기온(섭씨)
- `humidity-percent`: 습도(%)
- `wind-speed-ms`: 풍속(m/s)
- `fuel-moisture-percent`: 연료 수분율(%)
- `slope-class`: 경사 등급
- `wind-exposure`: 바람 노출도
- `risk-index-value`: 위험지수 값
- `risk-level`: 위험 등급
- `action-type`: 조치 유형
- `start-time`: 시작 시각
- `end-time`: 종료 시각
- `detection-time`: 탐지 시각
- `estimated-spread-rate`: 추정 확산 속도
- `availability-status`: 가용 상태
- `hazard-type`: 위험 유형
- `tactic-mode`: 전술 모드
- `visibility-level`: 가시성 수준
- `fatigue-level`: 피로 수준
- `alert-level`: 경보 수준
- `contained-percent`: 진화/포위 비율(%)
- `hotspot-count`: 잔불 지점 수
- `patrol-cycle-hours`: 순찰 주기(시간)
- `access-intensity`: 접근/이용 강도
- `cause-type`: 원인 유형
- `burned-area-ha`: 소실 면적(ha)
- `property-loss-krw`: 재산 피해액(원)
- `injury-count`: 부상자 수
- `resource-kind`: 자원 종류
- `resource-quantity`: 자원 수량

### 관계 타입 번역(대표)

- `zone-located-in-region`: 구역-행정구역 소속 관계
- `trail-located-in-zone`: 등산로-구역 소속 관계
- `weather-observed-in-zone`: 구역 기상 관측 관계
- `risk-assessment-for-zone`: 구역 위험도 평가 관계
- `incident-occurred-in-zone`: 사건 발생 구역 관계
- `dispatch-for-incident`: 사건별 출동 결정 관계
- `incident-command-for-incident`: 사건별 지휘 관계
- `evacuation-decision-for-incident`: 사건별 대피 결정 관계
- `containment-status-for-incident`: 사건별 진화 상태 관계
- `post-incident-report-for-incident`: 사건별 사후 보고 관계

필드명을 한글로 실제 변경하기보다는, **스키마 식별자는 영어로 유지**하고 문서/주석/대시보드 레이어에서 한글 라벨을 매핑하는 방식이 운영에 유리합니다.

---

## 12) `rules.tql` 설명 (TypeDB 3.x 호환 기준)

현재 환경(TypeDB 3.x)에서는 예전의 `rule ... when ... then ...` 문법이 `define` 스키마 구문으로 해석되지 않습니다.

즉, 아래 형태(2.x 스타일)는 현재 콘솔 `source`에서 문법 오류가 날 수 있습니다.

```typeql
rule some-rule:
when { ... }
then { ... };
```

한글 설명:
- 과거 버전에서는 "조건이 참이면 결과 사실을 추론"하는 선언형 규칙으로 사용했습니다.
- 현재 프로젝트 환경에서는 이 문법을 스키마에 직접 넣어 실행하지 않습니다.

현재 `schema/rules.tql` 파일은 다음 목적의 안내 파일입니다.
- 왜 규칙 파일을 실행하지 않는지 기록
- 추론 로직을 어디서 구현할지 기준 제시

권장 구현 위치:
1. 애플리케이션 레이어(서비스 코드)에서 조건 판단 후 의사결정 엔티티/관계 생성
2. TypeDB 3.x 함수/쿼리 파이프라인 설계로 대체

실무 권장:
- 스키마(`wildfire_schema.tql`)는 타입/관계 정의에 집중
- 추론(정책 로직)은 버전 호환성 영향이 적은 애플리케이션 로직으로 분리

---

## 13) `functions.tql` 문법 설명 (3.x 추론 대체)

`schema/functions.tql`은 3.x에서 규칙을 대체하기 위해 사용한 함수 정의 파일입니다.

기본 문법:

```typeql
define
fun function_name($arg: type) -> { return-type }:
  match
    ...
  return { $var };
```

### 함수 1: `high_risk_zones`

원문:

```typeql
fun high_risk_zones() -> { forest-zone }:
  match
    $zone isa forest-zone;
    $assessment isa risk-assessment, has risk-level "high";
    (assessment: $assessment, zone: $zone) isa risk-assessment-for-zone;
  return { $zone };
```

한글 설명:
- 위험도 평가가 `high`인 산림 구역들만 스트림으로 반환하는 함수입니다.
- 과거 규칙의 "고위험 구역 감지 조건"을 함수로 분리한 것입니다.

### 함수 2: `watch_targets`

원문:

```typeql
fun watch_targets() -> { fire-incident, settlement }:
  match
    $incident isa fire-incident;
    $zone isa forest-zone;
    (incident: $incident, zone: $zone) isa incident-occurred-in-zone;
    $settlement isa settlement;
    (settlement-role: $settlement, zone: $zone) isa settlement-adjacent-to-zone;
  return { $incident, $settlement };
```

한글 설명:
- 산불 사건과 해당 사건 구역에 인접한 정착지 쌍을 반환하는 함수입니다.
- 과거 규칙의 "인접 정착지 경보 대상 탐지" 조건을 함수화한 것입니다.

### 함수 호출 기반 추론 파이프라인

함수는 결과를 계산할 뿐, 자동으로 엔티티를 만들지 않습니다.  
의사결정 객체 생성은 별도 write 파이프라인에서 수행합니다.

예시:

```typeql
match
  let $zone in high_risk_zones();
insert
  $decision isa control-decision, has action-type "access-control-needed";
  (decision: $decision, zone: $zone) isa control-decision-for-zone;
```

즉, 3.x에서는 `rule`의 암묵 추론 대신 **함수(조건 계산) + insert 파이프라인(결과 반영)** 구조로 구현합니다.

현재 프로젝트 함수 선별 적용:
- 공통 필터(고위험 구역, 인접 정착지, 가용 자원)는 함수화
- 단발성 조회/리포팅은 `queries/q01~q10`에서 직접 `match/select`
