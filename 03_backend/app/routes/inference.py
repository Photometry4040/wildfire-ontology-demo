# routes/inference.py
# 역할: 추론 관련 엔드포인트
#   POST /api/inference/run                  — 추론 재실행
#   POST /api/inference/run-with-thresholds  — 가중치 시뮬레이터 (B-3)

from fastapi import APIRouter, HTTPException

from app.models import InferenceResult, WeightRequest, SegmentThresholdResult
from app.services.reasoning_typedb import run_inference, run_with_weights

router = APIRouter()


@router.post("/inference/run", response_model=InferenceResult)
def trigger_inference():
    """
    추론 재실행:
    기존 feature-record / signal-record / decision-state 삭제 후
    원본 segment 데이터 기반으로 재계산하여 삽입.
    """
    try:
        return run_inference()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"추론 실행 실패: {e}")


@router.post("/inference/run-with-thresholds", response_model=list[SegmentThresholdResult])
def simulate_weights(body: WeightRequest):
    """
    사용자 정의 가중치로 S_priority 재계산 (TypeDB 재쓰기 없음).
    Before (기본 가중치) vs After (사용자 가중치) 비교 결과 반환.
    가중치 합계 1.0 권장 (0.95~1.05 허용).
    """
    weights = body.weights.model_dump()
    total = sum(weights.values())
    if not (0.95 <= total <= 1.05):
        raise HTTPException(
            status_code=422,
            detail=f"가중치 합계 {total:.2f} — 1.0 권장 (±0.05 허용)",
        )
    try:
        return run_with_weights(weights)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"시뮬레이션 실패: {e}")
