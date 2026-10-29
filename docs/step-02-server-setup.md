# STEP 2 — FastAPI 서버와 Supabase 연결

## 1. 이번 단계의 목표

STEP 1에서 DB에 표를 만들고 상품을 넣었습니다. 이제 브라우저의 요청을 받아 DB와 대화할 **FastAPI 서버**를 준비합니다.

서버가 응답하는지, 서버가 Supabase의 상품 수를 읽을 수 있는지 직접 확인합니다. 화면 디자인과 회원 기능은 이후 단계에서 다룹니다. 아래 코드는 실행하거나 테스트하지 않았습니다.

### 용어부터 이해하기

| 용어 | 쉬운 설명 |
|---|---|
| 서버 | 브라우저의 요청을 받고 처리하는 프로그램 |
| FastAPI | 파이썬으로 서버를 만드는 데 사용하는 도구 |
| Uvicorn | FastAPI 프로그램을 실행하여 요청을 받을 수 있게 하는 도구 |
| 가상환경 | 이 프로젝트에 필요한 파이썬 도구를 따로 담아 두는 폴더 |
| 환경변수 | DB 주소·비밀번호 같은 설정을 코드 밖에서 전달하는 값 |
| JSON | 이름과 값을 짝지어 응답하는 텍스트 형식. 이번 확인 화면에서 보게 됩니다. |

Windows PowerShell과 **Python 3.12 이상**이 설치된 환경을 가정합니다. Node.js는 사용하지 않습니다. Python이 없거나 다른 버전이라면 설치를 진행하기 전에 알려주세요.

## 2. 파일 목록과 전체 코드

이번에 만든 파일입니다. `.env`는 실제 접속정보를 넣기 위해 사용자가 직접 복사해 만듭니다.

```text
Day12-demo/
├─ .gitignore
├─ .env.example
├─ requirements.txt
├─ app/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ database.py
│  └─ main.py
├─ docs/
│  └─ step-02-server-setup.md
└─ sql/
   ├─ 001_create_tables.sql
   └─ 002_seed_products.sql
```

기존 문서와 SQL은 그대로 있습니다. 빈 화면 폴더는 미리 만들지 않습니다. 화면 단계에서는 Jinja2 템플릿으로 HTML을 제공할 예정입니다. 서버에서 로그인 여부와 상품 데이터를 HTML에 넣을 수 있어 별도의 프론트엔드 데이터 처리 코드를 줄일 수 있습니다.

### `.gitignore`

Git으로 공유하지 않을 파일과 폴더의 목록입니다. 특히 비밀번호가 들어가는 `.env`를 제외합니다. 이 파일은 이미 공유한 비밀정보를 지워 주는 도구는 아닙니다.

```gitignore
.venv/
__pycache__/
*.py[cod]
.env
.env.*
!.env.example
.pytest_cache/
```

### `.env.example`

실제 비밀값이 없는 설정 양식입니다. `.env`로 복사한 뒤 값을 바꿉니다.

```dotenv
# Supabase의 Connect → Session pooler에 표시되는 접속정보를 설정한다.
# 아래 값은 예시이므로 실제 정보로 바꾼다.
DB_HOST=your-session-pooler-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD="replace-with-your-database-password"
```

### `requirements.txt`

설치할 파이썬 도구 목록입니다. 버전 범위는 허용할 버전의 범위이며, 실제 설치 버전을 고정한 파일은 아닙니다.

```text
fastapi>=0.115,<1.0
uvicorn>=0.30,<1.0
psycopg[binary]>=3.2,<4.0
pydantic-settings>=2.0,<3.0
```

| 도구 | 역할 |
|---|---|
| fastapi | 요청 주소와 처리 함수 연결 |
| uvicorn | 서버 실행 |
| psycopg[binary] | 파이썬에서 PostgreSQL에 연결 |
| pydantic-settings | .env와 환경변수를 읽고 설정 형식 확인 |

### `app/__init__.py`

```python
# app 폴더를 파이썬 패키지로 사용한다.
```

### `app/config.py`

접속정보를 읽는 파일입니다. `SecretStr`은 설정 객체를 표시할 때 비밀번호가 그대로 드러나는 일을 줄여 줍니다. DB에 연결할 때만 실제 값을 꺼냅니다.

```python
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = Field(min_length=1)
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "postgres"
    db_user: str = Field(min_length=1)
    db_password: SecretStr = Field(min_length=1)


@lru_cache
def get_settings() -> Settings:
    # 설정을 처음 사용할 때 읽고 재사용한다.
    return Settings()
```

### `app/database.py`

접속정보를 받아 DB 연결을 만드는 파일입니다. 비밀번호를 연결 URL에 합치지 않으므로 URL용 문자 변환 과정은 필요하지 않습니다. 연결과 SQL의 대기 시간을 제한합니다.

```python
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
```

### `app/main.py`

주소별로 어떤 일을 할지 정의합니다. `/health/db`는 상품 수만 읽으며 데이터를 추가하거나 수정하지 않습니다.

```python
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.database import get_connection


app = FastAPI(title="학습용 쇼핑몰")


@app.get("/")
def home():
    return {"message": "학습용 쇼핑몰 서버입니다."}


@app.get("/health")
def server_health():
    return {"status": "ok"}


@app.get("/health/db")
def database_health():
    try:
        # 연결은 처리가 끝나면 자동으로 닫힌다.
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM public.products")
                product_count = cursor.fetchone()[0]
    except (psycopg.Error, ValidationError):
        # DB 접속정보와 상세 오류를 응답에 노출하지 않는다.
        raise HTTPException(
            status_code=503,
            detail="DB 연결 또는 설정을 확인해 주세요.",
        ) from None

    return {"status": "ok", "product_count": product_count}
```

## 3. 요청 → 처리 → 응답

```text
브라우저에서 /health 접속
    → FastAPI가 서버 확인 함수를 실행
    → 상태를 JSON으로 응답

브라우저에서 /health/db 접속
    → .env에서 DB 설정 읽기
    → Supabase PostgreSQL에 연결
    → products의 상품 수 조회
    → 연결 종료
    → 상태와 상품 수를 JSON으로 응답
```

`/health`는 DB 없이도 확인할 수 있습니다. `/health/db`까지 확인되어야 서버와 DB가 함께 연결된 것입니다. 이 단계의 연결 확인 주소는 학습용이며, 이후에도 회원정보나 비밀번호를 응답에 포함하지 않습니다.

## 4. 직접 실행·확인하기

### ① VSCode 터미널 열기

VSCode의 **터미널 → 새 터미널**을 엽니다. 아래 명령은 Supabase SQL Editor가 아니라 **PowerShell 터미널**에서 실행합니다.

```powershell
cd C:\AIO4_lesson_\ai4_section01\Day12-demo
python --version
```

Python 3.12 이상인지 확인합니다. `python`을 찾지 못하거나 다른 버전이라면 표시 내용을 알려주세요.

### ② 가상환경 만들고 도구 설치하기

각 명령을 한 줄씩 실행합니다. 가상환경을 활성화하는 대신 그 안의 Python을 직접 지정하므로 PowerShell 실행 정책을 바꿀 필요가 없습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.venv`는 이번 프로젝트 전용 도구 상자라고 생각하면 됩니다. 설치가 끝나면 VSCode의 `Ctrl + Shift + P` → `Python: Select Interpreter`에서 `.venv`의 Python을 선택하면 편집기에서도 같은 환경을 사용합니다. 해당 메뉴는 VSCode Python 확장이 설치된 경우 사용할 수 있습니다.

### ③ .env 만들기

아래 명령은 최초 한 번 실행합니다. 이미 직접 만든 `.env`가 있다면 복사하지 말고 기존 파일을 편집하세요.

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

VSCode에서 `.env`를 열고 실제 접속정보로 교체합니다. 비밀번호는 채팅으로 보내지 마세요.

### ④ Supabase 접속정보 입력하기

Supabase 프로젝트의 **Connect → Session pooler**에서 값을 확인합니다. Session pooler는 IPv4 환경에서도 사용할 수 있어 이번 로컬 학습 환경의 기본 연결 방식으로 선택합니다.

| .env 항목 | 넣을 값 |
|---|---|
| DB_HOST | Session pooler의 Host. 주소만 입력하며 https://는 붙이지 않음 |
| DB_PORT | Session pooler의 Port. 일반적으로 5432이며 화면의 실제 값 사용 |
| DB_NAME | Database. 일반적으로 postgres |
| DB_USER | User. 일반적으로 postgres.프로젝트식별자 형태이며 화면의 실제 값 사용 |
| DB_PASSWORD | 프로젝트 생성 때 정한 DB 비밀번호. Supabase 로그인 비밀번호나 API 키가 아님 |

비밀번호의 바깥 따옴표는 `.env` 문법입니다. `#`나 `$` 같은 문자는 따옴표 안에 그대로 입력할 수 있습니다. 비밀번호 자체에 큰따옴표나 역슬래시가 포함되어 입력 방법이 헷갈리면 실제 비밀번호를 보내지 말고 해당 문자 종류만 알려주세요.

이번 단계는 DB에 직접 연결하므로 Supabase URL, anon key, service_role key를 입력하지 않습니다. 이 접속정보는 FastAPI 서버에서만 사용하고 브라우저 코드에 넣지 않습니다.

### ⑤ 서버 시작하기

프로젝트 루트에서 실행하고 터미널을 열어 둡니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`app.main:app`은 `app/main.py`의 `app` 객체를 실행하라는 뜻입니다. `--reload`는 파이썬 코드를 수정했을 때 개발 서버를 다시 읽게 합니다. `.env`를 바꿨을 때는 `Ctrl + C`로 서버를 중지한 뒤 위 명령으로 다시 시작하세요.

### ⑥ 브라우저에서 확인하기

아래 표는 직접 확인할 기준입니다. 제가 실행해서 얻은 결과가 아닙니다.

| 접속 URL | 확인할 내용 |
|---|---|
| [기본 주소](http://127.0.0.1:8000/) | 학습용 쇼핑몰 서버라는 안내 메시지 |
| [서버 확인](http://127.0.0.1:8000/health) | status가 ok |
| [DB 확인](http://127.0.0.1:8000/health/db) | status가 ok, 샘플 상품만 있다면 product_count가 5 |
| [API 설명 화면](http://127.0.0.1:8000/docs) | 이번에 만든 세 주소가 표시됨 |

서버 종료는 터미널에서 `Ctrl + C`입니다.

### 문제가 생기면

| 상황 | 먼저 확인할 부분 |
|---|---|
| 브라우저가 연결할 수 없음 | 서버 명령이 실행 중인지, 터미널에 시작 오류가 있는지 |
| /health는 되지만 /health/db는 503 | .env 파일명, Session pooler 접속정보, DB 비밀번호, Supabase 프로젝트 상태 |
| 설정을 바꿨는데 같은 문제가 계속됨 | 서버를 중지했다가 다시 실행했는지 |
| 주소를 이미 사용 중이라는 오류 | 다른 터미널에서 8000번 서버가 실행 중인지 |

DB 연결 오류는 상세 접속정보가 노출되지 않도록 일반 메시지로 응답합니다. 해결되지 않으면 접속 주소와 화면 메시지를 먼저 알려주세요. 연결 문자열과 비밀번호는 보내지 마세요.

## 5. 피드백 질문

1. Python 버전 확인과 도구 설치가 완료됐나요?
2. `/health`와 `/health/db`가 각각 열리나요?
3. DB 확인 화면에서 상품 수가 5로 나오나요?

어느 지점이든 어려우면 그 단계에서 멈추고 질문해 주세요. 확인 결과를 받기 전에는 STEP 3으로 넘어가지 않습니다.

## 참고 문서

- [Supabase: PostgreSQL 연결과 Session pooler](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [FastAPI: 환경변수와 설정 파일](https://fastapi.tiangolo.com/advanced/settings/)

이번 작업에서는 파일만 작성했습니다. 패키지 설치, 서버 실행, SQL 실행, DB 접속, 테스트는 수행하지 않았습니다.
