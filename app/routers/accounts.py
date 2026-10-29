from typing import Annotated

import psycopg
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.config import BASE_DIR, get_settings
from app.database import get_connection
from app.security import create_csrf_token, hash_password, is_valid_csrf_token


router = APIRouter(tags=["회원"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def signup_page(request: Request, *, error="", name="", email="", status_code=200):
    token = create_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={
            "completed": False,
            "error": error,
            "name": name,
            "email": email,
            "csrf_token": token,
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        "signup_csrf",
        token,
        max_age=3600,
        httponly=True,
        secure=get_settings().cookie_secure or request.url.scheme == "https",
        samesite="strict",
        path="/signup",
    )
    return response


@router.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return signup_page(request)


@router.post("/signup", response_class=HTMLResponse)
def signup(
    request: Request,
    name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    password_confirm: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
    signup_csrf: Annotated[str | None, Cookie()] = None,
):
    name = name.strip()
    email = email.strip().lower()

    def fail(message: str, status_code: int = 400):
        # 오류가 나도 비밀번호를 화면에 다시 채우지 않는다.
        return signup_page(
            request,
            error=message,
            name=name[:50],
            email=email[:254],
            status_code=status_code,
        )

    if not is_valid_csrf_token(signup_csrf, csrf_token):
        return fail("입력 시간이 만료되었거나 요청을 확인할 수 없습니다. 다시 입력해 주세요.", 403)

    if not 1 <= len(name) <= 50:
        return fail("이름은 앞뒤 공백을 제외하고 1~50자로 입력해 주세요.")

    if len(email) > 254:
        return fail("이메일은 254자 이내로 입력해 주세요.")

    try:
        # 주소 형식을 검사하며 실제 메일 발송이나 DNS 조회는 하지 않는다.
        email = validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return fail("올바른 이메일 주소를 입력해 주세요.")

    # bcrypt의 입력 제한을 넘는 비밀번호를 잘라 저장하지 않는다.
    if len(password) < 8 or len(password.encode("utf-8")) > 72 or "\x00" in password:
        return fail("비밀번호는 8자 이상, UTF-8 기준 72바이트 이하로 입력해 주세요.")

    if password != password_confirm:
        return fail("비밀번호와 비밀번호 확인이 일치하지 않습니다.")

    password_hash = hash_password(password)

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                # 사용자 입력은 문자열 조립 대신 SQL 매개변수로 전달한다.
                cursor.execute(
                    """
                    INSERT INTO public.shop_users (email, password_hash, name)
                    VALUES (%s, %s, %s)
                    """,
                    (email, password_hash, name),
                )
    except psycopg.errors.UniqueViolation:
        return fail("이미 가입된 이메일입니다. 다른 이메일을 입력해 주세요.", 409)
    except (psycopg.Error, ValidationError):
        return fail("회원가입을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.", 503)

    # 새로고침으로 가입 요청이 다시 전송되지 않도록 이동한다.
    response = RedirectResponse(url="/signup/complete", status_code=303)
    response.delete_cookie("signup_csrf", path="/signup")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/signup/complete", response_class=HTMLResponse)
def signup_complete(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={"completed": True},
        headers={"Cache-Control": "no-store"},
    )
