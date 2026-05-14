# main.py
# 역할: FastAPI 앱 진입점
# - CORS 미들웨어 (개발용 *)
# - 라우터 등록 (/api 접두사)
# - 정적 파일 서빙 (04_frontend/)

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import health, segments, inference, briefing, baseline

app = FastAPI(
    title="DOL 추론 엔진 API",
    description="광주·전남 예비주수 DOL(Decision Operating Layer) — TypeDB 기반 추론 엔진",
    version="1.0.0",
)

# ─── CORS 미들웨어 ───
# 발표용: 도메인 제한 없음. 운영 환경에서는 도메인 지정 필요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 라우터 등록 (/api 접두사) ───
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(segments.router, prefix="/api", tags=["segments"])
app.include_router(inference.router, prefix="/api", tags=["inference"])
app.include_router(briefing.router, prefix="/api", tags=["briefing"])
app.include_router(baseline.router, prefix="/api", tags=["baseline"])

# ─── baseline 프론트엔드 정적 서빙 (/baseline/) ───
baseline_frontend = Path(__file__).parent.parent.parent / "01_baseline" / "frontend"
if baseline_frontend.exists():
    app.mount("/baseline", StaticFiles(directory=str(baseline_frontend), html=True), name="baseline-frontend")

# ─── 정적 파일 서빙 ───
# 개발: npm run dev (localhost:5173)
# 프로덕션: npm run build → dist/ 서빙
frontend_path = Path(__file__).parent.parent.parent / "04_frontend" / "dist"
if not frontend_path.exists():
    frontend_path = Path(__file__).parent.parent.parent / "04_frontend"
if frontend_path.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_path), html=True),
        name="frontend",
    )
