from typing import Annotated

import psycopg
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.config import BASE_DIR
from app.database import get_connection
from app.security import hash_password, is_valid_csrf_token, verify_password
from app.session_auth import (
    SESSION_COOKIE,
    current_user,
    lock_account,
    login_redirect,
    session_csrf_token,
    session_token,
)


router = APIRouter(tags=["회원정보"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def profile_page(request, user, *, mode="edit", error="", status_code=200):
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user": user,
            "mode": mode,
            "error": error,
            "csrf_token": session_csrf_token(session_token(request)),
        },
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def check_form(request: Request, csrf_token: str):
    token = session_token(request)
    if not token or not is_valid_csrf_token(session_csrf_token(token), csrf_token):
        raise HTTPException(403, "요청을 확인할 수 없습니다. 화면을 새로고침해 주세요.")


def signed_out(notice: str):
    response = RedirectResponse("/login?notice=" + notice, status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/account/edit", response_class=HTMLResponse)
def edit_form(request: Request):
    user = current_user(request)
    return profile_page(request, user) if user else login_redirect("/account/edit")


@router.post("/account/edit", response_class=HTMLResponse)
def edit_profile(
    request: Request,
    name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    current_password: Annotated[str, Form()] = "",
    new_password: Annotated[str, Form()] = "",
    new_password_confirm: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    user = current_user(request)
    if not user:
        return login_redirect("/account/edit")
    check_form(request, csrf_token)
    name, email = name.strip(), email.strip().lower()

    def fail(message, status_code=400):
        # 오류 시 비밀번호를 제외한 입력만 다시 표시한다.
        values = {**user, "name": name[:50], "email": email[:254]}
        return profile_page(request, values, error=message, status_code=status_code)

    if not 1 <= len(name) <= 50:
        return fail("이름은 앞뒤 공백을 제외하고 1~50자로 입력해 주세요.")
    if len(email) > 254:
        return fail("이메일은 254자 이내로 입력해 주세요.")
    try:
        email = validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return fail("올바른 이메일 주소를 입력해 주세요.")
    if new_password or new_password_confirm:
        if len(new_password) < 8 or len(new_password.encode("utf-8")) > 72 or "\x00" in new_password:
            return fail("새 비밀번호는 8자 이상, UTF-8 기준 72바이트 이하로 입력해 주세요.")
        if new_password != new_password_confirm:
            return fail("새 비밀번호와 비밀번호 확인이 일치하지 않습니다.")

    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                locked = lock_account(cursor, user["id"], session_token(request))
                if not locked:
                    return login_redirect("/account/edit")
                if not verify_password(current_password, locked["password_hash"]):
                    return fail("현재 비밀번호가 올바르지 않습니다.")
                password_hash = hash_password(new_password) if new_password else locked["password_hash"]
                require_login = bool(new_password) or email != locked["email"]
                cursor.execute(
                    """
                    UPDATE public.shop_users
                    SET name = %s, email = %s, password_hash = %s WHERE id = %s
                    """,
                    (name, email, password_hash, user["id"]),
                )
                if require_login:
                    # 로그인 정보가 바뀌면 다른 브라우저의 세션도 모두 만료시킨다.
                    cursor.execute("DELETE FROM public.sessions WHERE user_id = %s", (user["id"],))
    except psycopg.errors.UniqueViolation:
        return fail("이미 사용 중인 이메일입니다.", 409)
    except (psycopg.Error, ValidationError):
        return fail("회원정보를 수정하지 못했습니다. 잠시 후 다시 시도해 주세요.", 503)

    if require_login:
        return signed_out("profile_updated")
    return RedirectResponse("/account?updated=true", status_code=303, headers={"Cache-Control": "no-store"})


@router.get("/account/withdraw", response_class=HTMLResponse)
def withdraw_form(request: Request):
    user = current_user(request)
    return profile_page(request, user, mode="withdraw") if user else login_redirect("/account/withdraw")


@router.post("/account/withdraw", response_class=HTMLResponse)
def withdraw(
    request: Request,
    current_password: Annotated[str, Form()] = "",
    confirm: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    user = current_user(request)
    if not user:
        return login_redirect("/account/withdraw")
    check_form(request, csrf_token)

    def fail(message, status_code=400):
        return profile_page(request, user, mode="withdraw", error=message, status_code=status_code)

    if confirm != "yes":
        return fail("탈퇴 안내를 읽고 확인란을 선택해 주세요.")
    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                locked = lock_account(cursor, user["id"], session_token(request))
                if not locked:
                    return login_redirect("/account/withdraw")
                if not verify_password(current_password, locked["password_hash"]):
                    return fail("현재 비밀번호가 올바르지 않습니다.")
                # 주문 기록은 유지하되 회원과 주문의 개인정보를 함께 제거한다.
                cursor.execute(
                    """
                    UPDATE public.shop_users
                    SET email = NULL, name = NULL, password_hash = NULL, deleted_at = now()
                    WHERE id = %s
                    """,
                    (user["id"],),
                )
                cursor.execute(
                    """
                    UPDATE public.orders
                    SET recipient_name = NULL, recipient_phone = NULL, shipping_address = NULL
                    WHERE user_id = %s
                    """,
                    (user["id"],),
                )
                cursor.execute("DELETE FROM public.sessions WHERE user_id = %s", (user["id"],))
    except (psycopg.Error, ValidationError):
        return fail("탈퇴를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.", 503)
    return signed_out("withdrawn")
