# D-2: 일일 브리핑 생성기 (Gemini 우선, Anthropic fallback)
# generate_daily_briefing() → async (asyncio.to_thread 사용)
from __future__ import annotations

from .gemini_client import get_gemini_client
from .client import get_llm_client, MAX_TOKENS_BRIEFING
from .lm_studio_client import get_lm_studio_client
from .prompts import SYSTEM_PROMPT, briefing_user_prompt


_STATE_KO = {
    "ImmediatePreWatering": "즉시예비주수",
    "PriorityPreWatering":  "우선예비주수",
    "ReviewPreWatering":    "검토예비주수",
    "EnhancedMonitoring":   "강화모니터링",
    "GeneralManagement":    "일반관리",
    "NotActionable":        "작업불가",
    "Deferred":             "접근유예",
    "MonitorOnly":          "모니터전용",
    "Recheck":              "재점검",
    "Completed":            "완료",
}

_STATE_ACTION = {
    "ImmediatePreWatering": "즉시 출동·주수·완료 기록",
    "PriorityPreWatering":  "예정 출동·주수 준비",
    "ReviewPreWatering":    "관할청 통보·일일 재점검",
    "EnhancedMonitoring":   "일 2회 모니터링",
    "GeneralManagement":    "정기 모니터링 유지",
    "NotActionable":        "안전 확인 후 재평가",
    "Deferred":             "접근로 확보 후 재평가",
    "MonitorOnly":          "강수 종료 후 재점검",
    "Recheck":              "위험창 재확인",
    "Completed":            "완료 기록 유지",
}


def _structured_fallback(target_date: str, top_dicts: list, total: int, state_counts: dict) -> str:
    """LLM 없이 데이터에서 직접 생성하는 구조화 markdown 브리핑."""
    top = top_dicts[0] if top_dicts else {}
    top_sigun  = top.get("sigun", "-")
    top_sp     = top.get("s_priority", 0)
    top_state  = top.get("state_band", "-")
    top_ko     = _STATE_KO.get(top_state, top_state)

    priority_count = sum(
        v for k, v in state_counts.items()
        if k in ("ImmediatePreWatering", "PriorityPreWatering")
    )
    review_count = state_counts.get("ReviewPreWatering", 0)

    # ① TRIGGER
    trigger_lines = f"> 총 **{total}개** 시군구 중 즉시·우선 조치 필요 **{priority_count}곳**, 검토 **{review_count}곳**"

    # ② STATE 순위표
    rows = ["| 순위 | 시군구 | S_priority | State | 핵심 Signal | Override |",
            "|---|---|---|---|---|---|"]
    for i, s in enumerate(top_dicts, 1):
        sigs = s.get("signals", {})
        top2 = sorted(sigs.items(), key=lambda x: x[1], reverse=True)[:2]
        top2s = " / ".join(f"{k.replace('S_','').lower()}={v:.3f}" for k, v in top2)
        ov = s.get("override", "none")
        ov_cell = f"**{ov}**" if ov != "none" else "—"
        ko = _STATE_KO.get(s.get("state_band",""), s.get("state_band",""))
        rows.append(f"| {i} | {s['sigun']} | {s['s_priority']:.3f} | {ko} | {top2s} | {ov_cell} |")
    state_table = "\n".join(rows)

    # ③ ACTION
    action_lines = []
    for s in top_dicts:
        st  = s.get("state_band", "")
        act = _STATE_ACTION.get(st, "-")
        ko  = _STATE_KO.get(st, st)
        ov  = s.get("override", "none")
        ov_note = f" *(Override: {ov})*" if ov != "none" else ""
        action_lines.append(f"- **{s['sigun']}** ({ko}){ov_note}: {act}")
    action_text = "\n".join(action_lines)

    # ④ LINEAGE
    if top:
        sigs = top.get("signals", {})
        sig_sorted = sorted(sigs.items(), key=lambda x: x[1], reverse=True)
        sig_detail = ", ".join(f"{k}={v:.3f}" for k, v in sig_sorted)
        ov = top.get("override", "none")
        ov_note = f"\n- Override **{ov}** 적용 → 최소 State 격상" if ov != "none" else ""
        _w = {"S_official": 0.20, "S_exposure": 0.25, "S_spread": 0.20,
               "S_action": 0.20, "S_time": 0.15}
        top_sig_name  = sig_sorted[0][0]
        top_sig_score = sig_sorted[0][1]
        top_sig_w     = _w.get(top_sig_name, "?")
        lineage_text = (
            f"**{top_sigun}** (S_priority={top_sp:.3f})이 1위인 이유:\n"
            f"- Signal 분해: {sig_detail}{ov_note}\n"
            f"- 가장 큰 기여: **{top_sig_name}={top_sig_score:.3f}** (가중치 {top_sig_w})"
        )
    else:
        lineage_text = "분석 데이터 없음"

    return f"""## 🔥 {target_date} 예비주수 일일 브리핑

### ① TRIGGER — 오늘의 위험 현황
{trigger_lines}
최우선 지역: **{top_sigun}** — S_priority **{top_sp:.3f}** ({top_ko})

### ② STATE — 우선순위 순위표
{state_table}

### ③ ACTION — 권고 조치
{action_text}

### ④ LINEAGE — 결정 근거
{lineage_text}

---
> ⚠️ **데이터 신뢰도**: S_official은 산림청 실 API 기반, S_exposure·S_spread·S_time은 mock, S_action은 stub(0.50 고정)
> LLM 브리핑 미생성 (Gemini 할당량 초과 또는 API 키 미설정)"""


# ─── 브리핑용 데이터 포맷터 ──────────────────────────────────

def _bundle_to_dict(bundle, decision) -> dict:
    """SignalBundle + DecisionResult → briefing_user_prompt용 dict."""
    return {
        "sigun":          bundle.sigun,
        "s_priority":     bundle.s_priority,
        "state_band":     bundle.state_band,
        "override":       bundle.override_applied,
        "action_summary": decision.action_summary if decision else "",
        "signals": {
            "S_official": bundle.s_official,
            "S_exposure": bundle.s_exposure,
            "S_spread":   bundle.s_spread,
            "S_action":   bundle.s_action,
            "S_time":     bundle.s_time,
        },
    }


# ─── 핵심 API (async) ────────────────────────────────────────

async def generate_daily_briefing(
    bundles: list,
    decisions: list,
    target_date: str = "2026-05-11",
    top_n: int = 5,
) -> dict:
    """
    일일 예비주수 브리핑 생성 (async).

    LLM 우선순위: Gemini → Anthropic → fallback 텍스트
    반환 dict에 llm_provider 필드 추가.
    """
    decision_map = {d.sigucode: d for d in decisions}
    top = bundles[:top_n]
    top_dicts = [_bundle_to_dict(b, decision_map.get(b.sigucode)) for b in top]

    state_counts: dict[str, int] = {}
    for b in bundles:
        state_counts[b.state_band] = state_counts.get(b.state_band, 0) + 1

    user_msg = briefing_user_prompt(target_date, top_dicts, len(bundles))

    # ── LLM 호출 우선순위: Gemini → Anthropic → LM Studio → 구조화 텍스트 ──
    report, from_llm, provider = "", False, "none"

    # 1순위: Gemini
    gemini = get_gemini_client()
    if gemini.available:
        report, from_llm = await gemini.generate_async(user_msg)
        if from_llm:
            provider = "gemini"

    # 2순위: Anthropic Claude
    if not from_llm:
        client = get_llm_client()
        report, from_llm = client.generate(
            system=SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=MAX_TOKENS_BRIEFING,
        )
        if from_llm:
            provider = "anthropic"

    # 3순위: LM Studio 로컬 LLM (max_tokens 기본값 4096 사용 — reasoning 토큰 포함)
    if not from_llm:
        lm = get_lm_studio_client()
        report, from_llm = await lm.generate_async(user_msg)
        if from_llm:
            provider = "lm_studio"

    # 최종: 구조화 텍스트 fallback (LLM 전체 불가 시)
    if not from_llm:
        report   = _structured_fallback(target_date, top_dicts, len(bundles), state_counts)
        provider = "structured"

    return {
        "date":          target_date,
        "report":        report,
        "from_llm":      from_llm,
        "llm_provider":  provider,
        "llm_available": gemini.available or get_llm_client().available,
        "top_segments":  top_dicts,
        "stats": {
            "total_sigungu": len(bundles),
            "state_counts":  state_counts,
            "priority_watering_count": sum(
                1 for b in bundles
                if b.state_band in ("PriorityPreWatering", "ImmediatePreWatering")
            ),
        },
    }
