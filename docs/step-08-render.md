# STEP 8 — Render 배포 설정과 최종 확인

## 1. 이번 단계의 목표

로컬 PC에서 실행한 쇼핑몰을 Render 서버에서 실행할 수 있도록 설정합니다. PC가 꺼져 있어도 Render가 서버를 실행하면 다른 기기에서 공개 주소로 접속할 수 있습니다.

**Render 배포 설정 파일과 안내를 준비한 상태입니다.** 패키지 설치·코드 실행·테스트·SQL 실행·Render 서비스 생성·실제 배포는 하지 않았습니다. GitHub 업로드는 별도 사용자 요청으로 지정한 mall_render_test 저장소에 진행하며, 실제 공개 주소의 생성과 확인은 아직 남아 있습니다.

학습용으로 Free Web Service를 사용하는 경로를 설명합니다. 실제 선택 가능한 플랜과 조건은 서비스 생성 화면에서 확인하세요. 기존 Git 저장소의 origin에 업로드할 권한이 있고 Render에서 해당 저장소를 연결할 수 있다는 점을 가정합니다.

### 처음 보는 용어

| 용어 | 쉬운 설명 |
|---|---|
| Git | 코드 변경 이력을 남기는 도구 |
| GitHub 저장소 | 코드를 온라인에 보관하는 장소 |
| Commit | 변경 내용을 이력에 기록하는 것 |
| Push | 로컬 이력을 GitHub 같은 원격 저장소로 보내는 것 |
| Render Web Service | 파이썬 서버를 실행하는 서비스 |
| Build Command | 서버 실행 전에 필요한 도구를 설치하는 명령 |
| Start Command | 서버를 켜는 명령 |
| Root Directory | 저장소 중 앱이 들어 있는 시작 폴더 |
| 환경변수 | 서버에 코드와 별도로 전달하는 설정값 |
| Health Check | 서버가 응답하는지 주기적으로 확인할 주소 |

## 2. 생성·수정 파일과 전체 코드

| 파일 | 작업 | 역할 |
|---|---|---|
| render.yaml | 생성 | Render 설정을 파일로 기록 |
| .python-version | 생성 | 사용할 Python 버전 명시 |
| .env.example | 정리 | 실제 값이 없는 공유용 양식과 COOKIE_SECURE 설명 |
| app/config.py | 수정 | COOKIE_SECURE 환경변수 읽기 |
| app/routers/accounts.py | 수정 | 회원가입 확인표 쿠키에 HTTPS 설정 적용 |
| app/routers/auth.py | 수정 | 로그인 확인표·세션 쿠키에 HTTPS 설정 적용 |
| README.md | 생성 | 프로젝트 실행 방법과 학습 문서 목록 |

실제 접속정보가 들어 있는 `.env`는 읽거나 수정하지 않았습니다. `.gitignore`는 기존에 `.env`·가상환경을 제외하고 있으므로 유지합니다. 공유용 `.env.example`은 실제 비밀값이 없는 양식으로 정리했습니다.

### render.yaml

배포 대상은 [mall_render_test](https://github.com/hichayu00/mall_render_test)입니다. 로컬에서는 상위 수업 저장소 안의 Day12-demo에 있지만, 배포 저장소에는 이 프로젝트 내용만 최상위에 배치합니다. 따라서 render.yaml에서 rootDir을 생략하고 Render 화면의 Root Directory를 빈칸으로 둡니다.

```yaml
services:
  - type: web
    name: small-cozy-shop
    runtime: python
    plan: free
    buildCommand: python -m pip install -r requirements.txt
    startCommand: >-
      python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
      --proxy-headers --forwarded-allow-ips '*'
    healthCheckPath: /health
    autoDeployTrigger: "off"
    envVars:
      - key: PYTHON_VERSION
        value: "3.15.2"
      - key: COOKIE_SECURE
        value: "true"
      - key: DB_HOST
        sync: false
      - key: DB_PORT
        value: "5432"
      - key: DB_NAME
        value: postgres
      - key: DB_USER
        sync: false
      - key: DB_PASSWORD
        sync: false
```

`sync: false`인 값은 Blueprint 생성 시 Render 화면에서 직접 입력합니다. 비밀번호를 파일에 넣지 않습니다. `autoDeployTrigger: off`는 이후 푸시마다 자동 배포하지 않고 수동으로 배포하도록 한 설정입니다. 최초 서비스 생성 자체는 배포를 시작합니다. [Render Blueprint 공식 문서](https://render.com/docs/blueprint-spec)

이 파일은 자동으로 실행되지 않습니다. 아래의 수동 Web Service 설정 경로를 먼저 사용하고, 파일로 설정하는 Blueprint 방식은 선택사항입니다. 두 방식으로 서비스를 중복 생성하지 마세요.

### .python-version

```text
3.15.2
```

사용자가 확인한 로컬 Python은 3.15.0입니다. 배포는 같은 3.15 계열의 패치 버전인 3.15.2를 지정했습니다. 공식 릴리스 여부를 확인했으며, 이 프로젝트를 해당 버전의 Render Linux 환경에서 실행해 검증한 것은 아닙니다. Render 환경변수의 `PYTHON_VERSION`을 같은 값으로 지정해 버전 선택을 명확히 합니다. [Python 3.15.2 공식 릴리스](https://www.python.org/downloads/release/python-3152/), [Render 버전 설정](https://render.com/docs/python-version)

이 파일을 추가해도 이미 만든 로컬 가상환경의 Python이 자동으로 바뀌지는 않습니다.

### .env.example

```dotenv
# 공유용 양식이다. 실제 접속정보는 .env에만 입력한다.
DB_HOST=your-session-pooler-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD="replace-with-your-database-password"

# 로컬 HTTP에서는 false, Render HTTPS에서는 환경변수로 true를 설정한다.
COOKIE_SECURE=false
```

기존 `.env`에 COOKIE_SECURE가 없어도 기본값 false이므로 로컬 실행을 유지합니다.

### app/config.py — Settings에 추가

```python
cookie_secure: bool = False
```

### app/routers/accounts.py — import와 쿠키 설정 변경

```python
from app.config import BASE_DIR, get_settings
```

signup_page의 set_cookie에서 secure 인자를 변경했습니다.

```python
secure=get_settings().cookie_secure or request.url.scheme == "https",
```

### app/routers/auth.py — import와 두 쿠키 설정 변경

```python
from app.config import BASE_DIR, get_settings
```

login_page의 login_csrf와 로그인 성공 시 shop_session을 설정하는 두 곳 모두 아래 secure 값을 사용합니다.

```python
secure=get_settings().cookie_secure or request.url.scheme == "https",
```

나머지 로그인·세션·CSRF·주문·결제 로직은 유지합니다. README 전체 내용은 [프로젝트 안내](../README.md)에서 확인할 수 있습니다.

## 3. 요청 → 처리 → 응답

```text
휴대폰·PC에서 Render 공개 HTTPS 주소 접속
    → Render 프록시가 요청을 앱 서버에 전달
    → Uvicorn이 FastAPI 실행
    → FastAPI가 Supabase를 조회·변경
    → HTML·JSON·정적 이미지 응답
```

Render의 PORT 환경변수로 전달된 포트에서 `0.0.0.0`에 연결을 열어야 외부 요청을 받을 수 있습니다. 로컬 개발용 `--reload`는 배포 명령에 넣지 않습니다. [Render FastAPI 배포 안내](https://render.com/docs/deploy-fastapi), [Web Service 안내](https://render.com/docs/web-services)

`--proxy-headers`는 HTTPS 같은 원래 요청 정보를 전달받는 설정입니다. `--forwarded-allow-ips '*'`는 Render 프록시를 통해서 요청을 받는 배포 구성을 전제로 합니다. 일반 로컬 서버에서는 기존 실행 명령을 유지하세요. 신뢰할 프록시를 지정하는 옵션의 의미는 [Uvicorn 공식 설정](https://uvicorn.dev/settings/)을 참고했습니다.

Render에는 `COOKIE_SECURE=true`를 설정해 로그인 쿠키와 CSRF 쿠키를 HTTPS 연결에서 사용합니다. 정적 파일 주소도 https로 생성되는지 최종 확인합니다.

## 4. 직접 배포·확인하는 방법

### ① GitHub 프로젝트 확인

사용자가 지정한 배포 저장소는 [hichayu00/mall_render_test](https://github.com/hichayu00/mall_render_test)입니다. 기존 수업 저장소의 원격 주소와 이력을 변경하지 않고, 쇼핑몰 프로젝트 내용만 별도의 임시 체크아웃을 통해 업로드합니다.

GitHub 저장소의 최상위에서 `app`, `templates`, `static`, `sql`, `docs`, `requirements.txt`, `render.yaml`이 보이는지 확인합니다. `Day12-demo`라는 상위 폴더 안에 다시 넣는 구조가 아닙니다. 실제 `.env`와 가상환경은 업로드 대상에서 제외하며, `.env.example`에는 예시 값만 포함합니다.

업로드에 사용하는 브랜치는 `codex/initial-shop`입니다. Render에서 같은 브랜치를 선택합니다. 기존 수업 저장소의 origin으로 push하는 이전 안내는 이 배포 저장소에 적용하지 않습니다.

### ② Render에서 Web Service 만들기

[Render 대시보드](https://dashboard.render.com/)에 로그인하고 **New → Web Service**를 선택합니다. GitHub를 연결하고 mall_render_test 저장소와 codex/initial-shop 브랜치를 선택합니다.

| 항목 | 입력할 내용 |
|---|---|
| Name | small-cozy-shop 또는 원하는 서비스 이름 |
| Language / Runtime | Python 3 |
| Root Directory | **빈칸** |
| Build Command | 아래 빌드 명령 |
| Start Command | 아래 시작 명령 |
| Health Check Path | /health |
| Instance Type | 학습용 Free가 제공되는 경우 Free 선택 |
| Auto Deploy | Off 또는 수동 배포 |
| Region | 사용 중인 Supabase DB와 가까운 제공 지역 선택 |

빌드 명령:

```bash
python -m pip install -r requirements.txt
```

시작 명령:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'
```

이 두 명령은 **Render 화면의 해당 입력란**에 넣습니다. `$PORT`는 Render가 설정하므로 Windows PowerShell에 그대로 실행하는 로컬 명령이 아닙니다.

현재 mall_render_test는 프로젝트 내용이 최상위에 있는 구조이므로 Root Directory는 빈칸입니다. 파일의 rootDir도 생략했습니다. 나중에 다른 상위 저장소의 Day12-demo 하위 폴더를 배포하는 경우에만 Root Directory를 Day12-demo로 지정합니다. [Render 하위 폴더 배포 안내](https://render.com/docs/monorepo-support)

### ③ 환경변수 입력

Environment 또는 Advanced의 환경변수 입력란에 다음 값을 넣습니다. 실제 값은 로컬 `.env`에서 확인해 직접 입력하고 채팅이나 GitHub 파일에 붙이지 않습니다.

| Key | Value |
|---|---|
| PYTHON_VERSION | 3.15.2 |
| COOKIE_SECURE | true |
| DB_HOST | Supabase Session pooler의 실제 Host |
| DB_PORT | Session pooler의 실제 Port. 기존 설정은 5432 |
| DB_NAME | 기존 Database 값. 일반적으로 postgres |
| DB_USER | Session pooler의 실제 User |
| DB_PASSWORD | 현재 DB 비밀번호 |

Render 환경변수 입력란에는 **값 자체만** 넣습니다. `.env`에서 비밀번호를 감싸던 큰따옴표는 복사하지 않습니다. 연결 URL이 아니라 별도 필드로 전달하므로 비밀번호를 URL용으로 변환하지 않습니다.

Session pooler는 IPv4 연결에도 사용할 수 있습니다. 기존 로컬 연결과 같은 Supabase 프로젝트를 사용합니다. 별도 Render PostgreSQL 데이터베이스를 만들거나 테이블 생성 SQL을 다시 실행할 필요는 없습니다. [Supabase PostgreSQL 연결 공식 문서](https://supabase.com/docs/guides/database/connecting-to-postgres)

PORT는 Render가 제공하므로 위 표에 추가하지 않아도 됩니다. Supabase anon key나 service_role key도 이번 DB 직접 연결 방식에는 필요하지 않습니다.

### ④ 서비스 생성과 로그 확인

설정과 환경변수를 확인한 뒤 사용자가 **Create Web Service**를 누르면 빌드와 배포가 시작됩니다. Render 로그에서 패키지 설치와 서버 시작을 확인합니다.

빌드·배포가 성공하면 서비스 화면의 실제 HTTPS 주소를 엽니다. 안내에 임의의 주소를 실제 발급 주소처럼 적지 않았습니다. `small-cozy-shop`을 선택해도 이름 중복 등에 따라 실제 주소가 다를 수 있으므로 화면의 URL을 사용하세요.

### ⑤ 공개 주소에서 최종 확인

아래 목록은 모두 **확인 대기**입니다. 지금까지 사용자가 확인한 로컬 결과와 Render 배포 결과를 구분합니다.

- [ ] /health에서 status가 ok인지
- [ ] /health/db에서 status가 ok이고 상품 수가 표시되는지
- [ ] /products에서 상품 사진·가격·품절 표시가 나오는지
- [ ] 상품 상세에서 이미지·수량·버튼이 정상인지
- [ ] 회원가입과 로그인, 새로고침 후 로그인 유지가 되는지
- [ ] 로그아웃 후 /account·/cart·/orders 접근 시 로그인 화면으로 이동하는지
- [ ] 로그인 성공 후 이전 내부 화면으로 돌아오는지
- [ ] 장바구니 담기·수량 변경·삭제가 되는지
- [ ] 주문서와 바로 구매로 결제 대기 주문을 만들 수 있는지
- [ ] 모의 결제 실패 시 재고 유지, 성공 시 재고 차감·상품 목록 이동이 되는지
- [ ] 구매내역과 결제 시도 기록을 확인할 수 있는지
- [ ] 회원정보 수정·비밀번호 변경·별도 학습용 계정 탈퇴가 되는지
- [ ] 브라우저 쿠키의 shop_session에 HttpOnly·Secure가 설정되는지
- [ ] 휴대폰에서 공개 HTTPS 주소를 열어 메뉴·상품·주문 화면을 읽을 수 있는지

쿠키는 Edge 개발자 도구의 Application → Cookies에서 속성 열만 확인하면 됩니다. 토큰 값을 복사하거나 스크린샷으로 공유하지 않습니다. 로컬 쿠키와 Render 도메인의 쿠키는 별개이므로 공개 주소에서는 다시 로그인해야 합니다.

Health Check는 `/health`로 서버 응답만 확인합니다. 이것이 성공해도 DB 연결까지 보장하지는 않으므로 `/health/db`를 별도로 확인해야 합니다. [Render Health Check 공식 문서](https://render.com/docs/health-checks)

### ⑥ 학습용 배포에서 알아둘 점

- Free Web Service는 일정 시간 요청이 없으면 중지되고 다음 접속 때 시작에 시간이 걸릴 수 있습니다. 현재 공식 문서는 15분 유휴 후 중지, 재시작은 약 1분으로 설명합니다. 정확한 플랜 조건은 Render 화면과 공식 문서를 확인하세요. [Render Free 안내](https://render.com/docs/free)
- GitHub에 포함한 상품 사진은 배포할 때 함께 복사됩니다. 실행 중 서버 폴더에 나중에 올린 파일은 재배포·재시작 후 유지되는 저장소가 아닙니다. 향후 업로드 기능은 별도 저장소로 설계합니다. [Render 파일시스템 안내](https://render.com/docs/free)
- DB와 세션은 Supabase에 있으므로 Render 재시작만으로 삭제되지는 않습니다.
- 로컬과 Render가 같은 Supabase를 쓰므로 배포 주소의 모의 결제도 같은 재고를 변경합니다.
- 현재 requirements.txt는 버전 범위입니다. 설치된 정확한 버전의 고정 파일을 생성하거나 Linux에서 호환성을 테스트한 것은 아닙니다.
- 학습용 구현이며 실제 PG·이메일 인증·비밀번호 재설정·환불·관리자 화면은 포함하지 않습니다.

### ⑦ 문제가 생겼을 때

| 증상 | 먼저 확인할 내용 |
|---|---|
| requirements.txt를 못 찾음 | mall_render_test의 최상위에 파일이 있는지, Root Directory가 빈칸인지 |
| app 모듈을 못 찾음 | 업로드 폴더 구조와 시작 명령의 app.main:app |
| 포트를 못 찾음 | --host 0.0.0.0, --port $PORT가 있는지 |
| 패키지 설치 실패 | PYTHON_VERSION과 빌드 로그의 마지막 오류 |
| /health는 되지만 DB가 503 | DB 환경변수, Session pooler 설정, Supabase 프로젝트 상태 |
| 로그인이 유지되지 않음 | 공개 주소가 HTTPS인지, COOKIE_SECURE=true, 쿠키 속성과 프록시 옵션 |
| 이미지가 안 나옴 | static/images/products가 GitHub에 올라갔는지, 경로의 대소문자가 맞는지 |
| 수정한 코드가 반영되지 않음 | 올바른 브랜치에 push했는지, Auto Deploy Off라면 Manual Deploy를 실행했는지 |

오류를 공유할 때는 비밀번호·토큰·연결 문자열을 제외하고 어느 단계에서 어떤 메시지가 나왔는지 알려주세요.

### 선택: Blueprint 방식

수동 Web Service 대신 설정 파일을 사용하고 싶다면 New → Blueprint에서 저장소를 연결하고 Blueprint 파일 경로를 **render.yaml**로 지정합니다. 현재 배포 저장소에는 해당 파일이 최상위에 있습니다. 생성 화면에서 DB_HOST·DB_USER·DB_PASSWORD를 입력합니다. [Render Blueprint 공식 문서](https://render.com/docs/blueprint-spec)

처음 학습에서는 위 수동 설정 경로 하나로 진행하면 충분합니다.

## 5. 피드백 질문

먼저 **GitHub의 mall_render_test 최상위에서 app·templates·static 파일이 보이는지** 확인해 주세요.

- GitHub 업로드까지 완료됐나요?
- Git push 오류가 있거나 Render 저장소 연결 화면을 찾기 어렵나요?
- 이미 Render 설정 화면을 열었다면 어느 단계까지 진행했나요?

공개 배포와 최종 확인은 아직 남아 있습니다. 사용자의 진행 결과를 받아 함께 마무리합니다.
