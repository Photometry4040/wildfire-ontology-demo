# D-4: 브리핑 + 회고 API 라우터
# GET  /api/briefing/daily?date=YYYY-MM-DD  → 일일 브리핑
# GET  /api/briefing/retrospective/gokseong → 곡성 산불 회고
# GET  /api/briefing/priority-ranking       → 우선순위 목록 (LLM 없음, 빠름)
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Query

_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "03_backend"))

from app.services.features import run_all_features_mock, run_all_features_live
from app.services.reasoning import compute_signals, evaluate_all_gates, state_ko
from app.services.llm.briefing import generate_daily_briefing
from app.services.retrospective.gokseong_2025_01 import run_retrospective

router = APIRouter()


@router.get("/briefing/priority-ranking")
async def get_priority_ranking(top_n: int = Query(default=10, ge=1, le=27)):
    """
    S_priority 순위 목록 (LLM 없음 — 빠른 응답).
    D-4 대시보드 패널용. 산림청 실 API 사용 (fallback: mock).
    """
    bundles   = compute_signals(await run_all_features_live())
    decisions = evaluate_all_gates(bundles)
    d_map     = {d.sigucode: d for d in decisions}

    return {
        "generated_at": str(date.today()),
        "total":        len(bundles),
        "ranking": [
            {
                "rank":            i,
                "sigucode":        b.sigucode,
                "sigun":           b.sigun,
                "s_priority":      round(b.s_priority, 4),
                "state_band":      b.state_band,
                "state_ko":        state_ko(b.state_band),
                "override_applied": b.override_applied,
                "action_mode":     d_map[b.sigucode].action_mode if b.sigucode in d_map else "unknown",
                "action_summary":  d_map[b.sigucode].action_summary if b.sigucode in d_map else "",
                "signals": {
                    s["kind"]: round(s["score"], 4)
                    for s in b.signal_details
                },
            }
            for i, b in enumerate(bundles[:top_n], 1)
        ],
    }


@router.get("/briefing/daily")
async def get_daily_briefing(
    target_date: str = Query(default=str(date.today()), description="YYYY-MM-DD"),
    top_n: int = Query(default=5, ge=1, le=10),
):
    """
    일일 예비주수 브리핑 (Gemini LLM 자연어 보고서 포함).
    Gemini 우선 → Anthropic fallback → 텍스트 fallback.
    산림청 실 API 사용 (fallback: mock).
    """
    bundles   = compute_signals(await run_all_features_live())
    decisions = evaluate_all_gates(bundles)
    result    = await generate_daily_briefing(bundles, decisions, target_date, top_n)
    return result


@router.get("/briefing/retrospective/gokseong")
def get_gokseong_retrospective():
    """
    2025-01-22 곡성 산불 회고 검증 (D-3).
    "이 추론 엔진이 산불 전날 어떻게 판단했을까?"
    """
    return run_retrospective()


@router.get("/briefing/stats")
async def get_briefing_stats():
    """
    현재 추론 통계 요약 (LLM 없음 — 빠른 응답).
    산림청 실 API 사용 (fallback: mock).
    """
    bundles = compute_signals(await run_all_features_live())

    state_counts: dict[str, int] = {}
    for b in bundles:
        state_counts[b.state_band] = state_counts.get(b.state_band, 0) + 1

    return {
        "total_sigungu": len(bundles),
        "state_counts":  state_counts,
        "immediate_count": state_counts.get("ImmediatePreWatering", 0),
        "priority_count":  state_counts.get("PriorityPreWatering", 0),
        "review_count":    state_counts.get("ReviewPreWatering", 0),
        "top_sigun":       bundles[0].sigun if bundles else "-",
        "top_s_priority":  bundles[0].s_priority if bundles else 0.0,
    }
