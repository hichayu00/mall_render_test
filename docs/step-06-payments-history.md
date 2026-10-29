# STEP 6 — 모의 결제와 주문·구매내역

## 1. 이번 단계의 목표

STEP 5에서 만든 결제 대기 주문을 **모의 결제 성공 또는 실패**로 처리합니다. 회원정보와 상품 메뉴에서 본인의 주문·구매내역을 조회할 수 있도록 연결합니다.

실제 PG나 카드 입력은 없습니다. 이번에는 테이블·환경변수·패키지를 추가하지 않으며 기존 `payments` 테이블을 사용합니다. 코드·서버·SQL을 실행하거나 테스트하지 않았으며 DB 데이터도 직접 변경하지 않았습니다.

### 주문과 결제는 왜 다를까요?

| 개념 | 쉬운 설명 | 테이블 |
|---|---|---|
| 주문 | 무엇을 몇 개, 얼마에 살지 확정한 구매 목록 | orders + order_items |
| 결제 | 그 주문의 대금 처리가 성공했는지 남기는 기록 | payments |
| 주문내역 | 결제 대기와 구매 완료를 함께 확인하는 목록 | 본인 orders 조회 |
| 구매내역 | 그중 결제가 완료된 주문 | orders.status = paid |

결제를 한 번 실패하고 다시 성공하면 **주문은 하나, 결제 시도는 두 개**입니다. 실패 기록을 없애고 성공으로 덮어쓰지 않습니다.

## 2. 생성·수정 파일과 전체 코드

| 파일 | 작업 | 역할 |
|---|---|---|
| app/payments.py | 생성 | 결제 트랜잭션, 중복 방지, 주문내역 조회 |
| app/routers/payments.py | 생성 | 모의 결제 화면·API, 주문내역 화면·API |
| templates/payment.html | 생성 | 모의 결제 성공·실패 선택 |
| templates/orders.html | 생성 | 전체·대기·구매 완료 목록 |
| app/main.py | 수정 | 결제 라우터 연결 |
| app/shopping.py | 수정 | 주문 상세에 결제 시도 기록 포함 |
| app/routers/products.py | 수정 | 결제 완료 안내 전 본인 성공 주문인지 확인 |
| templates/order.html | 수정 | 결제 버튼과 결제 시도 기록 표시 |
| templates/products.html | 수정 | 상품 목록의 결제 완료 안내 |
| 공통 메뉴·회원정보 HTML | 수정 | 주문내역 링크 추가 |
| static/style.css | 수정 | 주문내역 필터·카드 스타일 |

수정한 파일 전체를 반복하지 않고 바뀐 부분만 설명합니다. 신규 파일은 전체 코드를 담았습니다.

### app/payments.py

```python
from fastapi import HTTPException

from app.shopping import member_cursor


def record_payment(cursor, order, key, status, reason=None):
    cursor.execute(
        """
        INSERT INTO public.payments (order_id, idempotency_key, status, amount, failure_reason)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, order_id, status, amount, failure_reason, created_at
        """,
        (order["id"], key, status, order["total_amount"], reason),
    )
    return cursor.fetchone()


def pay_order(user_id: int, token: str, order_id: int, key, outcome: str):
    if outcome not in {"success", "failure"}:
        raise HTTPException(400, "모의 결제 결과를 확인해 주세요.")
    with member_cursor(user_id, token) as cursor:
        # 회원·세션 다음으로 주문을 잠가 중복 결제를 직렬로 처리한다.
        cursor.execute(
            """
            SELECT id, status, total_amount FROM public.orders
            WHERE id = %s AND user_id = %s AND status <> 'cart' FOR UPDATE
            """,
            (order_id, user_id),
        )
        order = cursor.fetchone()
        if not order:
            raise HTTPException(404, "주문을 찾을 수 없습니다.")

        cursor.execute(
            """
            SELECT id, order_id, status, amount, failure_reason, created_at
            FROM public.payments WHERE idempotency_key = %s
            """,
            (key,),
        )
        existing = cursor.fetchone()
        if existing:
            if existing["order_id"] != order_id:
                raise HTTPException(409, "다른 주문에서 사용한 결제 요청 번호입니다.")
            # 같은 키는 성공·실패 선택을 바꿔도 최초 결과를 그대로 반환한다.
            return existing

        if order["status"] == "paid":
            cursor.execute(
                """
                SELECT id, order_id, status, amount, failure_reason, created_at
                FROM public.payments WHERE order_id = %s AND status = 'succeeded'
                """,
                (order_id,),
            )
            completed = cursor.fetchone()
            if not completed:
                raise HTTPException(409, "주문과 결제 상태를 확인해야 합니다.")
            return completed
        if order["status"] != "pending":
            raise HTTPException(409, "결제 대기 주문만 결제할 수 있습니다.")

        cursor.execute(
            """
            SELECT product_id, product_name, unit_price, quantity
            FROM public.order_items WHERE order_id = %s ORDER BY product_id FOR UPDATE
            """,
            (order_id,),
        )
        items = cursor.fetchall()
        total = sum(item["unit_price"] * item["quantity"] for item in items)
        if not items or total <= 0 or total != order["total_amount"]:
            raise HTTPException(409, "주문 상세 합계와 주문 금액이 일치하지 않습니다.")

        if outcome == "failure":
            return record_payment(cursor, order, key, "failed", "학습용으로 선택한 모의 결제 실패입니다.")

        # 모든 상품을 번호 순으로 잠그고 검사한 뒤에만 재고를 차감한다.
        cursor.execute(
            """
            SELECT id, stock, is_active FROM public.products
            WHERE id = ANY(%s) ORDER BY id FOR UPDATE
            """,
            ([item["product_id"] for item in items],),
        )
        products = {row["id"]: row for row in cursor.fetchall()}
        for item in items:
            product = products.get(item["product_id"])
            if not product or not product["is_active"] or product["stock"] < item["quantity"]:
                return record_payment(
                    cursor, order, key, "failed",
                    f"{item['product_name']}: 판매가 중단되었거나 재고가 부족합니다.",
                )

        for item in items:
            cursor.execute(
                """
                UPDATE public.products SET stock = stock - %s
                WHERE id = %s AND stock >= %s AND is_active = true
                """,
                (item["quantity"], item["product_id"], item["quantity"]),
            )
            if cursor.rowcount != 1:
                raise HTTPException(409, "재고가 변경되었습니다. 다시 시도해 주세요.")

        payment = record_payment(cursor, order, key, "succeeded")
        cursor.execute(
            "UPDATE public.orders SET status = 'paid', paid_at = now() WHERE id = %s AND status = 'pending'",
            (order_id,),
        )
        if cursor.rowcount != 1:
            raise HTTPException(409, "주문 상태가 변경되었습니다. 다시 확인해 주세요.")
        # 이 블록이 정상 종료되어야 재고·결제·주문 변경을 함께 커밋한다.
        return payment


def list_orders(user_id: int, token: str, status="all"):
    if status not in {"all", "pending", "paid"}:
        raise HTTPException(400, "주문 상태를 확인해 주세요.")
    with member_cursor(user_id, token) as cursor:
        query = """
            SELECT o.id, o.status, o.total_amount, o.placed_at, o.paid_at,
                   (SELECT product_name FROM public.order_items WHERE order_id = o.id ORDER BY id LIMIT 1) AS first_product_name,
                   (SELECT COUNT(*) FROM public.order_items WHERE order_id = o.id) AS item_count
            FROM public.orders AS o WHERE o.user_id = %s AND o.status <> 'cart'
        """
        parameters = (user_id,)
        if status != "all":
            query += " AND o.status = %s"
            parameters = (user_id, status)
        query += " ORDER BY o.placed_at DESC, o.id DESC"
        cursor.execute(query, parameters)
        return cursor.fetchall()


def paid_confirmation(user_id: int, token: str, order_id: int) -> bool:
    with member_cursor(user_id, token) as cursor:
        cursor.execute(
            """
            SELECT o.id FROM public.orders AS o
            WHERE o.id = %s AND o.user_id = %s AND o.status = 'paid'
              AND EXISTS (SELECT 1 FROM public.payments AS p WHERE p.order_id = o.id AND p.status = 'succeeded')
            """,
            (order_id, user_id),
        )
        return cursor.fetchone() is not None
```

### app/routers/payments.py

```python
from datetime import timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError

from app import payments, shopping
from app.routers.shopping import PositiveId, check_csrf, html_result, page, redirect, require_user
from app.session_auth import session_csrf_token, session_token


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["결제·주문내역"], dependencies=[Depends(no_store)])
KOREA_TIME = timezone(timedelta(hours=9))


class PaymentInput(BaseModel):
    idempotency_key: UUID
    outcome: Literal["success", "failure"]


@router.get("/orders", response_class=HTMLResponse)
def history_page(request: Request, status: Literal["all", "pending", "paid"] = "all"):
    def action(user):
        orders = payments.list_orders(user["id"], session_token(request), status)
        for order in orders:
            order["placed_display"] = order["placed_at"].astimezone(KOREA_TIME).strftime("%Y-%m-%d %H:%M")
        return page(request, user, "orders.html", {"orders": orders, "selected_status": status})
    return html_result(request, f"/orders?status={status}", action)


@router.get("/orders/{order_id}/pay", response_class=HTMLResponse)
def payment_page(
    request: Request, order_id: PositiveId,
    payment_id: Annotated[int | None, Query(gt=0, le=shopping.MAX_AMOUNT)] = None,
):
    def action(user):
        order = shopping.get_order(user["id"], session_token(request), order_id)
        if order["status"] == "paid":
            return redirect(f"/products?paid_order={order_id}")
        attempt = None
        if payment_id:
            attempt = next((p for p in order["payments"] if p["id"] == payment_id), None)
            if not attempt:
                raise HTTPException(404, "결제 시도를 찾을 수 없습니다.")
        return page(request, user, "payment.html", {
            "order": order, "attempt": attempt, "idempotency_key": str(uuid4()),
        })
    return html_result(request, f"/orders/{order_id}/pay", action)


@router.post("/orders/{order_id}/pay")
def submit_payment(
    request: Request, order_id: PositiveId,
    idempotency_key: Annotated[str, Form()] = "",
    outcome: Annotated[str, Form()] = "success",
    csrf_token: Annotated[str, Form()] = "",
):
    def action(user):
        try:
            data = PaymentInput(idempotency_key=idempotency_key, outcome=outcome)
        except ValidationError:
            raise HTTPException(400, "결제 요청을 확인해 주세요. 결제 화면을 다시 열어 주세요.") from None
        result = payments.pay_order(user["id"], session_token(request), order_id, data.idempotency_key, data.outcome)
        if result["status"] == "succeeded":
            return redirect(f"/products?paid_order={order_id}")
        return redirect(f"/orders/{order_id}/pay?payment_id={result['id']}")
    return html_result(request, f"/orders/{order_id}/pay", action, csrf=csrf_token)


@router.get("/api/orders")
def history_api(request: Request, status: Literal["all", "pending", "paid"] = "all"):
    user = require_user(request)
    return payments.list_orders(user["id"], session_token(request), status)


@router.get("/api/orders/{order_id}/payments")
def payments_api(request: Request, order_id: PositiveId):
    user = require_user(request)
    order = shopping.get_order(user["id"], session_token(request), order_id)
    return {
        "order_id": order_id, "order_status": order["status"],
        "total_amount": order["total_amount"], "payments": order["payments"],
        "idempotency_key": str(uuid4()),
        "csrf_token": session_csrf_token(session_token(request)),
    }


@router.post("/api/orders/{order_id}/payments")
def pay_api(
    request: Request, order_id: PositiveId, data: PaymentInput,
    x_csrf_token: Annotated[str, Header()] = "",
):
    user = require_user(request)
    check_csrf(request, x_csrf_token)
    return payments.pay_order(user["id"], session_token(request), order_id, data.idempotency_key, data.outcome)
```

### templates/payment.html

```html
{% extends "catalog_base.html" %}
{% block title %}모의 결제{% endblock %}
{% block content %}
    <p class="back-link"><a href="/orders/{{ order.id }}">← 주문 확인으로</a></p>
    <h1>모의 결제</h1>
    <p class="hint">학습용 결제입니다. 실제 금액은 청구되지 않으며 카드정보를 입력하지 않습니다.</p>
    {% if attempt and attempt.status == 'failed' %}
        <p class="error" role="alert">결제에 실패했습니다. {{ attempt.failure_reason }} 주문은 결제 대기 상태입니다.</p>
    {% endif %}
    <div class="shopping-layout">
        <section class="shopping-item">
            <h2>주문 #{{ order.id }}</h2>
            {% for item in order['items'] %}
                <p>{{ item.product_name }} · {{ item.quantity }}개<br>{{ "{:,}".format(item.unit_price * item.quantity) }}원</p>
            {% endfor %}
            <p class="hint">배송지: {{ order.shipping_address }}</p>
        </section>
        <aside class="order-summary" aria-label="결제 금액과 결과 선택">
            <h2>결제 금액</h2>
            <p class="product-price">{{ "{:,}".format(order.total_amount) }}원</p>
            <form action="/orders/{{ order.id }}/pay" method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <input type="hidden" name="idempotency_key" value="{{ idempotency_key }}">
                <button type="submit" name="outcome" value="success">모의 결제 성공</button>
                <button type="submit" name="outcome" value="failure" class="secondary">모의 결제 실패</button>
            </form>
            <p class="hint">성공 시 재고가 차감됩니다. 실패 시 재고는 유지되며 다시 시도할 수 있습니다.</p>
        </aside>
    </div>
{% endblock %}
```

### templates/orders.html

```html
{% extends "catalog_base.html" %}
{% block title %}주문·구매내역{% endblock %}
{% block content %}
    <h1>주문·구매내역</h1>
    <p class="hint">결제 대기 주문과 구매가 완료된 주문을 확인하세요.</p>
    <nav class="history-filters" aria-label="주문 상태 선택">
        <a href="/orders" {% if selected_status == 'all' %}aria-current="page"{% endif %}>전체</a>
        <a href="/orders?status=pending" {% if selected_status == 'pending' %}aria-current="page"{% endif %}>결제 대기</a>
        <a href="/orders?status=paid" {% if selected_status == 'paid' %}aria-current="page"{% endif %}>구매 완료</a>
    </nav>
    {% if orders %}
        <div class="shopping-items">
            {% for order in orders %}
                <article class="shopping-item history-item">
                    <div>
                        <p class="eyebrow">주문 #{{ order.id }} · {{ order.placed_display }} (한국시간)</p>
                        <h2>{{ order.first_product_name or '주문 상품' }}{% if order.item_count > 1 %} 외 {{ order.item_count - 1 }}종{% endif %}</h2>
                        <p class="stock-badge {{ 'pending-badge' if order.status == 'pending' else '' }}">{{ '결제 대기' if order.status == 'pending' else '구매 완료' }}</p>
                        <p class="product-price">{{ "{:,}".format(order.total_amount) }}원</p>
                    </div>
                    <div class="history-actions">
                        <a class="button secondary" href="/orders/{{ order.id }}">주문 상세</a>
                        {% if order.status == 'pending' %}
                            <a class="button" href="/orders/{{ order.id }}/pay">결제하기</a>
                        {% endif %}
                    </div>
                </article>
            {% endfor %}
        </div>
    {% else %}
        <div class="empty-state">
            <p>선택한 상태의 주문이 없습니다.</p>
            <a class="button" href="/products">상품 보러 가기</a>
        </div>
    {% endif %}
{% endblock %}
```

### app/main.py — 추가·변경 부분

```python
from app.routers import accounts, auth, profile, products, shopping, payments

app.include_router(payments.router)
```

### app/shopping.py — 변경 부분

DB 오류 문구에 결제를 추가했고 get_order 함수는 아래처럼 결제 시도도 포함합니다.

```python
def get_order(user_id: int, token: str, order_id: int):
    with member_cursor(user_id, token) as cursor:
        cursor.execute(
            """
            SELECT id, status, total_amount, recipient_name, recipient_phone, shipping_address, placed_at, paid_at
            FROM public.orders WHERE id = %s AND user_id = %s AND status <> 'cart'
            """,
            (order_id, user_id),
        )
        order = cursor.fetchone()
        if not order:
            raise HTTPException(404, "주문을 찾을 수 없습니다.")
        cursor.execute(
            "SELECT product_id, product_name, unit_price, quantity FROM public.order_items WHERE order_id = %s ORDER BY product_id",
            (order_id,),
        )
        order["items"] = cursor.fetchall()
        cursor.execute(
            """
            SELECT id, status, amount, failure_reason, created_at
            FROM public.payments WHERE order_id = %s ORDER BY id DESC
            """,
            (order_id,),
        )
        order["payments"] = cursor.fetchall()
        return order
```

### app/routers/products.py — 변경 부분

Query와 paid_confirmation을 import하고 목록 함수를 수정했습니다.

```python
from fastapi import APIRouter, HTTPException, Path, Query, Request
from app.payments import paid_confirmation

@router.get("/products", response_class=HTMLResponse)
def product_list(
    request: Request,
    paid_order: Annotated[int | None, Query(gt=0, le=9_223_372_036_854_775_807)] = None,
):
    products = [product_view(row) for row in read_products()]
    user = current_user(request)
    confirmed_order = None
    if user and paid_order and paid_confirmation(user["id"], session_token(request), paid_order):
        confirmed_order = paid_order
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={"products": products, "user": user, "paid_order": confirmed_order},
        headers={"Cache-Control": "no-store"},
    )
```

### templates/catalog_base.html과 templates/account.html — 링크 추가

로그인 메뉴 안에 추가했습니다.

```html
<a href="/orders">주문내역</a>
```

회원정보 화면에 추가했습니다.

```html
<a class="button secondary" href="/orders">주문·구매내역</a>
```

### templates/products.html — content 블록 시작에 추가

```html
{% if paid_order %}
    <p class="success" role="status">주문 #{{ paid_order }}의 모의 결제가 완료되었습니다.
        <a href="/orders/{{ paid_order }}">주문 확인</a>
    </p>
{% endif %}
```

### templates/order.html — 추가 부분

합계 영역에 결제와 주문내역 링크를 추가했습니다.

```html
            {% if order.status == 'pending' %}
                <a class="button" href="/orders/{{ order.id }}/pay">결제하기</a>
            {% endif %}
            <p><a href="/orders">주문내역 보기</a></p>
```

content 블록 마지막에는 결제 시도 기록을 추가했습니다.

```html
    {% if order.payments %}
        <section class="shopping-item payment-history" aria-labelledby="payment-history-title">
            <h2 id="payment-history-title">결제 시도 기록</h2>
            {% for attempt in order.payments %}
                <div class="payment-attempt">
                    <p><strong>결제 #{{ attempt.id }} · {{ '성공' if attempt.status == 'succeeded' else '실패' }}</strong>
                        · {{ "{:,}".format(attempt.amount) }}원</p>
                    {% if attempt.failure_reason %}<p class="hint">{{ attempt.failure_reason }}</p>{% endif %}
                </div>
            {% endfor %}
        </section>
    {% endif %}
```

### static/style.css — 추가 부분

```css
/* 주문내역은 작은 화면에서도 가로 스크롤 없이 읽을 수 있게 한다. */
.history-filters { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0 24px; }
.history-filters a { display: inline-flex; align-items: center; min-height: 44px; padding: 8px 14px; border: 1px solid #b7c3d4; border-radius: 8px; color: #243855; text-decoration: none; background: #fff; }
.history-filters a[aria-current="page"] { background: #2849b8; color: #fff; border-color: #2849b8; }
.history-item { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; }
.history-actions .button { margin-top: 12px; }
.pending-badge { background: #fff1d6; color: #775000; }
.payment-history { margin-top: 24px; }
.payment-attempt + .payment-attempt { border-top: 1px solid #dce2ea; margin-top: 16px; padding-top: 12px; }
@media (min-width: 768px) {
    .history-item { grid-template-columns: minmax(0, 1fr) 180px; align-items: center; gap: 24px; }
}
```

## 3. 요청 → 처리 → 응답

### ① 결제 화면 열기

주문내역 또는 주문 상세의 **결제하기** → `GET /orders/실제주문번호/pay` → 로그인·주문 소유자 확인 → 확정 상품과 결제 금액 표시.

결제 화면을 여는 것만으로 재고나 결제 데이터는 변경하지 않습니다. 폼에는 CSRF 확인표와 새 결제 요청 번호인 `idempotency_key`를 넣습니다.

### ② 모의 결제 성공

```text
모의 결제 성공 버튼
    → POST /orders/실제주문번호/pay
    → 로그인·CSRF 검사
    → 회원·세션 → 주문 → 주문 상세 → 상품 순서로 잠금
    → 기존 요청 번호·주문 상태 검사
    → 주문 상세 합계와 주문 총액 일치 확인
    → 상품 판매 여부와 재고 확인
    → 재고 차감
    → payments에 succeeded 기록
    → orders를 paid로 변경하고 paid_at 저장
    → 함께 커밋
    → 상품 목록으로 이동해 완료 안내
```

상품을 잠글 때는 상품 번호 순서를 통일합니다. 여러 회원이 같은 상품을 사도 재고를 읽고 차감하는 과정이 엇갈리지 않게 합니다. 최종 재고가 음수가 되지 않도록 UPDATE 조건과 DB 제약조건도 함께 사용합니다.

**재고 차감·성공 결제·주문 완료는 한 트랜잭션입니다.** 중간에 DB 오류가 발생하면 모두 롤백합니다. 커밋이 끝나기 전에는 성공 응답을 반환하지 않습니다.

결제 금액은 사용자가 전송한 숫자를 믿지 않고 `orders.total_amount`를 사용합니다. `order_items`의 확정 단가 × 수량 합계도 다시 비교합니다. 주문 후 현재 상품 판매가가 바뀌더라도 확정 주문의 가격으로 처리합니다.

상품 목록의 완료 안내도 URL에 주문 번호가 있다는 이유만으로 표시하지 않습니다. 로그인한 본인의 paid 주문과 성공 결제 기록을 확인한 뒤 표시합니다.

### ③ 모의 결제 실패 또는 재고 부족

| 상황 | payments | orders | products |
|---|---|---|---|
| 실패 버튼 선택 | failed와 모의 실패 사유 저장 | pending 유지 | 변경 없음 |
| 성공 선택 시 판매 중단·재고 부족 | failed와 상품 관련 사유 저장 | pending 유지 | 변경 없음 |
| DB 오류 등 처리 자체가 중단 | 트랜잭션 롤백 | 기존 상태 유지 | 기존 상태 유지 |

결제 실패 결과는 저장한 뒤 결제 화면으로 돌아가 안내합니다. 새 화면에는 새 요청 번호가 들어 있어 재시도할 수 있습니다. DB 오류와 모의 결제 실패는 구분합니다. 전자는 작업을 완료하지 못한 상황이고, 후자는 처리한 실패 결과를 기록한 상황입니다.

재고 부족이나 판매 중단은 성공 버튼을 다시 눌러도 해결되지 않습니다. 재고가 보충되거나 판매가 재개되어야 성공할 수 있습니다. 주문 내용 수정·취소·환불은 기존 합의대로 이번 범위에 포함하지 않습니다.

### ④ 중복 결제 방지

- 같은 `idempotency_key`가 다시 오면 처음 저장한 결과를 반환합니다.
- 같은 키로 실패 후 성공을 선택해 보내도 최초 실패 결과를 반환합니다. 새 시도에는 새 키가 필요합니다.
- 이미 paid인 주문은 새 키로 요청해도 기존 성공 결제를 반환하며 추가 차감하지 않습니다.
- 다른 주문에서 사용한 키를 재사용하면 거부합니다.
- DB에서도 주문당 성공 결제 최대 하나를 고유 인덱스로 제한합니다.

STEP 5의 `orders.checkout_key`는 **주문 생성** 중복 방지용입니다. 이번 `payments.idempotency_key`는 **결제 시도** 중복 방지용이므로 용도가 다릅니다.

### ⑤ 주문·구매내역

`GET /orders` → 로그인 확인 → 본인 cart 이외 주문 조회 → 최신 주문부터 목록 응답.

- 전체: pending과 paid 모두 표시
- 결제 대기: pending만 표시하고 결제하기 링크 제공
- 구매 완료: paid만 표시

주문 상세에는 확정 상품·단가·수량·배송정보와 성공·실패 시도를 표시합니다. 본인 이외의 주문·결제 내역은 조회하지 못하도록 회원 번호 조건을 함께 검사합니다. 주문 목록의 시간은 한국시간(UTC+9)으로 표시합니다.

## 4. 직접 실행·확인하는 방법

### ① 서버 다시 시작

현재 서버 터미널에서 `Ctrl + C`로 종료하고 같은 가상환경에서 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

추가 SQL이나 패키지 설치는 필요하지 않습니다. 다음 항목은 직접 확인할 기준이며 제가 실행해서 얻은 결과가 아닙니다.

### ② 기존 결제 대기 주문 찾기

1. [로그인](http://127.0.0.1:8000/login)합니다.
2. [주문내역](http://127.0.0.1:8000/orders)을 엽니다. 회원정보의 **주문·구매내역** 버튼으로도 이동할 수 있습니다.
3. 앞서 생성한 결제 대기 주문이 보이는지 확인합니다.
4. **주문 상세** 또는 **결제하기**를 누릅니다.

결제 대기 주문이 없다면 상품을 담고 주문서를 한 번 작성합니다. 기존 테이블이나 구매 기록을 삭제하지 않습니다.

### ③ 실패부터 확인하기

1. Supabase `products`에서 주문 상품의 현재 재고를 확인해 둡니다.
2. 결제 화면에서 **모의 결제 실패**를 누릅니다.
3. 실패 안내와 재시도 버튼이 보이는지 확인합니다.
4. Supabase에서 해당 주문이 pending이고 재고가 그대로인지 확인합니다.
5. `payments`에 해당 order_id의 failed 기록과 failure_reason이 있는지 확인합니다.

### ④ 같은 주문으로 성공 확인하기

1. 실패 안내 후 표시된 결제 화면에서 **모의 결제 성공**을 누릅니다.
2. 상품 목록으로 이동하고 완료 안내가 보이는지 확인합니다.
3. 상품 재고가 구매 수량만큼 감소했는지 확인합니다.
4. 해당 `orders.status`가 paid이고 paid_at이 채워졌는지 확인합니다.
5. `payments`에 성공 기록이 생겼고 앞의 실패 기록도 남아 있는지 확인합니다.

실제 결제나 청구는 발생하지 않습니다. 성공 시 학습용 DB의 재고와 상태는 실제로 변경됩니다.

### ⑤ 구매내역과 재접속 확인하기

1. [구매 완료 목록](http://127.0.0.1:8000/orders?status=paid)을 엽니다.
2. 방금 구매한 주문이 표시되는지 확인합니다.
3. 주문 상세의 상품·금액과 결제 시도 기록을 확인합니다.
4. 이미 결제된 주문의 결제 주소를 다시 열면 상품 목록으로 이동하고 재고가 더 줄지 않는지 확인합니다.
5. 로그아웃 후 `/orders`를 열면 로그인 화면으로 이동하고, 성공 후 주문내역으로 복귀하는지 확인합니다.

상품 목록 새로고침이나 주문 상세 재접속은 GET 조회이므로 결제를 다시 실행하지 않습니다.

### ⑥ API 확인

| 메서드 | 주소 | 역할 |
|---|---|---|
| GET | /api/orders | 본인의 전체 주문내역 |
| GET | /api/orders?status=paid | 본인의 구매 완료 내역 |
| GET | /api/orders/{order_id} | 상품·배송정보·결제 시도가 포함된 본인 주문 |
| GET | /api/orders/{order_id}/payments | 결제 시도·새 요청 키·CSRF 확인표 조회 |
| POST | /api/orders/{order_id}/payments | 모의 결제 처리 |

같은 브라우저에서 로그인한 상태로 [주문내역 API](http://127.0.0.1:8000/api/orders)를 열 수 있습니다. 비로그인 API 요청에는 401 JSON을 반환합니다.

POST 본문은 `idempotency_key`와 `outcome`입니다. `outcome`은 `success` 또는 `failure`이며, 금액은 전송하지 않습니다. `X-CSRF-Token` 헤더도 필요합니다. GET 결제 API가 새 요청 키와 확인표를 제공하므로 `/docs`에서 값을 복사해 사용할 수 있습니다.

네트워크 오류로 같은 시도를 재전송할 때는 새 키를 받지 말고 기존 요청 키를 유지합니다. 실패 후 새로운 결제를 시도할 때는 GET으로 새 키를 받습니다. 처음에는 HTML 화면으로 확인하면 충분합니다.

## 5. 피드백 질문

먼저 **주문내역 → 결제하기 → 모의 결제 실패 → 모의 결제 성공** 순서로 확인해 주세요.

- 기존 결제 대기 주문이 보이나요?
- 실패 시 재고가 유지되나요?
- 성공 시 상품 목록으로 이동하고 재고가 구매 수량만큼 줄어드나요?
- 구매 완료 내역에서 주문을 다시 확인할 수 있나요?
- 오류나 설명이 필요한 부분이 있나요?

확인 결과를 받은 뒤 STEP 7의 모바일·태블릿·PC 화면 점검으로 넘어갑니다.

## 실제 PG로 확장할 때의 방향

서버가 확정 금액으로 PG 결제를 요청하고, 검증된 승인 응답이나 서명이 확인된 웹훅으로 결과를 반영하도록 바꿉니다. 브라우저의 성공 선택값은 실제 결제 승인 근거로 사용할 수 없습니다.

외부 PG 처리와 DB 트랜잭션을 하나의 트랜잭션으로 묶을 수 없으므로 승인 재확인·중복 콜백 방지·실패 보상 또는 취소 흐름을 추가해야 합니다. 현재 모의 결제는 DB 안에서 결과를 결정하므로 위와 같은 단일 트랜잭션으로 처리합니다.

## 참고

- [PostgreSQL 공식 문서: 행 잠금](https://www.postgresql.org/docs/17/explicit-locking.html)
- [Psycopg 공식 문서: 트랜잭션과 커밋·롤백](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)

이번 작업은 파일 작성만 수행했습니다. 코드·서버·SQL 실행, DB 변경 및 테스트는 하지 않았습니다.
