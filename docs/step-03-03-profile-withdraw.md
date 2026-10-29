# STEP 3-3 — 회원정보 수정과 탈퇴

## 1. 이번 단계의 목표

로그인한 회원이 자신의 이름·이메일·비밀번호를 수정하고 탈퇴할 수 있도록 구현합니다. **현재 비밀번호**를 확인한 후에만 처리합니다.

이 부분까지 확인하면 STEP 3의 회원가입·로그인·로그아웃·인증·정보 수정·탈퇴가 연결됩니다. 상품 기능으로 넘어가기 전에 사용자의 확인을 기다립니다. 이번 작업에서는 파일만 작성했으며 코드·SQL 실행, DB 접속 및 테스트를 하지 않았습니다.

### 비전공자를 위한 핵심 개념

| 개념 | 쉬운 설명 |
|---|---|
| 회원정보 수정 | 회원 명부의 이름·이메일·비밀번호 검증값을 바꾸는 일 |
| 현재 비밀번호 재확인 | 로그인한 상태라도 중요한 변경 전에 본인임을 다시 확인하는 절차 |
| 탈퇴 처리 | 회원 번호는 남기고 개인정보와 로그인 권한을 제거하는 방식 |
| 트랜잭션 | 관련 작업을 한 묶음으로 처리해 모두 저장하거나 모두 되돌리는 것 |
| 행 잠금 | 같은 회원정보를 동시에 바꿀 때 처리가 엇갈리지 않도록 순서를 지키게 하는 것 |

## 2. 생성·수정 파일과 코드

| 파일 | 작업 | 내용 |
|---|---|---|
| app/routers/profile.py | 생성 | 수정·탈퇴 요청 처리 |
| templates/profile.html | 생성 | 수정 화면과 탈퇴 확인 화면 |
| app/main.py | 수정 | profile 라우터 연결 |
| app/routers/auth.py | 수정 | 수정·탈퇴 결과 안내와 이름 수정 완료 표시 |
| templates/account.html | 수정 | 수정·탈퇴 화면으로 가는 링크 |
| templates/login.html | 수정 | 재로그인 또는 탈퇴 완료 안내 |
| static/style.css | 수정 | 성공 안내, 탈퇴 버튼, 확인란 스타일 |
| docs/table-definition.md | 수정 | 회원 수정과 세션 제거 규칙 설명 |

새 테이블이나 컬럼, 패키지, 환경변수는 추가하지 않았습니다. Supabase에서 테이블 생성 SQL을 다시 실행할 필요가 없습니다.

아래에는 새 파일의 전체 코드와 기존 파일의 변경 부분만 정리했습니다.

### app/main.py — 변경 부분

```python
from app.routers import accounts, auth, profile

app.include_router(profile.router)
```

### app/routers/auth.py — 변경 부분

login_page의 context에 아래 안내 매핑을 추가했습니다.

```python
"notice": {
    "profile_updated": "회원정보가 변경되었습니다. 변경한 정보로 다시 로그인해 주세요.",
    "withdrawn": "탈퇴 처리가 완료되었습니다. 회원 개인정보와 로그인 세션을 제거했습니다.",
}.get(request.query_params.get("notice", ""), ""),
```

account 함수는 updated 값을 받아 화면에 전달하도록 바꿨습니다. 아래는 변경된 함수 전체입니다.

```python
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
```

### templates/account.html — 변경 부분

제목 아래에 완료 안내를 추가했습니다.

```html
{% if updated %}
    <p class="success" role="status">회원정보를 수정했습니다.</p>
{% endif %}
```

기존 준비 중 안내를 수정 링크로 교체하고, 로그아웃 폼 아래에 탈퇴 링크를 추가했습니다.

```html
<a class="button" href="/account/edit">회원정보 수정</a>
<!-- 기존 로그아웃 폼 유지 -->
<p class="hint"><a href="/account/withdraw">회원 탈퇴</a></p>
```

### templates/login.html — 추가 부분

```html
{% if notice %}
    <p class="success" role="status">{{ notice }}</p>
{% endif %}
```

### static/style.css — 추가 부분

```css
.success { padding: 12px; background: #eaf6ed; color: #205e32; border-radius: 8px; }
.danger { background: #a52d26; }
.danger:hover { background: #7e211c; }
.check-label { display: flex; align-items: flex-start; gap: 10px; }
.check-label input { width: 22px; min-height: 22px; flex-shrink: 0; }
```

### app/routers/profile.py

```python
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
    hash_session_token,
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


def lock_account(cursor, user_id: int, token: str):
    # 로그인과 같은 순서로 회원을 먼저 잠그고 현재 세션을 다시 확인한다.
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
        WHERE user_id = %s AND token_hash = %s AND expires_at > now()
        FOR UPDATE
        """,
        (user_id, hash_session_token(token)),
    )
    return user if cursor.fetchone() else None


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
```

### templates/profile.html

```html
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ '회원 탈퇴' if mode == 'withdraw' else '회원정보 수정' }} | 작은 쇼핑몰</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body>
    <main class="card" aria-labelledby="page-title">
        <p class="brand">작은 쇼핑몰</p>
        <h1 id="page-title">{{ '회원 탈퇴' if mode == 'withdraw' else '회원정보 수정' }}</h1>
        {% if error %}
            <p class="error" role="alert">{{ error }}</p>
        {% endif %}

        {% if mode == 'withdraw' %}
            <p>탈퇴하면 모든 기기에서 로그아웃되며 기존 계정으로 로그인할 수 없습니다.</p>
            <p class="hint">회원 이름·이메일·비밀번호 해시와 주문 배송정보를 제거합니다. 주문·결제 기록은 유지합니다.</p>
            <form action="/account/withdraw" method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <label for="withdraw-password">현재 비밀번호</label>
                <input id="withdraw-password" name="current_password" type="password"
                       autocomplete="current-password" required>
                <label class="check-label" for="confirm">
                    <input id="confirm" name="confirm" type="checkbox" value="yes" required>
                    <span>안내를 확인했으며 회원 탈퇴에 동의합니다.</span>
                </label>
                <button class="danger" type="submit">탈퇴 확정</button>
            </form>
        {% else %}
            <p class="hint">이메일이나 비밀번호를 바꾸면 모든 기기에서 로그아웃됩니다.</p>
            <form action="/account/edit" method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <label for="name">이름</label>
                <input id="name" name="name" value="{{ user.name }}" type="text"
                       maxlength="50" autocomplete="name" required>
                <label for="email">이메일</label>
                <input id="email" name="email" value="{{ user.email }}" type="email"
                       maxlength="254" autocomplete="username" required>
                <label for="current-password">현재 비밀번호</label>
                <input id="current-password" name="current_password" type="password"
                       autocomplete="current-password" required>
                <label for="new-password">새 비밀번호 (선택)</label>
                <input id="new-password" name="new_password" type="password"
                       minlength="8" autocomplete="new-password" aria-describedby="password-help">
                <p class="hint" id="password-help">변경할 때만 8자 이상, 72바이트 이하로 입력하세요. 두 칸을 모두 비우면 기존 비밀번호를 유지합니다.</p>
                <label for="new-password-confirm">새 비밀번호 확인</label>
                <input id="new-password-confirm" name="new_password_confirm" type="password"
                       minlength="8" autocomplete="new-password">
                <button type="submit">수정 내용 저장</button>
            </form>
        {% endif %}
        <p class="hint"><a href="/account">취소하고 회원정보로 돌아가기</a></p>
    </main>
</body>
</html>
```

## 3. 요청 → 처리 → 응답

### ① 수정 화면 열기

`GET /account/edit` → 로그인 세션 확인 → 본인의 이름·이메일이 채워진 화면 응답.

비로그인이라면 로그인 화면으로 이동하고, 로그인 성공 후 수정 화면으로 돌아옵니다. 비밀번호 해시는 화면에 전달하지 않습니다.

### ② 수정 내용 저장하기

`POST /account/edit` → CSRF 확인표 검사 → 이름·이메일·새 비밀번호 검사 → DB에서 현재 회원과 세션 재확인 → 현재 비밀번호 비교 → UPDATE → 결과 화면으로 이동.

| 입력·변경 | 처리 |
|---|---|
| 이름만 변경 | 회원정보 화면으로 이동, 로그인 유지 |
| 이메일 변경 | 중복 검사 후 저장, 모든 세션 삭제, 새 이메일로 재로그인 |
| 새 비밀번호 두 칸 모두 빈 상태 | 기존 비밀번호 해시 유지 |
| 새 비밀번호 입력 | 길이·확인값 검사 후 bcrypt 해시 저장, 모든 세션 삭제, 새 비밀번호로 재로그인 |
| 현재 비밀번호 불일치 | 저장하지 않고 오류 안내 |
| 다른 회원의 이메일 사용 | DB UNIQUE 제약조건으로 막고 오류 안내 |

이메일·비밀번호 변경 시에는 현재 브라우저뿐 아니라 다른 브라우저의 로그인도 해제합니다. 단, 이메일 인증은 기존 학습 범위에서 제외했으므로 주소 형식과 중복만 검사합니다.

오류가 발생하면 이름·이메일은 남기지만 현재 비밀번호와 새 비밀번호 두 칸은 다시 입력해야 합니다. 비밀번호 앞뒤 공백은 임의로 제거하지 않습니다.

### ③ 탈퇴 확인하기

`GET /account/withdraw` → 로그인 확인 → 탈퇴 안내·현재 비밀번호 입력란·동의 확인란 표시.

화면을 열거나 링크를 누르는 것만으로 탈퇴하지 않습니다. 사용자가 현재 비밀번호를 입력하고 확인란을 선택한 뒤 **탈퇴 확정**을 눌러야 POST 요청이 전송됩니다.

### ④ 탈퇴 확정하기

`POST /account/withdraw` → 로그인·CSRF·확인란 검사 → DB에서 회원·세션 재확인 → 현재 비밀번호 비교 → 아래 작업을 한 트랜잭션으로 실행 → 로그인 화면으로 이동.

| 테이블 | 변화 |
|---|---|
| shop_users | email·name·password_hash를 NULL로 변경, deleted_at 저장 |
| orders | 해당 회원의 수령인·전화번호·배송주소를 NULL로 변경 |
| sessions | 해당 회원의 모든 세션 삭제 |
| order_items / payments | 기록 유지 |
| 기존 users | 사용하거나 변경하지 않음 |

회원 행 자체를 삭제하지 않으므로 기존 주문의 회원 번호 연결은 유지합니다. 중간에 DB 오류가 발생하면 위 변경을 모두 롤백합니다. 기록을 보존하는 것과 개인정보를 제거하는 것을 구분한 학습용 설계입니다.

탈퇴 후 같은 이메일로 다시 가입하면 **새 회원 번호**가 부여됩니다. 기존 구매 기록이 새 회원 계정으로 옮겨가지는 않습니다. 개인정보와 비밀번호 해시는 제거하므로 이번 구현에는 탈퇴 복구 기능이 없습니다.

### 주문 기능을 구현할 때 이어갈 규칙

아직 주문 API는 구현하지 않았습니다. 이후 주문 생성·결제에서도 같은 회원 행을 먼저 잠그고 활성 회원·유효한 세션을 재확인해 탈퇴와 주문 처리가 엇갈리지 않게 할 예정입니다.

## 4. 직접 실행·확인하기

### ① 서버 다시 시작

현재 서버를 실행 중인 터미널에서 `Ctrl + C`를 누른 뒤 같은 가상환경에서 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

패키지 설치와 SQL 실행은 필요하지 않습니다. 아래 내용은 사용자가 직접 확인할 기준이며 제가 실행해서 얻은 결과가 아닙니다.

### ② 이름 수정부터 확인

1. [로그인 화면](http://127.0.0.1:8000/login)에서 로그인합니다.
2. [회원정보 화면](http://127.0.0.1:8000/account)의 **회원정보 수정**을 누릅니다.
3. 이름만 바꾸고 현재 비밀번호를 입력합니다.
4. 새 비밀번호와 확인은 모두 비워 둡니다.
5. **수정 내용 저장**을 누릅니다.
6. 로그인 유지 상태에서 바뀐 이름과 수정 완료 안내가 보이는지 확인합니다.

Supabase Table Editor의 `shop_users`에서도 같은 회원 번호의 이름이 바뀌었는지 확인할 수 있습니다.

### ③ 비밀번호 변경 확인

1. 다시 수정 화면을 엽니다.
2. 현재 비밀번호와 새 비밀번호·확인을 입력합니다.
3. 저장 후 로그인 화면으로 이동하는지 확인합니다.
4. 새 비밀번호로 로그인합니다.
5. 이전 비밀번호로는 로그인할 수 없는지 확인합니다.

비밀번호는 실제 다른 서비스에서 쓰는 값 대신 학습용으로 정하세요. 입력한 비밀번호와 해시를 채팅에 보낼 필요는 없습니다.

### ④ 이메일 변경·잘못된 입력 확인

| 확인 항목 | 확인 기준 |
|---|---|
| 새 이메일로 변경 | 로그인 화면 이동 후 새 이메일로 로그인 가능 |
| 잘못된 현재 비밀번호 | 오류 안내, DB 정보 유지 |
| 새 비밀번호 확인 불일치 | 오류 안내, 저장하지 않음 |
| 이미 다른 회원이 쓰는 이메일 | 중복 안내, 기존 정보 유지 |
| 비로그인 상태에서 수정 화면 열기 | 로그인으로 이동, 성공 후 수정 화면 복귀 |

이메일을 바꿨다면 이후 로그인에는 바뀐 이메일을 사용합니다.

### ⑤ 탈퇴는 별도의 학습용 계정으로 확인

주요 학습 계정을 유지하고 싶다면 다른 이메일로 탈퇴 확인용 회원을 하나 가입해 그 회원으로 로그인하세요. 예: `withdraw-study@example.com`.

1. [회원정보 화면](http://127.0.0.1:8000/account)에서 **회원 탈퇴**를 누릅니다.
2. 안내를 읽고 현재 비밀번호와 동의 확인란을 입력합니다.
3. **탈퇴 확정**을 누릅니다.
4. 로그인 화면에 탈퇴 완료 안내가 보이는지 확인합니다.
5. 탈퇴한 계정으로 로그인할 수 없는지 확인합니다.
6. Supabase에서 해당 회원 번호의 행을 찾아 개인정보가 NULL이고 deleted_at이 채워졌는지 확인합니다.
7. `sessions`에서 해당 회원의 세션이 제거됐는지 확인합니다.

현재 주문 기록이 없다면 주문 배송정보 제거는 실제로 확인할 대상이 없습니다. 주문·결제 단계에서 해당 흐름을 다시 다룰 예정입니다.

## 5. 피드백 질문

우선 **이름만 바꿔 저장했을 때 바뀐 이름이 보이는지** 확인해 주세요.

- 수정 화면과 저장이 정상적으로 동작하나요?
- 비밀번호 변경 후 새 비밀번호로 다시 로그인되나요?
- 별도 학습용 계정의 탈퇴도 확인했나요?
- 오류나 이해하기 어려운 부분이 있나요?

확인 결과를 받은 뒤 STEP 4 상품 목록·상세로 넘어갑니다.

## 참고

- [Psycopg 공식 문서: 트랜잭션 처리](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [PostgreSQL 공식 문서: 행 잠금](https://www.postgresql.org/docs/17/explicit-locking.html)

서버 코드를 실행하거나 가상의 실행 결과를 만들지 않았습니다. 문서의 데이터 변화와 확인 항목은 구현 의도와 직접 확인할 기준입니다.
