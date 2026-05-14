# routes/health.py
# 역할: GET /api/health — TypeDB + LM Studio 연결 상태 확인

from fastapi import APIRouter
from typedb.driver import TransactionType

from app.typedb_client import get_driver, DB_NAME
from app.models import HealthResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    """TypeDB + LM Studio 연결 상태 + DB 존재 여부 확인."""
    # TypeDB
    try:
        with get_driver() as driver:
            with driver.transaction(DB_NAME, TransactionType.READ) as tx:
                tx.query(
                    "match $x isa pre-watering-segment; select $x; limit 1;"
                ).resolve()
        typedb_status = "connected"
    except Exception:
        typedb_status = "disconnected"

    # LM Studio
    from app.services.llm.lm_studio_client import get_lm_studio_client
    lm = get_lm_studio_client()
    lm_health = await lm.health_check()

    return {
        "status":     "ok",
        "typedb":     typedb_status,
        "db_name":    DB_NAME,
        "lm_studio":  lm_health,
    }
