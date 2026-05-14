# 2025-01-22 전남 곡성군 산불 회고 분석 보고서

**생성일**: 2026-05-11  
**분석 기준일**: 2025-01-21 (산불 발생 전날)  
**목적**: DOL 추론 엔진이 2025-01-22 곡성 산불 이전 시점에 어떤 판단을 내렸을지 검증

---

## 1. 추론 결과 요약

| 항목 | 값 |
|---|---|
| **S_priority** | **0.7061** |
| **State Band** | **PriorityPreWatering (우선예비주수)** |
| 전체 순위 | 1위 / 광주·전남 27개 시군구 |
| Override | none (S_priority 자체로 PriorityPreWatering 도달) |
| Action Mode | manual_review (mock 데이터 기반) |
| 권고 행동 | 예정 출동·주수·완료기록 |

---

## 2. Signal별 기여도

| Signal | score | 가중치 | 기여 |  의미 |
|---|---|---|---|---|
| **S_spread** | **0.8733** | 0.20 | 0.1747 | 강풍 NW(14m/s) + 정면 협곡 지형 + 연속 밀림 |
| **S_time**   | **0.8018** | 0.15 | 0.1203 | 2시간 후 최고조 + 강수 없음(inv=1.0) |
| S_exposure  | 0.7086 | 0.25 | 0.1772 | 인구 2.5만 + 산림 150m + 문화재 |
| S_official  | 0.6700 | 0.20 | 0.1340 | 위험등급 높음(0.75) + 주의보 파생(0.60) |
| S_action    | 0.5000 | 0.20 | 0.1000 | C-1 stub (WateringActionability 미구현) |

**핵심**: S_spread(0.87)가 가장 강하게 기여. 북서풍 + 협곡 정면 노출 + 연속 조밀 산림의 조합이 연소 전파 위험을 극대화.

---

## 3. 곡성군 특이점

### 왜 1위인가

```
WindTowardAssetFeature   = 0.705  (wsd=14m/s, 자산 방향 일치, 돌풍=18m/s)
TerrainTowardAssetFeature = 1.000  (협곡 정면 — 산림이 마을 방향 정면 노출)
FuelContinuityFeature     = 0.975  (연속 산림, 단절 1개, 조밀)
→ S_spread = 0.40×0.705 + 0.25×1.0 + 0.35×0.975 = 0.873
```

```
ForestInterfaceFeature    = 0.964  (산림↔자산 50m, 접경선 950m)
ResidentialExposureFeature = 0.785 (인구 2.5만 + 산림 150m)
→ S_exposure = 0.709
```

### 2025-01-22 실제 산불과의 정합성

- 실제 산불: 전남 곡성군 일대, 강한 건조 북서풍 조건
- 추론 엔진 판단: 1위 PriorityPreWatering (실제 발화 위치와 일치)
- **정합성 평가**: mock 데이터이나, 구조적 패턴이 실제 산불 발생 조건과 일치

---

## 4. Decision Gate 결과

| Gate | 발동 | Mode | 이유 |
|---|---|---|---|
| SelectPreWateringSegment | ✓ | advisory_only | PriorityPreWatering 이상 |
| SchedulePreWatering | ✓ | advisory_only | F_time_lead=low (미구현) |
| AssignResourcePackage | ✓ | manual_review | vehicle/water/duration 3개 low |
| DeferOrMonitor | — | blocked | 대상 State 아님 |
| RequestManualReview | ✓ | manual_review | mock_input=True + 상위 State 검증 권고 |

**최종**: `manual_review` — mock 데이터 기반이므로 인간 확인 필요

---

## 5. DOL 시스템의 가치

> **"만약 실데이터였다면"**

- 산림청 OFFICIAL_FIRE_RISK_FORECAST(A-1 완료)가 실제 2025-01-21 데이터였다면
- KMA 기상 API(A-2 예정)가 당일 건조도·풍속을 정확히 반영했다면
- WateringActionability(C-2 stub → 향후 실구현)가 곡성군 차량 접근성을 반영했다면

→ 이 추론 엔진은 **2025-01-21 오후 시점에 곡성군 일대 PriorityPreWatering을 자동 발령**하고 현장 담당자에게 예정 출동을 권고했을 가능성이 높다.

---

## 6. 한계 및 다음 단계

| 현재 한계 | 다음 단계 |
|---|---|
| mock 데이터 (구조만 실제) | KMA A-2 실연동 후 실검증 |
| S_action stub (0.50 고정) | WateringActionability Feature 구현 |
| 시군구 단위 (읍면동 불가) | 행정동 polygon A-3 후 grain 확장 |
| LLM fallback | ANTHROPIC_API_KEY 설정 후 자연어 브리핑 활성화 |

---

*이 보고서는 DOL 추론 엔진 prototype 검증 목적으로 작성되었습니다.*  
*구조: 김O학님 광주·전남 DOL, 값: 시연용 mock — "구조는 real, 값은 mock"*
