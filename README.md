# 작은 쇼핑몰 — FastAPI 학습 프로젝트

비전공자가 회원·상품·장바구니·주문·모의 결제의 흐름을 단계별로 익히기 위한 프로젝트입니다.

## 사용 기술

- Python, FastAPI, Uvicorn
- Supabase PostgreSQL, Psycopg
- Jinja2, HTML, CSS
- bcrypt 비밀번호 해시, HttpOnly 쿠키와 DB 세션
- Render 배포 설정

React·Node.js·번들러를 사용하지 않습니다. 실제 PG 결제는 포함하지 않습니다.

## 로컬 실행

프로젝트 폴더에서 기존에 사용하는 가상환경을 선택한 뒤 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

최초 환경 구성과 `.env` 작성은 [STEP 2 안내](docs/step-02-server-setup.md)를 참고하세요. `.env.example`은 공유용 양식이며 실제 비밀번호는 `.env`에만 저장합니다. 로컬 HTTP에서는 COOKIE_SECURE를 false로 사용합니다.

주요 주소:

| 주소 | 내용 |
|---|---|
| /products | 상품 목록 |
| /signup · /login | 회원가입·로그인 |
| /account | 회원정보 |
| /cart | 장바구니 |
| /orders | 주문·구매내역 |
| /docs | API 설명 |
| /health · /health/db | 서버·DB 연결 확인 |

## DB 구성

이 프로젝트의 회원 테이블은 **shop_users**입니다. 이전부터 사용하던 users는 사용하지 않습니다.

SQL은 Supabase SQL Editor에서 사용자가 직접 실행합니다. 서버가 시작할 때 자동 실행하지 않습니다.

- 새 DB: 001_create_tables.sql → 002_seed_products.sql
- STEP 5 이전에 생성한 DB: 003_order_checkout_key.sql 추가 실행
- 기존 빈 이미지 경로를 DB에도 저장: 004_product_images.sql 선택 실행

현재 001에는 checkout_key가 포함되어 있으므로 새 DB에 003을 추가 실행할 필요는 없습니다. 기존 테이블이 있는 DB에서 001을 다시 실행하거나 테이블을 삭제하지 마세요.

## 학습 문서

| 순서 | 문서 |
|---|---|
| 설계 | [테이블 정의·ERD·구매 흐름](docs/table-definition.md), [Mermaid 원본](docs/erd.mmd) |
| STEP 2 | [서버와 DB 연결](docs/step-02-server-setup.md) |
| STEP 3-1 | [회원가입](docs/step-03-01-signup.md) |
| STEP 3-2 | [로그인·로그아웃](docs/step-03-02-login-logout.md) |
| STEP 3-3 | [회원정보 수정·탈퇴](docs/step-03-03-profile-withdraw.md) |
| STEP 4 | [상품 조회](docs/step-04-products.md) |
| STEP 5 | [장바구니·주문](docs/step-05-shopping.md) |
| 추가 작업 | [상품 사진](docs/product-photos.md), [따뜻한 디자인](docs/design-warm.md) |
| STEP 6 | [모의 결제·주문내역](docs/step-06-payments-history.md) |
| STEP 7 | [반응형 점검](docs/step-07-responsive.md) |
| STEP 8 | [Render 배포·최종 확인](docs/step-08-render.md) |

단계별 문서의 코드는 해당 단계의 설명입니다. 이후 단계에서 수정한 파일은 현재 프로젝트 파일을 기준으로 확인합니다.

## Render 배포

배포 대상은 [mall_render_test](https://github.com/hichayu00/mall_render_test)입니다. 이 저장소에는 프로젝트 내용을 최상위에 배치하므로 Render의 **Root Directory는 빈칸**으로 둡니다. 상세 설정은 [STEP 8](docs/step-08-render.md)을 참고하세요.

- Build: `python -m pip install -r requirements.txt`
- Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`
- Python: 3.15.2
- HTTPS 쿠키: Render 환경변수 COOKIE_SECURE=true
- DB 설정: 실제 값을 Render 환경변수로 입력

위 시작 명령은 Render용입니다. 로컬에서는 앞의 --reload 명령을 사용합니다.

## 확인 상태

로컬 기능과 화면은 학습 과정에서 사용자가 직접 실행해 확인했습니다. 에이전트는 애플리케이션·테스트·SQL을 실행하지 않았습니다. Render 파일은 준비했으며 실제 배포와 공개 주소의 최종 확인은 아직 남아 있습니다.
