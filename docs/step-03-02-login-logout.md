# STEP 3-2 — 로그인·로그아웃과 로그인 상태 확인

## 1. 이번 단계의 목표

가입한 이메일·비밀번호로 로그인하고, 로그인한 회원만 자신의 회원정보를 확인하도록 구현합니다. 로그아웃하면 DB 세션과 브라우저 쿠키를 제거합니다.

이번에는 로그인·로그아웃·회원정보 조회만 다룹니다. 회원정보 수정과 탈퇴는 확인 결과를 받은 뒤 이어갑니다. 새 테이블·SQL·환경변수·패키지는 필요하지 않습니다. 코드 실행, DB 접속, 테스트는 하지 않았습니다.

### 로그인은 입장권 발급이라고 생각하세요

| 구성요소 | 쉬운 설명 | 저장 위치 |
|---|---|---|
| 이메일·비밀번호 | 회원인지 확인할 때 제출하는 정보 | 비밀번호는 해시만 shop_users에 저장 |
| 세션 토큰 | 로그인 후 발급하는 무작위 입장권 | 브라우저 쿠키 |
| 세션 | 누가 언제까지 로그인했는지 적은 기록 | sessions 테이블 |
| 쿠키 | 브라우저가 같은 사이트 요청에 함께 보내는 작은 값 | 브라우저 |
| HttpOnly | JavaScript에서 해당 쿠키 값을 읽지 못하게 하는 속성 | 쿠키 설정 |

로그인 후에는 요청마다 비밀번호를 다시 보내지 않습니다. 브라우저가 입장권을 보내면 서버는 DB의 유효한 세션인지 확인합니다.

## 2. 생성·수정 파일과 코드

| 파일 | 작업 | 역할 |
|---|---|---|
| app/security.py | 수정 | 입력한 비밀번호와 bcrypt 해시 비교 |
| app/session_auth.py | 생성 | 세션 조회, 내부 복귀 경로 검사, 로그인 이동 |
| app/routers/auth.py | 생성 | 로그인·로그아웃·회원정보 요청 처리 |
| app/main.py | 수정 | 로그인 라우터 연결 |
| templates/login.html | 생성 | 로그인 화면 |
| templates/account.html | 생성 | 로그인 회원의 정보와 로그아웃 버튼 |
| templates/signup.html | 수정 | 가입 완료 후 로그인 링크 |
| static/style.css | 수정 | 회원정보 표시 스타일 |

아래에는 새 파일의 전체 코드와 기존 파일의 변경 부분만 담았습니다. `auth.py`의 비교용 더미 해시는 사용자가 서버를 시작할 때 만들어지며, 학습용 회원이나 DB 데이터를 생성하지 않습니다.

### app/security.py — 추가한 함수

```python
def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > 72 or "\x00" in password:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False
```

### app/main.py — 바뀐 부분

기존 라우터 import를 아래처럼 바꾸고, auth 라우터 연결을 추가했습니다.

```python
from app.routers import accounts, auth

app.include_router(auth.router)
```

### templates/signup.html — 바뀐 부분

가입 완료 안내와 버튼을 교체했습니다.

```html
<p class="hint">가입한 이메일과 비밀번호로 로그인해 주세요.</p>
<a class="button" href="/login">로그인하기</a>
```

가입 폼 아래에는 다음 링크를 추가했습니다.

```html
<p class="hint">이미 가입하셨나요? <a href="/login">로그인</a></p>
```

### static/style.css — 추가한 부분

```css
dt { margin-top: 16px; font-weight: 700; }
dd { margin: 4px 0 0; overflow-wrap: anywhere; }
```

### app/session_auth.py

```python
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
```

### app/routers/auth.py

```python
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

from app.config import BASE_DIR
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
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        "login_csrf", token, max_age=3600, httponly=True,
        secure=request.url.scheme == "https", samesite="strict", path="/login",
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
        httponly=True, secure=request.url.scheme == "https", samesite="lax", path="/",
    )
    response.delete_cookie("login_csrf", path="/login")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/account", response_class=HTMLResponse)
def account(request: Request):
    user = current_user(request)
    if not user:
        return login_redirect("/account")
    return templates.TemplateResponse(
        request=request,
        name="account.html",
        context={"user": user, "csrf_token": session_csrf_token(session_token(request))},
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
```

### templates/login.html

```html
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>로그인 | 작은 쇼핑몰</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body>
    <main class="card" aria-labelledby="page-title">
        <p class="brand">작은 쇼핑몰</p>
        <h1 id="page-title">로그인</h1>
        <p class="hint">가입한 이메일과 비밀번호를 입력해 주세요.</p>
        {% if error %}
            <p class="error" role="alert">{{ error }}</p>
        {% endif %}
        <form action="/login" method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <input type="hidden" name="next" value="{{ next_path }}">

            <label for="email">이메일</label>
            <input id="email" name="email" type="email" value="{{ email }}"
                   maxlength="254" autocomplete="username" required>

            <label for="password">비밀번호</label>
            <input id="password" name="password" type="password"
                   autocomplete="current-password" required>

            <button type="submit">로그인</button>
        </form>
        <p class="hint">처음 오셨나요? <a href="/signup">회원가입</a></p>
    </main>
</body>
</html>
```

### templates/account.html

```html
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>회원정보 | 작은 쇼핑몰</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body>
    <main class="card" aria-labelledby="page-title">
        <p class="brand">작은 쇼핑몰</p>
        <h1 id="page-title">회원정보</h1>
        <p><strong>{{ user.name }}</strong>님, 로그인되었습니다.</p>
        <dl>
            <dt>회원 번호</dt>
            <dd>{{ user.id }}</dd>
            <dt>이메일</dt>
            <dd>{{ user.email }}</dd>
        </dl>
        <p class="hint">회원정보 수정과 탈퇴는 다음 학습에서 연결합니다.</p>
        <form action="/logout" method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <button type="submit">로그아웃</button>
        </form>
    </main>
</body>
</html>
```

## 3. 요청 → 처리 → 응답

### ① 로그인

```text
GET /login
    → 로그인 입력 화면 응답

POST /login
    → 폼 확인표(CSRF 토큰) 검사
    → 이메일 정리 및 shop_users 조회
    → 입력 비밀번호와 저장된 bcrypt 해시 비교
    → sessions에 새 세션 저장
    → 브라우저에 HttpOnly 쿠키 설정
    → 검증된 이전 화면 또는 /account로 이동
```

로그인 실패 시에는 이메일 존재 여부와 관계없이 "이메일 또는 비밀번호가 올바르지 않습니다"라고 안내합니다. 없는 이메일도 비교용 해시를 사용해 비밀번호 비교 작업을 수행합니다. 잘못된 입력의 비밀번호는 화면에 다시 채우지 않습니다.

### ② 로그인 유지

로그인 표는 `secrets.token_urlsafe(32)`로 생성합니다. DB에는 이 값의 SHA-256 해시를 저장합니다. 회원 비밀번호 해시인 bcrypt와 용도가 다릅니다.

| 대상 | 처리 |
|---|---|
| 브라우저 | shop_session 쿠키에 원본 토큰 저장 |
| sessions | user_id, token_hash, created_at, expires_at 저장 |
| 서버 | 받은 쿠키를 해시로 바꿔 DB 세션과 대조 |

세션은 발급 시점부터 **7일간 유효**하며, 화면을 볼 때마다 만료일을 늘리지는 않습니다. 만료되거나 탈퇴한 회원이면 다시 로그인해야 합니다. 같은 브라우저에서 다시 로그인하면 이전 쿠키에 해당하는 세션을 삭제하고 새 값을 발급합니다. 다른 브라우저의 유효한 세션은 유지합니다.

쿠키는 HttpOnly, SameSite=Lax로 설정하며 HTTPS 요청에서는 Secure를 사용합니다. 로컬 학습 주소는 HTTP이므로 Secure를 끄고 사용합니다. 배포 단계에서는 HTTPS와 프록시 설정을 함께 확인할 예정입니다.

### ③ 회원정보 접근과 이전 화면 복귀

```text
비로그인 사용자가 /account 요청
    → /login?next=%2Faccount로 이동
    → 로그인 성공
    → /account로 복귀
```

`%2F`는 URL 안에서 `/`를 표현하는 방식입니다. `next=/account`와 같은 목적입니다.

`next`는 사용자 입력이므로 서버가 다시 검사합니다. 현재 경로는 `/account`, `/products/3`처럼 영문·숫자·슬래시·밑줄·하이픈으로 된 내부 경로만 허용합니다. 상품 주소는 이후 단계에서 구현합니다.

- `https://example.com`, `//example.com` 같은 외부 주소는 거부합니다.
- 역슬래시, 제어문자, 인코딩된 경로 우회도 경로 허용 규칙으로 차단합니다.
- `/login`, `/logout`으로 다시 복귀해 반복 이동하는 경로도 제외합니다.
- 허용하지 않는 값은 `/account`로 대체합니다.

`/account`는 쿠키에 저장된 회원정보를 그대로 믿지 않습니다. 요청할 때 DB에서 유효한 세션과 회원을 조회하므로 다른 회원 번호를 URL에 넣어 회원정보를 보는 구조가 아닙니다.

### ④ 로그아웃

```text
회원정보 화면에서 로그아웃 버튼 클릭
    → POST /logout
    → 해당 세션의 폼 확인표 검사
    → sessions에서 현재 토큰의 해시를 가진 행 삭제
    → 커밋
    → 브라우저의 shop_session 쿠키 삭제
    → 로그인 화면으로 이동
```

로그아웃은 GET 링크가 아닌 POST 폼으로 처리합니다. 세션에 연결한 확인표로 요청을 검사합니다. 로그아웃은 현재 브라우저의 세션만 제거하며 회원과 주문 데이터는 삭제하지 않습니다.

DB 작업이 실패하면 로그아웃 완료로 안내하지 않고 오류를 반환합니다. 회원정보 화면에는 `Cache-Control: no-store`를 설정하며, 로그아웃 후 새로고침하거나 회원정보 주소로 다시 접속하면 인증을 다시 확인합니다.

## 4. 직접 실행·확인하는 방법

### ① 서버 다시 시작

서버 터미널에서 `Ctrl + C`로 종료한 뒤, 기존 가상환경에서 실행합니다. 이번에 추가 설치할 패키지는 없습니다.

```powershell
python -m uvicorn app.main:app --reload
```

아래 내용은 직접 확인할 기준입니다. 제가 실행해서 얻은 결과가 아닙니다.

### ② 로그인 화면 열기

[로그인 화면](http://127.0.0.1:8000/login)을 열고, 앞서 실제로 가입한 이메일과 학습용 비밀번호를 입력합니다. `.env`의 DB 비밀번호가 아닌 **쇼핑몰 회원가입 때 입력한 비밀번호**입니다.

로그인 후 [회원정보 화면](http://127.0.0.1:8000/account)으로 이동하고 본인의 이름·이메일이 표시되는지 확인합니다.

### ③ Supabase에서 세션 확인

Table Editor에서 `sessions`를 엽니다.

- 로그인한 회원의 `user_id`가 있는지 확인합니다.
- `token_hash`는 64자리 문자열이며 원본 쿠키 값과 다릅니다.
- `expires_at`이 생성 시점보다 약 7일 뒤인지 확인합니다. 표시 시간대는 Supabase 화면 설정에 따라 다를 수 있습니다.

토큰·비밀번호·해시를 복사해 채팅에 보내지 않아도 됩니다. DB는 브라우저에서 직접 연결하지 않으며 기존 `users` 대신 `shop_users`를 사용합니다.

### ④ 로그아웃 확인

회원정보 화면의 **로그아웃** 버튼을 누릅니다. 로그인 화면으로 이동하는지, `sessions`에서 해당 로그인 행이 삭제됐는지 확인합니다. Table Editor는 새로고침해야 변경이 보일 수 있습니다.

### ⑤ 비로그인 접근과 자동 복귀 확인

1. 로그아웃한 상태에서 [회원정보 주소](http://127.0.0.1:8000/account)를 직접 엽니다.
2. 주소가 `/login?next=...`로 바뀌는지 확인합니다.
3. 다시 로그인합니다.
4. 회원정보 화면으로 돌아오는지 확인합니다.

### ⑥ 잘못된 비밀번호와 외부 주소 확인

| 시도 | 확인 기준 |
|---|---|
| 잘못된 비밀번호 입력 | 로그인 실패 안내, 세션 생성 안 함 |
| 로그인 후 새로고침 | 이름·이메일 유지 |
| 로그아웃 후 /account 재접속 | 로그인 화면 이동 |
| 로그아웃 상태에서 /login?next=https://example.com 접속 후 로그인 | 외부 사이트로 가지 않고 /account 이동 |

외부 주소 검사 예시: [내부 복귀 제한 확인](http://127.0.0.1:8000/login?next=https://example.com). 이 주소 자체는 로컬 서버이며, 허용하지 않는 복귀 값은 서버가 `/account`로 대체합니다.

서버·DB 오류는 상세 접속정보가 드러나지 않게 일반 메시지를 표시합니다. 오류가 나면 접속 주소와 비밀정보를 제외한 메시지를 알려주세요.

## 5. 피드백 질문

먼저 로그인에 성공하고 회원정보 화면에 이름·이메일이 보이는지 확인해 주세요.

1. 로그인 화면이 열리나요?
2. 가입한 정보로 로그인하면 회원정보가 보이나요?
3. 로그아웃 후 회원정보를 열면 다시 로그인 화면으로 이동하나요?

확인 결과를 받기 전에는 회원정보 수정·탈퇴로 넘어가지 않습니다.

## 참고

- [Starlette 공식 문서: 쿠키 설정과 삭제](https://starlette.dev/responses/)
- [FastAPI 공식 문서: 비밀번호 비교와 더미 해시](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [Psycopg 공식 문서: 트랜잭션과 연결 컨텍스트](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)

이번 학습에서는 JWT를 도입하지 않고 DB 세션 방식을 유지합니다. DB에 남은 만료 세션을 주기적으로 청소하거나 로그인 시도 횟수를 제한하는 운영 기능은 이번 구현에 포함하지 않았습니다. 로그인 시에는 해당 회원의 만료 세션을 정리합니다.
