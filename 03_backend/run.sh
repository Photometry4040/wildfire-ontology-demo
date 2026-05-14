#!/bin/bash
# run.sh
# 역할: FastAPI 서버 기동
# 사용법: cd 03_backend && ./run.sh

# 스크립트 위치로 이동
cd "$(dirname "$0")"

# 의존성 설치 (이미 설치된 경우 건너뜀)
echo "패키지 확인 중..."
pip install -q -r requirements.txt

# FastAPI 서버 기동
echo "FastAPI 서버 시작 — http://localhost:8001"
echo "API 문서: http://localhost:8001/docs"
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
