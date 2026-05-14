# routes/segments.py
# 역할: 구간 관련 엔드포인트
#   GET /api/segments                        — 전체 목록
#   GET /api/segments/{id}                   — 상세 (feature + signal 포함)
#   GET /api/segments/{id}/lineage           — Lineage 역추적
#   GET /api/segments/{id}/inference-trace   — 3단계 추론 라이브 뷰 (B-4)

from fastapi import APIRouter, HTTPException

from app.models import SegmentSummary, SegmentDetail, LineageItem, InferenceTraceResponse
from app.services.reasoning_typedb import (
    get_all_segments,
    get_segment_detail,
    get_segment_lineage,
    get_inference_trace,
    get_all_raw_signals,
)

router = APIRouter()


@router.get("/segments/raw-signals")
def list_raw_signals():
    """몬테카를로 시뮬레이션용 — 모든 구간의 5개 Signal 원시값 반환."""
    try:
        return get_all_raw_signals()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TypeDB 조회 실패: {e}")


@router.get("/segments", response_model=list[SegmentSummary])
def list_segments():
    """전체 구간 목록 반환."""
    try:
        return get_all_segments()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TypeDB 조회 실패: {e}")


@router.get("/segments/{segment_id}", response_model=SegmentDetail)
def get_segment(segment_id: str):
    """구간 ID로 상세 정보 반환 (feature + signal 포함)."""
    try:
        result = get_segment_detail(segment_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TypeDB 조회 실패: {e}")

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"구간 '{segment_id}'를 찾을 수 없습니다.",
        )
    return result


@router.get("/segments/{segment_id}/lineage", response_model=list[LineageItem])
def get_lineage(segment_id: str):
    """구간 ID로 Decision Lineage 역추적 결과 반환."""
    try:
        return get_segment_lineage(segment_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TypeDB 조회 실패: {e}")


@router.get("/segments/{segment_id}/inference-trace", response_model=InferenceTraceResponse)
def get_trace(segment_id: str):
    """구간 ID로 3단계 함수 추론 trace 반환 (B-4 라이브 뷰용)."""
    try:
        result = get_inference_trace(segment_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TypeDB 조회 실패: {e}")

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"구간 '{segment_id}'의 trace를 찾을 수 없습니다.",
        )
    return result
