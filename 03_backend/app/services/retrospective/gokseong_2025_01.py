# D-3: 곡성 산불 (2025-01-22) 회고 검증
# "이 추론 엔진이 2025-01-21 시점에 어떻게 판단했을까?"
#
# 데이터: 기존 mock 데이터 그대로 사용
#   - 모든 mock 값이 2025-01-22 산불 직전 시나리오 기준으로 설정됨
#   - 구조는 김O학님 광주·전남 DOL 그대로, 값은 시연용 mock
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "03_backend"))

from app.services.features import run_all_features_mock
from app.services.reasoning import compute_signals, evaluate_all_gates
from app.services.llm.client import get_llm_client, MAX_TOKENS_RETRO
from app.services.llm.prompts import SYSTEM_PROMPT, retrospective_user_prompt


# ─── 회고 분석 핵심 상수 ─────────────────────────────────────

INCIDENT_DATE   = "2025-01-22"
ANALYSIS_DATE   = "2025-01-21"   # 산불 전날 (추론 엔진 실행 가정)
TARGET_SIGUCODE = "4672000000"   # 곡성군
TARGET_REGION   = "전남 곡성군"

_SIGNAL_NAMES = {
    "S_official": "공식위험",
    "S_exposure": "노출도",
    "S_spread":   "연소전파",
    "S_action":   "행동성(stub)",
    "S_time":     "시간긴박",
}


# ─── 메인 함수 ───────────────────────────────────────────────

def run_retrospective() -> dict:
    """
    곡성 산불 회고 분석 실행.

    반환:
        {
          "incident_date": str,
          "analysis_date": str,
          "target": dict,          # 곡성군 추론 결과
          "region_ranking": list,  # 전체 순위
          "key_findings": dict,
          "report": str,           # LLM 자연어 보고서
          "from_llm": bool,
        }
    """
    # ── 추론 실행 ──
    feature_rows = run_all_features_mock()
    bundles      = compute_signals(feature_rows)
    decisions    = evaluate_all_gates(bundles)

    # ── 곡성군 결과 추출 ──
    gk_bundle   = next(b for b in bundles  if b.sigucode == TARGET_SIGUCODE)
    gk_decision = next(d for d in decisions if d.sigucode == TARGET_SIGUCODE)

    gk_signals = {
        _SIGNAL_NAMES[s["kind"]]: s["score"]
        for s in gk_bundle.signal_details
    }

    # ── 전체 순위 (상위 10) ──
    ranking = [
        {
            "rank":       i,
            "sigun":      b.sigun,
            "s_priority": b.s_priority,
            "state_band": b.state_band,
            "signals": {s["kind"]: s["score"] for s in b.signal_details},
        }
        for i, b in enumerate(bundles[:10], 1)
    ]

    # ── 주요 발견 ──
    gk_rank    = next(r["rank"] for r in ranking if r["sigun"] == "곡성군")
    top_signal = max(gk_bundle.signal_details, key=lambda s: s["score"])

    key_findings = {
        "전체 순위":    f"{gk_rank}위 / {len(bundles)}개 시군구",
        "S_priority":  f"{gk_bundle.s_priority:.4f} → {gk_bundle.state_band}",
        "최대 기여 Signal": f"{top_signal['kind']} = {top_signal['score']:.4f}",
        "S_spread":    f"{gk_bundle.s_spread:.4f} (강풍 NW + 정면 지형 + 연속 밀림)",
        "S_time":      f"{gk_bundle.s_time:.4f} (2시간 후 최고조, 강수 없음)",
        "Override":    gk_bundle.override_applied or "none",
        "권고 행동":   gk_decision.action_summary,
        "Action Mode": gk_decision.action_mode,
        "데이터 출처":  "시연용 mock (구조: 김O학 DOL, 값: 2025-01-22 시나리오 기반)",
    }

    # ── LLM 회고 보고서 ──
    user_msg = retrospective_user_prompt(
        incident_date=INCIDENT_DATE,
        incident_location=TARGET_REGION,
        analysis_date=ANALYSIS_DATE,
        segments=[
            {
                "sigun":      b.sigun,
                "s_priority": b.s_priority,
                "state_band": b.state_band,
                "signals":    {s["kind"]: s["score"] for s in b.signal_details},
            }
            for b in bundles[:5]
        ],
        key_findings=key_findings,
    )

    client = get_llm_client()
    report, from_llm = client.generate(
        system=SYSTEM_PROMPT,
        user=user_msg,
        max_tokens=MAX_TOKENS_RETRO,
        use_cache=False,   # 회고는 캐시 사용 안 함 (매번 신선한 분석)
    )

    return {
        "incident_date":  INCIDENT_DATE,
        "analysis_date":  ANALYSIS_DATE,
        "target_region":  TARGET_REGION,
        "target": {
            "sigucode":      gk_bundle.sigucode,
            "sigun":         gk_bundle.sigun,
            "s_priority":    gk_bundle.s_priority,
            "state_band":    gk_bundle.state_band,
            "override":      gk_bundle.override_applied,
            "signals":       gk_signals,
            "action_mode":   gk_decision.action_mode,
            "action_summary": gk_decision.action_summary,
            "gates": [
                {"gate": g.gate, "triggered": g.triggered, "mode": g.mode}
                for g in gk_decision.gates
            ],
        },
        "region_ranking": ranking,
        "key_findings":   key_findings,
        "report":         report,
        "from_llm":       from_llm,
        "llm_available":  client.available,
    }


# ─── CLI 직접 실행 ───────────────────────────────────────────

if __name__ == "__main__":
    import json
    result = run_retrospective()
    print("\n" + "=" * 60)
    print(f"★ {result['target_region']} 산불 회고 분석 ({result['incident_date']})")
    print("=" * 60)
    print(f"\n추론 엔진 실행 가정일: {result['analysis_date']}")
    print(f"S_priority : {result['target']['s_priority']:.4f}")
    print(f"State Band : {result['target']['state_band']}")
    print(f"Action Mode: {result['target']['action_mode']}")
    print("\n[LLM 보고서]")
    print(result["report"])
    print("\n[Key Findings]")
    for k, v in result["key_findings"].items():
        print(f"  {k}: {v}")
