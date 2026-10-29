import psycopg

from app.config import get_settings


def get_connection() -> psycopg.Connection:
    settings = get_settings()

    # 비밀번호를 URL에 합치지 않고 개별 인자로 전달한다.
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        sslmode="require",
        connect_timeout=10,
        options="-c statement_timeout=10000",
    )
