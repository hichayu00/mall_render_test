import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import psycopg
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Cookie, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.config import BASE_DIR, get_settings
from app.database import get_connection
from app.security import create_csrf_token, hash_password, is_valid_csrf_token, verify_password
from app.session_auth import (
    SESSION_COOKIE,
    SESSION_SECONDS,
    current_user,
    hash_session_token,
    login_redirect,
    safe_next,
    session_csrf_token,
    session_token,
)


router = APIRouter(tags=["로그인"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")
# 없는 이메일도 해시 비교를 하도록 서버 시작 시 비교용 값을 만든다.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def login_page(request: Request, *, next_path="/account", email="", error="", status_code=200):
    token = create_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "next_path": safe_next(next_path),
            "email": email[:254],
            "error": error,
            "csrf_token": token,
            "notice": {
                "profile_updated": "회원정보가 변경되었습니다. 변경한 정보로 다시 로그인해 주세요.",
                "withdrawn": "탈퇴 처리가 완료되었습니다. 회원 개인정보와 로그인 세션을 제거했습니다.",
            }.get(request.query_params.get("notice", ""), ""),
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        "login_csrf", token, max_age=3600, httponly=True,
        secure=get_settings().cookie_secure or request.url.scheme == "https", samesite="strict", path="/login",
    )
    return response


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/account"):
    destination = safe_next(next)
    if current_user(request):
        return RedirectResponse(destination, status_code=303, headers={"Cache-Control": "no-store"})
    return login_page(request, next_path=destination)


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "/account",
    csrf_token: Annotated[str, Form()] = "",
    login_csrf: Annotated[str | None, Cookie()] = None,
):
    email = email.strip().lower()
    destination = safe_next(next)

    def fail(message: str, status_code: int):
        return login_page(
            request, next_path=destination, email=email,
            error=message, status_code=status_code,
        )

    if not is_valid_csrf_token(login_csrf, csrf_token):
        return fail("입력 시간이 만료되었거나 요청을 확인할 수 없습니다. 다시 입력해 주세요.", 403)
    if len(email) > 254:
        return fail("이메일 또는 비밀번호가 올바르지 않습니다.", 401)
    try:
        email = validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return fail("이메일 또는 비밀번호가 올바르지 않습니다.", 401)

    new_token = secrets.token_urlsafe(32)
    old_token = session_token(request)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)
    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                # 회원 변경·탈퇴와 세션 생성이 엇갈리지 않도록 회원 행을 잠근다.
                cursor.execute(
                    """
                    SELECT id, password_hash
                    FROM public.shop_users
                    WHERE email = %s AND deleted_at IS NULL
                    FOR UPDATE
                    """,
                    (email,),
                )
                user = cursor.fetchone()
                valid_password = verify_password(
                    password, user["password_hash"] if user else DUMMY_PASSWORD_HASH
                )
                if not user or not valid_password:
                    return fail("이메일 또는 비밀번호가 올바르지 않습니다.", 401)

                # 같은 브라우저의 이전 로그인 표는 폐기하고 새 표를 발급한다.
                cursor.execute(
                    """
                    DELETE FROM public.sessions
                    WHERE (user_id = %s AND expires_at <= now()) OR token_hash = %s
                    """,
                    (user["id"], hash_session_token(old_token) if old_token else None),
                )
                cursor.execute(
                    """
                    INSERT INTO public.sessions (user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (user["id"], hash_session_token(new_token), expires_at),
                )
    except (psycopg.Error, ValidationError):
        return fail("로그인을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.", 503)

    response = RedirectResponse(destination, status_code=303)
    response.set_cookie(
        SESSION_COOKIE, new_token, max_age=SESSION_SECONDS, expires=expires_at,
        httponly=True, secure=get_settings().cookie_secure or request.url.scheme == "https", samesite="lax", path="/",
    )
    response.delete_cookie("login_csrf", path="/login")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/account", response_class=HTMLResponse)
def account(request: Request, updated: bool = False):
    user = current_user(request)
    if not user:
        return login_redirect("/account")
    return templates.TemplateResponse(
        request=request,
        name="account.html",
        context={
            "user": user,
            "csrf_token": session_csrf_token(session_token(request)),
            "updated": updated,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/logout")
def logout(request: Request, csrf_token: Annotated[str, Form()] = ""):
    token = session_token(request)
    if not token:
        return login_redirect()
    if not is_valid_csrf_token(session_csrf_token(token), csrf_token):
        raise HTTPException(403, "요청을 확인할 수 없습니다. 회원정보 화면을 새로고침해 주세요.")
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.sessions WHERE token_hash = %s",
                    (hash_session_token(token),),
                )
    except (psycopg.Error, ValidationError):
        raise HTTPException(503, "로그아웃을 처리하지 못했습니다. 다시 시도해 주세요.") from None
    return login_redirect()
