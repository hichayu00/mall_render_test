import hashlib
import hmac
import re
from urllib.parse import quote, urlsplit

import psycopg
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.database import get_connection


SESSION_COOKIE = "shop_session"
SESSION_SECONDS = 7 * 24 * 60 * 60


def lock_account(cursor, user_id: int, token: str):
    # 회원 → 세션 순서로 잠가 탈퇴·수정·주문이 엇갈리지 않게 한다.
    cursor.execute(
        """
        SELECT id, name, email, password_hash FROM public.shop_users
        WHERE id = %s AND deleted_at IS NULL FOR UPDATE
        """,
        (user_id,),
    )
    user = cursor.fetchone()
    if not user:
        return None
    cursor.execute(
        """
        SELECT id FROM public.sessions
        WHERE user_id = %s AND token_hash = %s AND expires_at > now() FOR UPDATE
        """,
        (user_id, hash_session_token(token)),
    )
    return user if cursor.fetchone() else None


def session_token(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    return token if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None


def hash_session_token(token: str) -> str:
    # DB에는 로그인 표의 원문 대신 SHA-256 해시만 저장한다.
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def session_csrf_token(token: str) -> str:
    # 로그인 표를 노출하지 않으면서 해당 세션에 연결된 확인표를 만든다.
    return hmac.new(token.encode("ascii"), b"shop-form-csrf", hashlib.sha256).hexdigest()


def safe_next(value: str) -> str:
    # 현재 쇼핑몰에서 쓰는 영문·숫자 기반 내부 경로만 허용한다.
    if not value or len(value) > 2048 or value.startswith("//"):
        return "/account"
    if "\\" in value or any(ord(char) <= 32 or ord(char) == 127 for char in value):
        return "/account"
    try:
        parts = urlsplit(value)
    except ValueError:
        return "/account"
    if parts.scheme or parts.netloc or not re.fullmatch(r"/[A-Za-z0-9/_-]*", parts.path):
        return "/account"
    if parts.path.rstrip("/") in {"/login", "/logout"}:
        return "/account"
    return value


def login_redirect(next_path: str = "/account") -> RedirectResponse:
    response = RedirectResponse(
        url="/login?next=" + quote(safe_next(next_path), safe=""), status_code=303
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


def current_user(request: Request) -> dict | None:
    token = session_token(request)
    if not token:
        return None
    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.email, u.name, s.expires_at
                    FROM public.sessions AS s
                    JOIN public.shop_users AS u ON u.id = s.user_id
                    WHERE s.token_hash = %s
                      AND s.expires_at > now()
                      AND u.deleted_at IS NULL
                    """,
                    (hash_session_token(token),),
                )
                return cursor.fetchone()
    except (psycopg.Error, ValidationError):
        raise HTTPException(503, "로그인 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.") from None
