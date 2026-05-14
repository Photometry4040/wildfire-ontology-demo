# typedb_client.py
# 역할: TypeDB 연결 싱글톤 + 공통 헬퍼
# 접속 정보: localhost:1729, .env의 TYPEDB_USER/TYPEDB_PASSWORD (기본값: admin/password)

import os
from typedb.driver import TypeDB, TransactionType, Credentials, DriverOptions
from contextlib import contextmanager
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

# ─── 접속 상수 ───
ADDRESS  = os.getenv("TYPEDB_ADDRESS", "localhost:1729")
DB_NAME  = os.getenv("TYPEDB_DB", "onto-fire-dol")
USER     = os.getenv("TYPEDB_USER", "admin")
PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

# TypeDB 드라이버 자격 증명
_creds = Credentials(USER, PASSWORD)
_opts  = DriverOptions(is_tls_enabled=False)


def get_driver():
    """
    TypeDB 드라이버 반환.
    context manager 방식으로 사용:
        with get_driver() as driver:
            with driver.transaction(DB_NAME, TransactionType.READ) as tx:
                ...
    """
    return TypeDB.driver(ADDRESS, credentials=_creds, driver_options=_opts)


def get_value(concept) -> float | str | bool | None:
    """
    ConceptRow.get("varname") 결과에서 Python 기본값 추출.
    TypeDB 3.x: Attribute 객체는 .as_double() / .as_string() / .as_boolean() 호출 필요.
    """
    if concept is None:
        return None
    # 1) double 시도
    try:
        return concept.as_double()
    except Exception:
        pass
    # 2) string 시도
    try:
        return concept.as_string()
    except Exception:
        pass
    # 3) boolean 시도
    try:
        return concept.as_boolean()
    except Exception:
        pass
    # 4) get_value() 시도 (일부 드라이버 버전)
    try:
        return concept.get_value()
    except Exception:
        pass
    # 5) 최후 fallback
    return str(concept)
