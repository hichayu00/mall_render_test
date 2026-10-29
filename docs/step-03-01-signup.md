# STEP 3-1 — 회원가입

## 1. 이번 단계의 목표

회원가입 화면에서 이름·이메일·비밀번호를 입력받아 `shop_users` 테이블에 저장합니다. 비밀번호는 원문 대신 bcrypt 해시로 바꾸어 저장합니다.

STEP 3 전체 중 **회원가입만** 다룹니다. 회원가입 후 자동 로그인하지 않습니다. 이메일 인증과 비밀번호 재설정은 기존 합의대로 제외합니다. 코드·SQL 실행, 패키지 설치, DB 변경 및 테스트는 수행하지 않았습니다.

### 쉽게 이해하기

- **HTML 폼**: 이름과 비밀번호 등을 적는 신청서입니다.
- **GET**: 신청서 화면을 보여 달라는 요청입니다.
- **POST**: 작성한 신청서를 서버에 제출하는 요청입니다.
- **Jinja2**: HTML 양식에 안내 문구와 오류 메시지 등을 채우는 도구입니다.
- **라우터**: 회원 기능의 주소와 처리 함수를 따로 모아 둔 파일입니다.
- **해시**: 비밀번호를 검증용 값으로 변환한 결과입니다. 로그인 때 저장한 해시와 입력한 비밀번호가 맞는지 검사하며, 원래 비밀번호를 복원해 비교하지 않습니다.

## 2. 생성·수정 파일과 코드

| 파일 | 작업 | 역할 |
|---|---|---|
| requirements.txt | 수정 | 화면·폼·해시·이메일 검사 도구 추가 |
| app/main.py | 수정 | 정적 파일과 회원 라우터 연결 |
| app/security.py | 생성 | 비밀번호 해시와 폼 확인 토큰 처리 |
| app/routers/__init__.py | 생성 | 라우터 폴더의 패키지 표시 |
| app/routers/accounts.py | 생성 | 가입 화면·입력 검사·회원 저장 |
| templates/signup.html | 생성 | 회원가입과 완료 화면 |
| static/style.css | 생성 | 모바일 우선 화면 스타일 |

기존 SQL과 `.env`는 수정할 필요가 없습니다. 기존 `users` 테이블은 사용하지 않으며, **`shop_users`에만 회원을 추가**합니다.

아래에는 수정된 파일의 변경 부분과 새 파일의 전체 코드를 담았습니다.

### requirements.txt — 추가한 부분

```text
jinja2>=3.1,<4.0
python-multipart>=0.0.20,<1.0
bcrypt>=4.2,<6.0
email-validator>=2.2,<3.0
```

### app/main.py — 추가한 부분

아래 import와 app 생성 뒤의 연결 구문을 추가했습니다. 기존 세 요청 처리 함수는 그대로입니다.

```python
from fastapi.staticfiles import StaticFiles
from app.config import BASE_DIR
from app.routers import accounts

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(accounts.router)
```

### app/security.py

```python
import secrets

import bcrypt


def hash_password(password: str) -> str:
    # 무작위 salt를 포함한 bcrypt 해시만 DB에 저장한다.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def is_valid_csrf_token(cookie_token: str | None, form_token: str) -> bool:
    # 쿠키와 폼의 토큰이 일치하는지 비교한다.
    if not cookie_token or not form_token or len(form_token) > 128:
        return False
    return secrets.compare_digest(
        cookie_token.encode("utf-8"), form_token.encode("utf-8")
    )
```

### app/routers/__init__.py

```python
# 기능별 요청 처리 코드를 모은다.
```

### app/routers/accounts.py

```python
from typing import Annotated

import psycopg
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.config import BASE_DIR
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
        secure=request.url.scheme == "https",
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
```

### templates/signup.html

```html
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>회원가입 | 작은 쇼핑몰</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body>
    <main class="card" aria-labelledby="page-title">
        <p class="brand">작은 쇼핑몰</p>
        {% if completed %}
            <h1 id="page-title">회원가입 완료</h1>
            <p>회원가입이 완료되었습니다.</p>
            <p class="hint">로그인 기능은 다음 학습에서 연결합니다. 현재는 자동 로그인되지 않습니다.</p>
            <a class="button" href="/signup">회원가입 화면으로</a>
        {% else %}
            <h1 id="page-title">회원가입</h1>
            <p class="hint">쇼핑을 시작할 회원정보를 입력해 주세요.</p>

            {% if error %}
                <p class="error" role="alert">{{ error }}</p>
            {% endif %}

            <form action="/signup" method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

                <label for="name">이름</label>
                <input id="name" name="name" type="text" value="{{ name }}"
                       maxlength="50" autocomplete="name" required>

                <label for="email">이메일</label>
                <input id="email" name="email" type="email" value="{{ email }}"
                       maxlength="254" autocomplete="email" required>

                <label for="password">비밀번호</label>
                <input id="password" name="password" type="password"
                       minlength="8" autocomplete="new-password"
                       aria-describedby="password-help" required>
                <p id="password-help" class="hint">8자 이상, 72바이트 이하로 입력하세요. 영문·숫자는 보통 한 글자에 1바이트입니다.</p>

                <label for="password-confirm">비밀번호 확인</label>
                <input id="password-confirm" name="password_confirm" type="password"
                       minlength="8" autocomplete="new-password" required>

                <button type="submit">가입하기</button>
            </form>
        {% endif %}
    </main>
</body>
</html>
```

### static/style.css

```css
/* 모바일 화면을 기본으로 하고 넓은 화면에서 여백을 늘린다. */
* { box-sizing: border-box; }

body {
    margin: 0;
    padding: 24px 16px;
    background: #f3f5f8;
    color: #172033;
    font-family: system-ui, "Malgun Gothic", sans-serif;
    line-height: 1.6;
}

.card {
    width: 100%;
    max-width: 460px;
    margin: 0 auto;
    padding: 24px;
    background: #fff;
    border: 1px solid #dce2ea;
    border-radius: 16px;
}

.brand { margin-top: 0; color: #354fb0; font-weight: 700; }
h1 { margin: 8px 0; font-size: 1.75rem; }
.hint { margin: 8px 0 16px; color: #526078; font-size: 0.9rem; }
label { display: block; margin-top: 16px; font-weight: 600; }

input {
    width: 100%;
    min-height: 48px;
    margin-top: 6px;
    padding: 10px 12px;
    border: 1px solid #8794a8;
    border-radius: 8px;
    font: inherit;
    background: #fff;
}

button, .button {
    display: block;
    width: 100%;
    min-height: 48px;
    margin-top: 24px;
    padding: 12px;
    border: 0;
    border-radius: 8px;
    background: #2849b8;
    color: #fff;
    font: inherit;
    font-weight: 700;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
}

button:hover, .button:hover { background: #1c378f; }
:focus-visible { outline: 3px solid #b25200; outline-offset: 3px; }
.error { padding: 12px; background: #fff0ee; color: #9a251b; border-radius: 8px; }

@media (min-width: 768px) {
    body { padding-top: 64px; }
    .card { padding: 32px; }
}
```

## 3. 요청 → 처리 → 응답

### ① 회원가입 화면 열기

브라우저가 `GET /signup` 요청 → 서버가 Jinja2로 HTML 작성 → 이름·이메일·비밀번호 입력 화면 응답.

다른 사이트가 임의로 가입 폼을 제출하는 일을 줄이기 위해, 폼과 쿠키에 무작위 확인표인 CSRF 토큰을 넣고 제출할 때 두 값이 맞는지 확인합니다. 이것은 로그인 세션과는 별개의 값입니다.

### ② 가입하기 누르기

브라우저가 `POST /signup` 요청 → 입력 검사 → 비밀번호 해시 생성 → DB INSERT → 저장 성공 후 완료 화면으로 이동.

```text
입력한 이름 ────────────────→ shop_users.name
입력한 이메일 → 공백 정리·소문자화 → shop_users.email
입력한 비밀번호 → bcrypt 해시 ───→ shop_users.password_hash
```

비밀번호 확인 값과 CSRF 토큰은 회원 테이블에 저장하지 않습니다. 비밀번호 앞뒤 공백은 임의로 제거하지 않습니다.

| 검사 | 처리 |
|---|---|
| 이름 | 앞뒤 공백 제거 후 1~50자 |
| 이메일 | 주소 형식 확인, 앞뒤 공백 제거 및 소문자 저장 |
| 비밀번호 | 8자 이상, UTF-8 기준 72바이트 이하, NUL 문자 제외 |
| 비밀번호 확인 | 비밀번호와 같아야 함 |
| 같은 이메일 | DB의 UNIQUE 제약조건으로 중복 저장 방지 |

바이트는 글자가 컴퓨터에 저장될 때 차지하는 크기의 단위입니다. 영어·숫자는 보통 1글자에 1바이트이고, 한글은 보통 3바이트입니다. bcrypt의 입력 제한 때문에 글자 수 외에 바이트 수도 검사합니다. 너무 긴 비밀번호를 잘라 저장하지 않습니다.

### ③ 저장 성공 또는 오류

- 성공하면 DB 연결 구간을 벗어날 때 커밋하여 저장을 확정합니다.
- DB 작업 중 오류가 발생하면 해당 트랜잭션을 롤백합니다.
- 이메일 중복 등 오류는 같은 입력 화면에 한국어로 표시합니다.
- 오류가 나면 이름·이메일은 남기되 비밀번호 두 칸은 다시 입력하도록 비웁니다.
- 성공 후 303 이동 응답으로 완료 화면을 열어 새로고침 시 POST가 재전송되는 일을 피합니다.
- 이번에는 로그인하지 않으므로 `sessions`에는 데이터가 생기지 않습니다.

완료 주소를 직접 입력해서 화면을 여는 것만으로는 회원이 생성되지 않습니다. 실제 회원 생성은 가입 폼을 제출해 DB 저장이 성공했을 때 이루어집니다.

## 4. 직접 실행·확인하는 방법

### ① 서버 중지

서버가 실행 중인 VSCode 터미널에서 `Ctrl + C`를 누릅니다.

### ② 새 도구 설치

기존에 서버 실행에 성공했던 **같은 가상환경의 터미널**에서 다음 명령을 순서대로 실행합니다. 이번에는 실행이 확인된 `python` 명령을 사용합니다.

```powershell
cd C:\AIO4_lesson_\ai4_section01\Day12-demo
python -m pip install -r requirements.txt
```

새로 추가한 도구는 Jinja2, python-multipart, bcrypt, email-validator입니다. Node.js는 필요하지 않습니다. 설치 오류가 나오면 중간에서 멈추고 오류 메시지를 알려주세요.

### ③ 서버 다시 시작

```powershell
python -m uvicorn app.main:app --reload
```

시작 오류가 없으면 터미널을 그대로 두고 브라우저를 엽니다.

### ④ 회원가입 화면 확인

[회원가입 화면 열기](http://127.0.0.1:8000/signup)

이전 기본 주소 `/`는 서버 안내 JSON 화면으로 유지됩니다. 회원가입은 `/signup`에서 확인합니다.

입력 예시입니다. 실제 본인 비밀번호를 사용하지 말고 학습용 비밀번호를 정해서 입력하세요.

| 입력란 | 예시 |
|---|---|
| 이름 | 학습회원 |
| 이메일 | student@example.com |
| 비밀번호 | 직접 정한 학습용 비밀번호. 영문·숫자 조합 8자 이상 권장 |
| 비밀번호 확인 | 같은 비밀번호 다시 입력 |

가입하기를 누른 뒤 완료 화면으로 이동하는지 확인합니다. 이메일 주소는 발송 없이 형식만 확인합니다.

### ⑤ Supabase에서 저장 확인

Supabase의 Table Editor → `public` → **`shop_users`**를 엽니다.

- 입력한 이름과 이메일이 있는지 확인합니다.
- `password_hash`가 입력한 비밀번호와 다른 긴 문자열인지 확인합니다. bcrypt를 사용하므로 일반적으로 `$2b$`로 시작합니다.
- `created_at`이 채워지고 `deleted_at`은 비어 있는지 확인합니다.
- 기존 `users`가 아닌 `shop_users`에서 확인하세요.

DB 비밀번호, 가입 비밀번호, 전체 해시를 채팅으로 보내지 않아도 됩니다. 해시는 브라우저 응답에 포함하지 않습니다.

### ⑥ 잘못된 입력 확인

아래는 사용자가 직접 확인할 항목이며 제가 테스트해서 얻은 결과가 아닙니다.

| 시도 | 확인할 동작 |
|---|---|
| 같은 이메일로 다시 가입 | 이미 가입된 이메일이라는 안내, 중복 회원은 생성하지 않음 |
| 비밀번호 확인을 다르게 입력 | 불일치 안내, 회원은 생성하지 않음 |
| 비밀번호 8자 미만 | 브라우저에서 입력 제한. 서버도 동일 조건 검사 |
| 화면 폭을 좁혀 보기 | 입력란·버튼이 화면 폭에 맞고 가로 스크롤이 생기지 않는지 확인 |

입력 오류만 검사하려면 중복 이메일 대신 아직 가입하지 않은 이메일로 진행하세요. 오류를 수정할 때는 비밀번호 두 칸을 다시 입력합니다.

## 5. 피드백 질문

먼저 **도구 설치 → 서버 시작 → `/signup` 화면 표시**까지 진행해 주세요.

1. 회원가입 화면이 보이나요?
2. 가입 후 `shop_users`에 학습회원이 추가됐나요?
3. 오류가 있다면 어느 단계에서 어떤 메시지가 나왔나요?

확인 결과를 받기 전에는 로그인 구현으로 넘어가지 않습니다.

## 참고

- [FastAPI 공식 문서: Jinja2 템플릿](https://fastapi.tiangolo.com/advanced/templates/)
- [FastAPI 공식 문서: 폼 입력 처리](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/)
- [bcrypt 공식 패키지 설명: 해시 생성과 72바이트 제한](https://pypi.org/project/bcrypt/)

현재 파일은 작성만 완료한 상태입니다. 실제 설치·실행·테스트 결과는 사용자의 확인을 통해 판단합니다.
