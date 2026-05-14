# D-2: 프롬프트 템플릿
# 출처: CLAUDE.md §발표 핵심 수식, docs/06_decision-logic.md §Signal Formulas
from __future__ import annotations

SYSTEM_PROMPT = """당신은 광주·전남 산불 예방 예비주수(豫備注水) 운영 지원 AI입니다.

## 역할
DOL(Decision Operating Layer) 추론 엔진 출력을 의사결정자가 즉시 행동할 수 있는 구조화된 한국어 보고서로 변환합니다.
B-1 데이터는 산림청 실 API 기반입니다. 수치를 신뢰하되 B-2~B-4는 mock 기반임을 주석으로 표기하세요.

## DOL 추론 파이프라인 (4단계)
TRIGGER → STATE → ACTION → LINEAGE

### Signal 구조
S_priority = 0.20×S_official + 0.25×S_exposure + 0.20×S_spread + 0.20×S_action + 0.15×S_time

| Signal | 데이터 소스 | 의미 | 가중치 |
|---|---|---|---|
| S_official | 산림청 실 API ✅ | 공식 위험등급·추세·대형산불경보 | 0.20 |
| S_exposure | mock | 주거지·문화재·병원 노출도 + 산림 접경 | 0.25 |
| S_spread | mock | 바람·지형·연료 연속성 | 0.20 |
| S_action | stub(0.50) | 차량 접근성·수원·작업 안전성 | 0.20 |
| S_time | mock | 위험 시간창 긴박도·강수 상쇄 | 0.15 |

### State Band (5단계)
- **GeneralManagement** (< 0.20): 정기 모니터링
- **EnhancedMonitoring** (0.20~0.40): 일 2회 재점검
- **ReviewPreWatering** (0.40~0.60): 관할청 통보·일일 재점검
- **PriorityPreWatering** (0.60~0.80): 예정 출동·주수·완료 기록
- **ImmediatePreWatering** (≥ 0.80): 즉시 출동·주수·완료 기록·재점검 예약

### Override (9개, 우선순위 순)
1. HazardGate — 작업 불가  2. AccessGate — 접근 불가  3. RainGate — 강수 우세
4. Recheck — 완료 후 새 위험창  5. Completed — 완료
6. AlertSevere — 경보  7. AlertWarning — 주의보+노출  8. GradeSevere — 매우높음  9. GradeHigh — 높음

## 출력 형식 (반드시 아래 마크다운 구조 사용)
```
## 🔥 {날짜} 예비주수 일일 브리핑

### ① TRIGGER — 오늘의 위험 현황
(전체 {N}개 시군구 중 조치 필요 구간 수, 최고위험 지역 1~2문장)

### ② STATE — 우선순위 순위표
| 순위 | 시군구 | S_priority | State | 핵심 Signal | Override |
|---|---|---|---|---|---|
(상위 5개 행)

### ③ ACTION — 권고 조치
(각 시군구별 "무엇을 해야 하는가" — 출동/관찰/대기 구분)

### ④ LINEAGE — 결정 근거
(최우선 시군구가 1위인 이유를 Signal 수치 기반으로 설명)

> ⚠️ **데이터 신뢰도**: S_official은 산림청 실 API 기반, S_exposure·S_spread·S_time은 mock, S_action은 stub(0.50 고정)
```

## 출력 원칙
- 한국어, 수치 명시, 간결
- 의사결정자 관점: "무엇을 해야 하는가"가 핵심
- 마크다운 헤딩(##/###)과 표(|---|)를 반드시 사용
"""


def briefing_user_prompt(
    target_date: str,
    top_segments: list[dict],
    total_count: int,
) -> str:
    """
    일일 브리핑 user message 생성.
    top_segments: [{"sigun", "s_priority", "state_band", "signals", "action_summary", "override"}, ...]
    """
    # 순위표 텍스트 생성
    rows = []
    for i, s in enumerate(top_segments, 1):
        sigs  = s.get("signals", {})
        # 가장 높은 Signal 2개 추출
        top2  = sorted(sigs.items(), key=lambda x: x[1], reverse=True)[:2]
        top2s = " / ".join(f"{k.replace('S_','').lower()}={v:.3f}" for k, v in top2)
        ov    = s.get("override", "none")
        ov    = f"**{ov}**" if ov != "none" else "—"
        rows.append(
            f"| {i} | {s['sigun']} "
            f"| {s['s_priority']:.3f} "
            f"| {s['state_band']} "
            f"| {top2s} "
            f"| {ov} |"
        )
    table = (
        "| 순위 | 시군구 | S_priority | State | 핵심 Signal | Override |\n"
        "|---|---|---|---|---|---|\n"
        + "\n".join(rows)
    )

    # 전체 signal 상세 (LLM LINEAGE 생성용)
    detail_text = ""
    for i, s in enumerate(top_segments, 1):
        sigs = s.get("signals", {})
        sig_str = ", ".join(f"{k}={v:.3f}" for k, v in sigs.items())
        detail_text += (
            f"\n{i}. {s['sigun']} — {sig_str}"
            f" / override={s.get('override','none')}"
            f" / 권고={s.get('action_summary','-')}"
        )

    return f"""## {target_date} 일일 예비주수 브리핑 생성 요청

**분석 대상**: 광주·전남 {total_count}개 시군구 (B-1 산림청 실 API 기반)

### 상위 {len(top_segments)}개 시군구 데이터
{table}

#### 상세 Signal 값 (LINEAGE 분석용)
{detail_text}

---
위 데이터를 바탕으로 시스템 프롬프트에 명시된 ①TRIGGER→②STATE→③ACTION→④LINEAGE 구조의 마크다운 브리핑을 작성해 주세요.
순위표는 그대로 포함하고, LINEAGE 섹션에서 1위 시군구의 결정 근거를 Signal 수치로 설명해 주세요.
"""


def retrospective_user_prompt(
    incident_date: str,
    incident_location: str,
    analysis_date: str,
    segments: list[dict],
    key_findings: dict,
) -> str:
    """
    곡성 산불 회고 분석 user message.
    """
    segs_text = ""
    for s in segments:
        sigs = s.get("signals", {})
        sig_str = ", ".join(f"{k}={v:.3f}" for k, v in sigs.items())
        segs_text += (
            f"- {s['sigun']}: S_priority={s['s_priority']:.3f}, "
            f"State={s['state_band']}\n"
            f"  Signals: {sig_str}\n"
        )

    findings_text = "\n".join(f"- {k}: {v}" for k, v in key_findings.items())

    return f"""## {incident_date} {incident_location} 산불 회고 분석

분석 시나리오:
- 산불 발생일: {incident_date}
- 추론 엔진 실행 가정일: {analysis_date} (산불 전날)
- 분석 목적: "이 추론 엔진이 그날 어떻게 판단했을까?"

### 추론 결과 (mock 데이터 기반)
{segs_text}

### 주요 발견
{findings_text}

위 데이터를 바탕으로 회고 분석 보고서를 작성해 주세요:
1. 추론 엔진의 당시 판단 요약
2. 어떤 Signal이 가장 강하게 기여했는가
3. 실제 산불과의 정합성 평가 (mock 한계 명시)
4. DOL 시스템의 운영 가치 — "만약 실데이터였다면"
"""
