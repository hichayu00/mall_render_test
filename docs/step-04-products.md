# STEP 4 — 상품 목록·상세 API와 화면

## 1. 이번 단계의 목표

Supabase의 `products`에 저장한 상품을 목록과 상세 화면으로 보여줍니다. 같은 상품을 JSON 데이터로 확인할 수 있는 API도 추가합니다. **로그인하지 않아도 조회할 수 있습니다.**

학습 범위를 작게 유지하기 위해 이번에는 조회만 구현합니다. 장바구니 담기와 바로 구매 버튼은 STEP 5에서 추가합니다. 상품 관리 화면·검색·정렬·페이지 나누기는 이번 범위에서 제외하고 샘플 상품을 한 목록으로 보여줍니다.

SQL·환경변수·패키지 설치는 필요하지 않습니다. 코드 실행·DB 접속·테스트는 하지 않았습니다.

### 화면과 API는 어떻게 다를까요?

| 종류 | 비유 | 주소 예시 | 응답 |
|---|---|---|---|
| 화면 | 사람이 읽기 좋게 꾸민 상품 안내판 | /products | HTML |
| API | 다른 프로그램이 읽을 수 있는 상품 데이터 전달 창구 | /api/products | JSON |

이번 화면은 FastAPI가 Jinja2로 완성한 HTML을 보내는 방식입니다. 브라우저의 JavaScript가 API를 다시 호출하는 구조는 아닙니다. **HTML 화면과 JSON API가 동일한 파이썬 조회 함수를 사용**해 코드가 중복되는 것을 줄입니다.

## 2. 파일 목록과 코드

| 파일 | 작업 | 역할 |
|---|---|---|
| app/routers/products.py | 생성 | 공통 상품 조회, 목록·상세 API와 화면 처리 |
| templates/catalog_base.html | 생성 | 상품 화면에서 공통으로 쓰는 메뉴와 레이아웃 |
| templates/products.html | 생성 | 상품 목록 |
| templates/product_detail.html | 생성 | 상세 및 상품 없음 안내 |
| app/main.py | 수정 | 상품 라우터 연결, 기본 주소를 상품 목록으로 이동 |
| templates/account.html | 수정 | 상품 목록 이동 링크 |
| static/style.css | 수정 | 상품 카드와 반응형 레이아웃 |

현재 상품 데이터에 이미지가 없으므로 **상품 사진 준비 중**이라는 대체 문구를 보여줍니다. 이미지 생성·다운로드는 하지 않았습니다. 나중에 `image_url`에 HTTP(S) 이미지 URL 또는 `/static/`으로 시작하는 정적 파일 경로를 저장하면 이미지로 표시합니다. 외부 이미지 주소가 유효하지 않으면 브라우저에서 이미지가 정상 표시되지 않을 수 있습니다.

아래에는 새 파일 전체 코드와 수정 파일의 변경 부분만 담았습니다.

### app/main.py — 추가·변경 부분

기존 라우터 import와 home 함수를 아래 내용으로 바꾸고 상품 라우터 연결을 추가했습니다.

```python
from fastapi.responses import RedirectResponse
from app.routers import accounts, auth, profile, products

app.include_router(products.router)

@app.get("/")
def home():
    return RedirectResponse("/products", status_code=303)
```

### templates/account.html — 추가한 링크

```html
<p class="hint"><a href="/products">상품 목록으로</a></p>
```

### app/routers/products.py

```python
from typing import Annotated
from urllib.parse import urlsplit

import psycopg
from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row
from pydantic import BaseModel, ValidationError

from app.config import BASE_DIR
from app.database import get_connection
from app.session_auth import current_user


router = APIRouter(tags=["상품"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")
ProductId = Annotated[int, Path(gt=0, le=9_223_372_036_854_775_807)]


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    description: str
    price: int
    stock: int
    image_url: str | None


def read_products(product_id: int | None = None) -> list[dict]:
    # 화면과 API가 같은 조회 함수를 사용한다.
    query = """
        SELECT id, sku, name, description, price, stock, image_url
        FROM public.products WHERE is_active = true
    """
    parameters = ()
    if product_id is not None:
        query += " AND id = %s"
        parameters = (product_id,)
    query += " ORDER BY id"

    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchall()
    except (psycopg.Error, ValidationError):
        raise HTTPException(503, "상품을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.") from None


def image_source(value: str | None) -> str | None:
    if not value or "\\" in value or any(ord(char) <= 32 for char in value):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme in {"http", "https"} and parts.netloc and not parts.username:
        return value
    if value.startswith("/static/"):
        return value
    return None


def product_view(product: dict) -> dict:
    return {**product, "display_image": image_source(product["image_url"])}


@router.get("/api/products", response_model=list[ProductResponse])
def product_list_api():
    return read_products()


@router.get("/api/products/{product_id}", response_model=ProductResponse)
def product_detail_api(product_id: ProductId):
    rows = read_products(product_id)
    if not rows:
        raise HTTPException(404, "상품을 찾을 수 없습니다.")
    return rows[0]


@router.get("/products", response_class=HTMLResponse)
def product_list(request: Request):
    products = [product_view(row) for row in read_products()]
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={"products": products, "user": current_user(request)},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: ProductId):
    rows = read_products(product_id)
    return templates.TemplateResponse(
        request=request,
        name="product_detail.html",
        context={
            "product": product_view(rows[0]) if rows else None,
            "user": current_user(request),
        },
        status_code=200 if rows else 404,
        headers={"Cache-Control": "no-store"},
    )
```

### templates/catalog_base.html

```html
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}상품 목록{% endblock %} | 작은 쇼핑몰</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body class="catalog-body">
    <header class="site-header">
        <a class="site-logo" href="/products">작은 쇼핑몰</a>
        <nav aria-label="주요 메뉴">
            <a href="/products">상품 목록</a>
            {% if user %}
                <a href="/account">회원정보</a>
            {% else %}
                <a href="/login?next={{ request.url.path | urlencode }}">로그인</a>
                <a href="/signup">회원가입</a>
            {% endif %}
        </nav>
    </header>
    <main class="catalog-main">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

### templates/products.html

```html
{% extends "catalog_base.html" %}

{% block title %}상품 목록{% endblock %}

{% block content %}
    <div class="catalog-heading">
        <p class="eyebrow">매일 곁에 두는 물건</p>
        <h1>상품 목록</h1>
        <p class="hint">총 {{ products | length }}개 · 마음에 드는 상품을 자세히 살펴보세요.</p>
    </div>
    {% if products %}
        <div class="product-grid">
            {% for product in products %}
                <article class="product-card">
                    <a class="product-link" href="/products/{{ product.id }}">
                        <div class="product-image">
                            {% if product.display_image %}
                                <img src="{{ product.display_image }}" alt="{{ product.name }}" loading="lazy">
                            {% else %}
                                <span class="image-placeholder">상품 사진 준비 중</span>
                            {% endif %}
                        </div>
                        <div class="product-card-content">
                            {% if product.stock == 0 %}
                                <span class="stock-badge sold-out">품절</span>
                            {% else %}
                                <span class="stock-badge">판매 중</span>
                            {% endif %}
                            <h2>{{ product.name }}</h2>
                            <p class="product-price">{{ "{:,}".format(product.price) }}원</p>
                            <span class="detail-link">상품 자세히 보기 →</span>
                        </div>
                    </a>
                </article>
            {% endfor %}
        </div>
    {% else %}
        <div class="empty-state">
            <h2>아직 등록된 상품이 없습니다.</h2>
            <p>다음에 다시 방문해 주세요.</p>
        </div>
    {% endif %}
{% endblock %}
```

### templates/product_detail.html

```html
{% extends "catalog_base.html" %}

{% block title %}{{ product.name if product else '상품을 찾을 수 없습니다' }}{% endblock %}

{% block content %}
    <p class="back-link"><a href="/products">← 상품 목록으로</a></p>
    {% if product %}
        <article class="product-detail">
            <div class="product-image detail-image">
                {% if product.display_image %}
                    <img src="{{ product.display_image }}" alt="{{ product.name }}">
                {% else %}
                    <span class="image-placeholder">상품 사진 준비 중</span>
                {% endif %}
            </div>
            <div class="product-detail-content">
                <p class="eyebrow">상품 코드 {{ product.sku }}</p>
                <h1>{{ product.name }}</h1>
                <p class="product-price detail-price">{{ "{:,}".format(product.price) }}원</p>
                {% if product.stock == 0 %}
                    <p class="stock-badge sold-out">품절 · 현재 구매할 수 없습니다.</p>
                {% else %}
                    <p class="stock-badge">재고 {{ product.stock }}개</p>
                {% endif %}
                <h2 class="section-title">상품 설명</h2>
                <p class="product-description">{{ product.description or '등록된 상품 설명이 없습니다.' }}</p>
            </div>
        </article>
    {% else %}
        <div class="empty-state">
            <h1>상품을 찾을 수 없습니다.</h1>
            <p>상품이 없거나 판매가 중단되었습니다. 목록에서 다른 상품을 확인해 주세요.</p>
            <a class="button" href="/products">상품 목록 보기</a>
        </div>
    {% endif %}
{% endblock %}
```

### static/style.css — 추가한 부분

```css
/* 상품 화면은 회원 입력 폼과 별도의 넓은 레이아웃을 사용한다. */
.catalog-body { padding: 0; }
.site-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px 24px;
    max-width: 1200px;
    margin: 0 auto;
    padding: 16px;
    border-bottom: 1px solid #dce2ea;
}
.site-logo { color: #20346f; font-size: 1.2rem; font-weight: 800; text-decoration: none; }
.site-header nav { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.site-header nav a { display: inline-flex; align-items: center; min-height: 44px; color: #35435d; }
.catalog-main { max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }
.catalog-heading { margin-bottom: 24px; }
.eyebrow { color: #526078; font-size: 0.85rem; letter-spacing: 0.04em; }
.product-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; }
.product-card { overflow: hidden; min-width: 0; border: 1px solid #dce2ea; border-radius: 16px; background: #fff; }
.product-link { display: block; height: 100%; color: inherit; text-decoration: none; }
.product-link:hover h2 { text-decoration: underline; }
.product-image { display: grid; place-items: center; aspect-ratio: 4 / 3; overflow: hidden; background: #e8edf4; }
.product-image img { width: 100%; height: 100%; object-fit: cover; }
.image-placeholder { padding: 16px; color: #58667a; font-size: 0.9rem; text-align: center; }
.product-card-content { padding: 20px; }
.product-card h2 { margin: 12px 0 8px; font-size: 1.15rem; overflow-wrap: anywhere; }
.product-price { margin: 8px 0; font-size: 1.2rem; font-weight: 800; }
.stock-badge { display: inline-block; margin: 0; padding: 4px 10px; border-radius: 6px; background: #eaf6ed; color: #205e32; font-size: 0.85rem; }
.sold-out { background: #f2e8e6; color: #8b3027; }
.detail-link { display: inline-block; margin-top: 12px; color: #2849b8; font-size: 0.9rem; }
.back-link { margin: 0 0 24px; }
.back-link a { display: inline-flex; align-items: center; min-height: 44px; color: #35435d; }
.product-detail { display: grid; grid-template-columns: minmax(0, 1fr); overflow: hidden; border: 1px solid #dce2ea; border-radius: 16px; background: #fff; }
.product-detail-content { min-width: 0; padding: 24px; }
.product-detail h1 { overflow-wrap: anywhere; }
.detail-price { margin: 16px 0; font-size: 1.8rem; }
.section-title { margin-top: 28px; font-size: 1.05rem; }
.product-description { white-space: pre-line; overflow-wrap: anywhere; }
.empty-state { padding: 32px 20px; border: 1px solid #dce2ea; border-radius: 16px; background: #fff; }
.empty-state .button { max-width: 280px; }

@media (min-width: 600px) {
    .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (min-width: 768px) {
    .site-header { padding: 20px 24px; }
    .catalog-main { padding: 40px 24px 64px; }
    .product-detail { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-items: start; }
    .product-detail-content { padding: 32px; }
}

@media (min-width: 1024px) {
    .product-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```

## 3. 요청 → 처리 → 응답

### ① 상품 목록

```text
GET /products
    → products에서 is_active = true인 상품 조회
    → ID 순서로 정렬
    → 상품명·가격·품절 표시를 HTML에 채움
    → 목록 화면 응답
```

재고가 0인 상품도 목록에서 보여주되 품절로 표시합니다. `is_active = false`는 판매를 중단한 상품이므로 목록에서 제외합니다.

### ② 상품 상세

```text
상품 카드 클릭
    → GET /products/실제상품번호
    → 해당 번호의 판매 중인 상품 조회
    → 상품명·코드·설명·가격·재고 표시
```

상품이 없거나 판매가 중단된 경우 HTTP 404와 함께 안내 화면을 보여줍니다. HTTP 404는 요청한 대상을 찾지 못했다는 뜻입니다. 상품 번호는 양수이며 PostgreSQL bigint 범위 이내여야 합니다. 숫자가 아니거나 범위가 잘못된 요청은 FastAPI가 HTTP 422로 거부합니다.

### ③ API로 조회

```text
GET /api/products 또는 /api/products/실제상품번호
    → 같은 조회 함수로 products 읽기
    → ProductResponse에 정의한 상품 필드만 JSON으로 응답
```

API는 회원정보나 비밀번호를 포함하지 않습니다. 없는 상품의 상세 API는 HTTP 404와 한국어 메시지를 반환합니다. DB 오류는 접속정보를 노출하지 않고 HTTP 503으로 안내합니다.

### ④ 로그인 상태와 메뉴

- 비로그인: 상품 목록·로그인·회원가입 링크 표시
- 로그인: 상품 목록·회원정보 링크 표시
- 상품 화면의 로그인 링크: 현재 상품 화면을 `next`에 담고 로그인 후 돌아옴
- 회원정보 화면: 상품 목록 링크 추가

상품 조회 자체는 로그인을 요구하지 않습니다. 로그인 쿠키가 있으면 메뉴 표시를 위해 유효한 세션인지 확인합니다. 이 단계는 조회만 하므로 재고·주문·결제 데이터는 변경하지 않습니다.

기본 주소 `/`도 이제 JSON 안내 대신 `/products`로 이동합니다. 기존 `/health`, `/health/db`, `/docs`는 유지합니다.

### ⑤ 모바일 우선 레이아웃

| 화면 폭 | 상품 목록 | 상세 화면 |
|---|---|---|
| 600px 미만 | 1열 | 이미지 아래 상품정보 |
| 600px 이상 | 2열 | 768px 미만은 세로 배치 유지 |
| 768px 이상 | 2열 | 이미지·상품정보를 나란히 배치 |
| 1024px 이상 | 3열 | 나란히 배치 유지 |

`@media`는 화면 폭에 따라 CSS 규칙을 바꾸는 문법입니다. 먼저 좁은 화면을 위한 1열 규칙을 만들고, 넓어질 때 2열·3열 규칙을 추가했습니다. 실제 기기에서의 최종 점검은 STEP 7에서도 다룹니다.

## 4. 직접 실행·확인하기

### ① 서버 다시 시작

기존 서버 터미널에서 `Ctrl + C`로 종료한 뒤 같은 가상환경에서 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

새로 설치할 도구와 실행할 SQL은 없습니다. 아래 항목은 사용자가 직접 확인할 기준이며 제가 실행해서 얻은 결과가 아닙니다.

### ② 상품 목록과 상세 화면

1. [상품 목록](http://127.0.0.1:8000/products)을 엽니다.
2. 샘플 상품을 그대로 유지했다면 5개가 보이는지 확인합니다.
3. 머그컵 가격이 12,000원인지 확인합니다.
4. 재고가 0인 텀블러에 **품절**이 표시되는지 확인합니다.
5. 상품 카드를 눌러 상세 화면을 엽니다.
6. 상품명·설명·가격·재고가 해당 상품과 맞는지 확인합니다.
7. **상품 목록으로** 링크를 눌러 목록으로 돌아옵니다.

ID는 DB의 실제 값을 사용하므로 상세 주소를 임의로 1번이라고 가정하지 않습니다. 카드를 누르면 올바른 번호로 이동합니다.

### ③ 비로그인 조회와 로그인 복귀

1. 회원정보에서 로그아웃하거나 시크릿 창을 엽니다.
2. `/products`와 상품 상세에 접속할 수 있는지 확인합니다.
3. 상품 상세 화면의 **로그인**을 누릅니다.
4. 로그인 성공 후 같은 상품 상세로 돌아오는지 확인합니다.

시크릿 창은 기존 브라우저의 로그인 쿠키를 공유하지 않는 별도 창입니다. 이 확인은 브라우저에서 직접 진행합니다.

### ④ API 확인

[상품 목록 API](http://127.0.0.1:8000/api/products)를 열어 JSON 데이터가 표시되는지 확인합니다. 화면과 달리 목록이 꾸며지지 않은 텍스트로 보이는 것이 정상입니다.

상세 API는 위 JSON의 실제 `id`를 사용해 `/api/products/해당번호`로 접속합니다. 예시의 상품 번호를 실제 조회 결과처럼 가정하지 않습니다.

[API 설명 화면](http://127.0.0.1:8000/docs)에서도 `/api/products`와 `/api/products/{product_id}`를 확인할 수 있습니다.

### ⑤ 화면 폭 확인

브라우저 창을 좁혔다 넓히거나 개발자 도구의 기기 모드를 사용합니다.

- 390px 정도: 목록 1열, 상세 세로 배치
- 768px 정도: 목록 2열, 상세 가로 배치
- 1200px 정도: 목록 3열
- 가로 스크롤 없이 이름·가격·메뉴를 읽을 수 있는지 확인

등록 상품이 없을 때는 빈 목록 안내가, 없는 상품의 상세는 상품을 찾을 수 없다는 안내가 표시되도록 작성했습니다. 이 상태를 확인하기 위해 기존 데이터를 삭제할 필요는 없습니다.

## 5. 피드백 질문

우선 **상품 목록 → 카드 클릭 → 상세 화면**까지 확인해 주세요.

1. 상품 5개와 텀블러의 품절 표시가 보이나요?
2. 카드를 누르면 해당 상품 상세가 보이나요?
3. 좁은 화면에서도 내용을 읽기 편한가요?
4. 오류나 바꾸고 싶은 부분이 있나요?

확인 결과를 받은 뒤 STEP 5의 장바구니·주문 기능으로 진행합니다.

## 참고

- [FastAPI 공식 문서: 응답 모델](https://fastapi.tiangolo.com/tutorial/response-model/)
- [FastAPI 공식 문서: Jinja2 템플릿](https://fastapi.tiangolo.com/advanced/templates/)
- [Psycopg 공식 문서: dict_row](https://www.psycopg.org/psycopg3/docs/advanced/rows.html)
