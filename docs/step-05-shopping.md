# STEP 5 — 장바구니와 주문

## 1. 이번 단계의 목표

상품 상세에서 **장바구니 담기·바로 구매**를 선택하고, 배송정보를 입력해 **결제 대기 주문**을 생성합니다. 장바구니 수량 변경과 삭제도 구현합니다.

이번에는 결제하지 않습니다. 재고는 결제 성공 시 차감하므로 이번 단계에서는 조회·검사만 합니다. 실제 카드정보는 입력하지 않습니다. 로그인하지 않은 사용자는 로그인 화면으로 이동하고 성공 후 이전 화면으로 돌아옵니다.

### 이번 단계의 용어

| 용어 | 쉬운 설명 |
|---|---|
| 장바구니 | 살까 생각 중인 상품 목록. 아직 주문 확정 전 |
| 주문서 | 최종 상품·수량·가격을 확인하고 배송정보를 적는 화면 |
| 결제 대기 주문 | 구매할 내용을 확정했지만 결제는 끝나지 않은 상태 |
| checkout_key | 같은 주문서를 중복 제출했는지 구별하는 무작위 요청 번호 |
| fingerprint | 화면에 보여준 상품명·가격·수량이 변경됐는지 확인하는 요약값 |
| 트랜잭션 | 여러 DB 작업을 모두 성공하거나 모두 되돌리게 묶는 처리 |

### 이번 구현의 구체적인 선택

- 같은 상품을 다시 담으면 기존 수량에 더합니다.
- 수량 변경은 새 수량으로 교체합니다. 삭제는 별도 버튼으로 처리합니다.
- 학습용으로 상품당 수량을 **1~999개**, 현재 재고 이내로 제한합니다.
- 상품 선택 시와 주문 확정 시에 판매 여부·재고를 재검사합니다.
- 주문서에는 최신 가격을 표시합니다. 주문서를 연 뒤 가격·수량이 바뀌면 주문을 만들지 않고 다시 확인하도록 안내합니다.
- 주문 확정 후 상세의 상품명·단가·수량과 주문 합계는 구매 당시 사본으로 유지합니다.
- 배송비는 기존 합의대로 0원입니다.

## 2. 파일과 전체 코드

| 파일 | 작업 | 역할 |
|---|---|---|
| sql/003_order_checkout_key.sql | 생성 | 기존 orders에 중복 요청 방지 컬럼 추가 |
| sql/001_create_tables.sql | 수정 | 새 DB를 만들 때도 같은 컬럼·인덱스가 생기도록 반영 |
| app/shopping.py | 생성 | 장바구니·주문 DB 처리와 트랜잭션 |
| app/routers/shopping.py | 생성 | HTML 폼과 JSON API 요청 처리 |
| templates/cart.html | 생성 | 장바구니 |
| templates/checkout.html | 생성 | 주문서와 배송정보 입력 |
| templates/order.html | 생성 | 확정 주문 확인 |
| templates/shopping_error.html | 생성 | 오류와 돌아가기 안내 |
| app/session_auth.py | 수정 | 회원·세션 잠금 함수를 공통 위치로 이동 |
| app/routers/profile.py | 수정 | 공통 함수를 가져오도록 변경, 기존 동작 유지 |
| app/main.py | 수정 | 새 라우터 연결 |
| app/routers/products.py | 수정 | 상품 상세 폼에 세션 확인표 전달 |
| 기존 상품·메뉴·회원정보 HTML | 수정 | 담기·바로 구매·장바구니 이동 연결 |
| static/style.css | 수정 | 장바구니·주문서의 모바일 우선 배치 |

추가 패키지와 `.env` 변경은 필요하지 않습니다. **이미 테이블을 만든 경우 `001_create_tables.sql`을 다시 실행하지 말고 `003_order_checkout_key.sql`만 실행**합니다.

아래에는 새 파일의 전체 코드와 기존 파일에서 바뀐 부분만 담았습니다. 파일 작성만 완료했으며 실행·테스트·DB 변경은 하지 않았습니다.

### sql/003_order_checkout_key.sql

```sql
BEGIN;

-- 주문 생성 버튼을 다시 눌러도 같은 주문을 반환하기 위한 요청 번호다.
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS checkout_key uuid;
CREATE UNIQUE INDEX IF NOT EXISTS orders_checkout_key_idx
    ON public.orders(checkout_key);

COMMIT;
```

### app/shopping.py

```python
import hashlib
import json
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.database import get_connection
from app.session_auth import lock_account


MAX_QUANTITY = 999
MAX_AMOUNT = 9_223_372_036_854_775_807


@contextmanager
def member_cursor(user_id: int, token: str):
    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if not lock_account(cursor, user_id, token):
                    raise HTTPException(401, "다시 로그인해 주세요.")
                yield cursor
    except (psycopg.Error, ValidationError):
        raise HTTPException(503, "장바구니·주문을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.") from None


def cart_order(cursor, user_id: int):
    cursor.execute(
        "SELECT id FROM public.orders WHERE user_id = %s AND status = 'cart' FOR UPDATE",
        (user_id,),
    )
    return cursor.fetchone()


def cart_rows(cursor, order_id: int, *, lock_products=False):
    query = """
        SELECT i.product_id, i.quantity, i.unit_price AS saved_unit_price,
               p.name AS product_name, p.price AS unit_price, p.stock, p.is_active
        FROM public.order_items AS i
        JOIN public.products AS p ON p.id = i.product_id
        WHERE i.order_id = %s ORDER BY p.id
    """
    if lock_products:
        query += " FOR UPDATE OF p"
    cursor.execute(query, (order_id,))
    rows = cursor.fetchall()
    for row in rows:
        row["line_total"] = row["unit_price"] * row["quantity"]
    return rows


def checked_total(items: list[dict]) -> int:
    if not items:
        raise HTTPException(409, "장바구니가 비어 있습니다. 상품을 먼저 담아 주세요.")
    for item in items:
        if not item["is_active"] or not 1 <= item["quantity"] <= min(item["stock"], MAX_QUANTITY):
            raise HTTPException(409, f"{item['product_name']}: 판매 여부·재고·수량을 다시 확인해 주세요.")
    total = sum(item["unit_price"] * item["quantity"] for item in items)
    if not 0 < total <= MAX_AMOUNT:
        raise HTTPException(400, "주문 금액 범위를 초과했습니다.")
    return total


def fingerprint(items: list[dict]) -> str:
    data = [[i["product_id"], i["product_name"], i["unit_price"], i["quantity"]] for i in items]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode("utf-8")).hexdigest()


def get_cart(user_id: int, token: str):
    with member_cursor(user_id, token) as cursor:
        order = cart_order(cursor, user_id)
        items = cart_rows(cursor, order["id"]) if order else []
        return {
            "id": order["id"] if order else None,
            "status": "cart",
            "items": items,
            "total_amount": sum(item["line_total"] for item in items),
        }


def change_cart(user_id: int, token: str, product_id: int, quantity: int, *, add=False):
    if not 0 <= quantity <= MAX_QUANTITY or (add and quantity == 0):
        raise HTTPException(400, "수량은 1~999개로 입력해 주세요.")
    with member_cursor(user_id, token) as cursor:
        order = cart_order(cursor, user_id)
        if not order:
            if not add:
                raise HTTPException(404, "장바구니 상품을 찾을 수 없습니다.")
            cursor.execute("INSERT INTO public.orders (user_id) VALUES (%s) RETURNING id", (user_id,))
            order = cursor.fetchone()
        cursor.execute(
            "SELECT quantity FROM public.order_items WHERE order_id = %s AND product_id = %s",
            (order["id"], product_id),
        )
        existing = cursor.fetchone()
        if not add and not existing:
            raise HTTPException(404, "장바구니 상품을 찾을 수 없습니다.")
        if quantity == 0:
            cursor.execute(
                "DELETE FROM public.order_items WHERE order_id = %s AND product_id = %s",
                (order["id"], product_id),
            )
            return
        cursor.execute("SELECT id, name, price, stock, is_active FROM public.products WHERE id = %s FOR UPDATE", (product_id,))
        product = cursor.fetchone()
        if not product or not product["is_active"]:
            raise HTTPException(404, "판매 중인 상품을 찾을 수 없습니다.")
        new_quantity = quantity + (existing["quantity"] if add and existing else 0)
        if new_quantity > min(product["stock"], MAX_QUANTITY):
            raise HTTPException(409, "담으려는 수량이 현재 재고 또는 999개 제한을 초과합니다.")
        cursor.execute(
            """
            INSERT INTO public.order_items (order_id, product_id, product_name, unit_price, quantity)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (order_id, product_id) DO UPDATE
            SET product_name = EXCLUDED.product_name, unit_price = EXCLUDED.unit_price,
                quantity = EXCLUDED.quantity
            """,
            (order["id"], product_id, product["name"], product["price"], new_quantity),
        )


def checkout_snapshot(cursor, user_id, source, product_id=None, quantity=1, cart_id=None):
    if source == "cart":
        order = cart_order(cursor, user_id)
        if not order or (cart_id is not None and order["id"] != cart_id):
            raise HTTPException(409, "장바구니가 변경되었습니다. 장바구니에서 다시 주문해 주세요.")
        cart_id = order["id"]
        items = cart_rows(cursor, cart_id, lock_products=True)
    elif source == "buy" and product_id and 1 <= quantity <= MAX_QUANTITY:
        cursor.execute(
            """
            SELECT id AS product_id, name AS product_name, price AS unit_price, stock, is_active
            FROM public.products WHERE id = %s FOR UPDATE
            """,
            (product_id,),
        )
        product = cursor.fetchone()
        if not product:
            raise HTTPException(404, "상품을 찾을 수 없습니다.")
        items = [{**product, "quantity": quantity, "line_total": product["unit_price"] * quantity}]
        cart_id = None
    else:
        raise HTTPException(400, "주문 경로 또는 상품 수량이 올바르지 않습니다.")
    total = checked_total(items)
    return {
        "source": source, "cart_id": cart_id, "product_id": product_id if source == "buy" else None,
        "quantity": quantity if source == "buy" else 1,
        "items": items, "total_amount": total, "fingerprint": fingerprint(items),
    }


def checkout_preview(user_id, token, source="cart", product_id=None, quantity=1):
    with member_cursor(user_id, token) as cursor:
        preview = checkout_snapshot(cursor, user_id, source, product_id, quantity)
        return {**preview, "checkout_key": str(uuid4())}


def create_order(user_id: int, token: str, data: dict) -> int:
    with member_cursor(user_id, token) as cursor:
        # 같은 요청 번호의 재전송은 새 주문을 만들지 않는다.
        cursor.execute(
            "SELECT * FROM public.orders WHERE checkout_key = %s AND user_id = %s FOR UPDATE",
            (data["checkout_key"], user_id),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "SELECT product_id, product_name, unit_price, quantity FROM public.order_items WHERE order_id = %s ORDER BY product_id",
                (existing["id"],),
            )
            saved_items = cursor.fetchall()
            same_shipping = all(existing[key] == data[key] for key in ("recipient_name", "recipient_phone", "shipping_address"))
            if not same_shipping or fingerprint(saved_items) != data["fingerprint"]:
                raise HTTPException(409, "같은 요청 번호로 주문 내용을 바꿀 수 없습니다. 주문서를 다시 열어 주세요.")
            return existing["id"]

        preview = checkout_snapshot(
            cursor, user_id, data["source"], data["product_id"], data["quantity"], data["cart_id"]
        )
        if data["source"] == "cart" and data["cart_id"] != preview["cart_id"]:
            raise HTTPException(409, "장바구니가 변경되었습니다. 주문서를 다시 열어 주세요.")
        if preview["fingerprint"] != data["fingerprint"]:
            raise HTTPException(409, "상품명·가격·수량이 변경되었습니다. 주문서를 다시 열고 확인해 주세요.")
        values = (data["checkout_key"], preview["total_amount"], data["recipient_name"], data["recipient_phone"], data["shipping_address"])
        if data["source"] == "cart":
            order_id = preview["cart_id"]
            for item in preview["items"]:
                cursor.execute(
                    "UPDATE public.order_items SET product_name = %s, unit_price = %s WHERE order_id = %s AND product_id = %s",
                    (item["product_name"], item["unit_price"], order_id, item["product_id"]),
                )
            cursor.execute(
                """
                UPDATE public.orders SET status = 'pending', checkout_key = %s, total_amount = %s,
                    recipient_name = %s, recipient_phone = %s, shipping_address = %s, placed_at = now()
                WHERE id = %s
                """,
                (*values, order_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO public.orders
                    (checkout_key, total_amount, recipient_name, recipient_phone, shipping_address, user_id, status, placed_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', now()) RETURNING id
                """,
                (*values, user_id),
            )
            order_id = cursor.fetchone()["id"]
            for item in preview["items"]:
                cursor.execute(
                    """
                    INSERT INTO public.order_items (order_id, product_id, product_name, unit_price, quantity)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (order_id, item["product_id"], item["product_name"], item["unit_price"], item["quantity"]),
                )
        return order_id


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
        return order
```

### app/routers/shopping.py

```python
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Form, Header, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app import shopping
from app.config import BASE_DIR
from app.security import is_valid_csrf_token
from app.session_auth import current_user, login_redirect, session_csrf_token, session_token


router = APIRouter(tags=["장바구니·주문"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")
PositiveId = Annotated[int, Path(gt=0, le=shopping.MAX_AMOUNT)]
QueryId = Annotated[int | None, Query(gt=0, le=shopping.MAX_AMOUNT)]
Quantity = Annotated[int, Query(ge=1, le=shopping.MAX_QUANTITY)]


class CartItemInput(BaseModel):
    product_id: int = Field(gt=0, le=shopping.MAX_AMOUNT)
    quantity: int = Field(ge=1, le=shopping.MAX_QUANTITY)


class QuantityInput(BaseModel):
    quantity: int = Field(ge=1, le=shopping.MAX_QUANTITY)


class OrderInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: Literal["cart", "buy"]
    cart_id: int | None = Field(default=None, gt=0, le=shopping.MAX_AMOUNT)
    product_id: int | None = Field(default=None, gt=0, le=shopping.MAX_AMOUNT)
    quantity: int = Field(default=1, ge=1, le=shopping.MAX_QUANTITY)
    checkout_key: UUID
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipient_name: str = Field(min_length=1, max_length=50)
    recipient_phone: str = Field(min_length=8, max_length=30, pattern=r"^[0-9+() -]+$")
    shipping_address: str = Field(min_length=5, max_length=300)

    @model_validator(mode="after")
    def validate_source(self):
        if (self.source == "cart" and not self.cart_id) or (self.source == "buy" and not self.product_id):
            raise ValueError("주문 대상이 필요합니다.")
        digits = sum(char.isdigit() for char in self.recipient_phone)
        if not 8 <= digits <= 15:
            raise ValueError("연락처는 숫자 8~15자리를 포함해야 합니다.")
        return self


def require_user(request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user


def check_csrf(request, value):
    token = session_token(request)
    if not token or not is_valid_csrf_token(session_csrf_token(token), value):
        raise HTTPException(403, "요청을 확인할 수 없습니다. 원래 화면을 새로고침해 주세요.")


def page(request, user, template, context, status_code=200):
    token = session_token(request)
    return templates.TemplateResponse(
        request=request, name=template,
        context={**context, "user": user, "csrf_token": session_csrf_token(token) if token else ""},
        status_code=status_code, headers={"Cache-Control": "no-store"},
    )


def html_result(request, next_path, action, csrf=None):
    user = None
    try:
        user = require_user(request)
        if csrf is not None:
            check_csrf(request, csrf)
        return action(user)
    except HTTPException as error:
        if error.status_code == 401:
            return login_redirect(next_path)
        return page(request, user, "shopping_error.html", {
            "message": error.detail, "back_path": next_path,
        }, error.status_code)


def redirect(url):
    return RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})


@router.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request):
    def action(user):
        cart = shopping.get_cart(user["id"], session_token(request))
        return page(request, user, "cart.html", {"cart": cart})
    return html_result(request, "/cart", action)


@router.post("/cart/items")
def add_item(
    request: Request,
    product_id: Annotated[int, Form()],
    quantity: Annotated[int, Form()] = 1,
    action: Annotated[str, Form()] = "cart",
    csrf_token: Annotated[str, Form()] = "",
):
    def submit(user):
        if not 0 < product_id <= shopping.MAX_AMOUNT or not 1 <= quantity <= shopping.MAX_QUANTITY:
            raise HTTPException(400, "상품 번호와 수량을 확인해 주세요.")
        if action == "buy":
            return redirect(f"/checkout?source=buy&product_id={product_id}&quantity={quantity}")
        if action != "cart":
            raise HTTPException(400, "선택한 동작을 확인해 주세요.")
        shopping.change_cart(user["id"], session_token(request), product_id, quantity, add=True)
        return redirect("/cart")
    return html_result(request, f"/products/{product_id}", submit, csrf=csrf_token)


@router.post("/cart/items/{product_id}/quantity")
def set_quantity(
    request: Request, product_id: PositiveId,
    quantity: Annotated[int, Form()], csrf_token: Annotated[str, Form()] = "",
):
    def action(user):
        if quantity < 1:
            raise HTTPException(400, "수량은 1개 이상으로 입력해 주세요. 상품 삭제는 삭제 버튼을 사용하세요.")
        shopping.change_cart(user["id"], session_token(request), product_id, quantity)
        return redirect("/cart")
    return html_result(request, "/cart", action, csrf=csrf_token)


@router.post("/cart/items/{product_id}/remove")
def remove_item(request: Request, product_id: PositiveId, csrf_token: Annotated[str, Form()] = ""):
    def action(user):
        shopping.change_cart(user["id"], session_token(request), product_id, 0)
        return redirect("/cart")
    return html_result(request, "/cart", action, csrf=csrf_token)


@router.get("/checkout", response_class=HTMLResponse)
def checkout_page(
    request: Request, source: Literal["cart", "buy"] = "cart",
    product_id: QueryId = None, quantity: Quantity = 1,
):
    def action(user):
        checkout = shopping.checkout_preview(user["id"], session_token(request), source, product_id, quantity)
        return page(request, user, "checkout.html", {"checkout": checkout})
    next_path = "/checkout" if source == "cart" else f"/checkout?source=buy&product_id={product_id}&quantity={quantity}"
    return html_result(request, next_path, action)


@router.post("/orders")
def submit_order(
    request: Request,
    source: Annotated[str, Form()] = "cart",
    cart_id: Annotated[str, Form()] = "",
    product_id: Annotated[str, Form()] = "",
    quantity: Annotated[str, Form()] = "1",
    checkout_key: Annotated[str, Form()] = "",
    fingerprint: Annotated[str, Form()] = "",
    recipient_name: Annotated[str, Form()] = "",
    recipient_phone: Annotated[str, Form()] = "",
    shipping_address: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    def action(user):
        try:
            data = OrderInput(
                source=source, cart_id=cart_id or None, product_id=product_id or None,
                quantity=quantity, checkout_key=checkout_key, fingerprint=fingerprint,
                recipient_name=recipient_name, recipient_phone=recipient_phone,
                shipping_address=shipping_address,
            )
        except ValidationError:
            raise HTTPException(400, "주문서와 배송정보를 확인해 주세요. 연락처는 숫자 8~15자리, 주소는 5자 이상이어야 합니다.") from None
        order_id = shopping.create_order(user["id"], session_token(request), data.model_dump())
        return redirect(f"/orders/{order_id}")
    return html_result(request, "/cart" if source == "cart" else "/products", action, csrf=csrf_token)


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_page(request: Request, order_id: PositiveId):
    def action(user):
        order = shopping.get_order(user["id"], session_token(request), order_id)
        return page(request, user, "order.html", {"order": order})
    return html_result(request, f"/orders/{order_id}", action)


@router.get("/api/cart")
def cart_api(request: Request):
    user = require_user(request)
    cart = shopping.get_cart(user["id"], session_token(request))
    return {**cart, "csrf_token": session_csrf_token(session_token(request))}


@router.post("/api/cart/items")
def add_api(request: Request, data: CartItemInput, x_csrf_token: Annotated[str, Header()] = ""):
    user = require_user(request)
    check_csrf(request, x_csrf_token)
    shopping.change_cart(user["id"], session_token(request), data.product_id, data.quantity, add=True)
    return shopping.get_cart(user["id"], session_token(request))


@router.patch("/api/cart/items/{product_id}")
def quantity_api(request: Request, product_id: PositiveId, data: QuantityInput, x_csrf_token: Annotated[str, Header()] = ""):
    user = require_user(request)
    check_csrf(request, x_csrf_token)
    shopping.change_cart(user["id"], session_token(request), product_id, data.quantity)
    return shopping.get_cart(user["id"], session_token(request))


@router.delete("/api/cart/items/{product_id}")
def remove_api(request: Request, product_id: PositiveId, x_csrf_token: Annotated[str, Header()] = ""):
    user = require_user(request)
    check_csrf(request, x_csrf_token)
    shopping.change_cart(user["id"], session_token(request), product_id, 0)
    return shopping.get_cart(user["id"], session_token(request))


@router.get("/api/checkout")
def checkout_api(
    request: Request, source: Literal["cart", "buy"] = "cart",
    product_id: QueryId = None, quantity: Quantity = 1,
):
    user = require_user(request)
    return shopping.checkout_preview(user["id"], session_token(request), source, product_id, quantity)


@router.post("/api/orders", status_code=201)
def order_api(request: Request, data: OrderInput, x_csrf_token: Annotated[str, Header()] = ""):
    user = require_user(request)
    check_csrf(request, x_csrf_token)
    order_id = shopping.create_order(user["id"], session_token(request), data.model_dump())
    return shopping.get_order(user["id"], session_token(request), order_id)


@router.get("/api/orders/{order_id}")
def order_detail_api(request: Request, order_id: PositiveId):
    user = require_user(request)
    return shopping.get_order(user["id"], session_token(request), order_id)
```

### templates/cart.html

```html
{% extends "catalog_base.html" %}
{% block title %}장바구니{% endblock %}
{% block content %}
    <h1>장바구니</h1>
    <p class="hint">현재 판매가 기준이며, 장바구니에 담아도 재고가 예약되지는 않습니다.</p>
    {% if cart['items'] %}
        <div class="shopping-layout">
            <div class="shopping-items">
                {% for item in cart['items'] %}
                    <article class="shopping-item">
                        <h2><a href="/products/{{ item.product_id }}">{{ item.product_name }}</a></h2>
                        <p>{{ "{:,}".format(item.unit_price) }}원 × {{ item.quantity }}개</p>
                        <p class="product-price">{{ "{:,}".format(item.line_total) }}원</p>
                        {% if not item.is_active or item.stock < item.quantity %}
                            <p class="error">판매가 중단됐거나 재고가 부족합니다. 수량을 변경하거나 삭제해 주세요.</p>
                        {% endif %}
                        {% if item.saved_unit_price != item.unit_price %}
                            <p class="hint">담은 시점과 가격이 달라 현재 가격을 표시합니다.</p>
                        {% endif %}
                        <form action="/cart/items/{{ item.product_id }}/quantity" method="post" class="quantity-form">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <label for="qty-{{ item.product_id }}">수량</label>
                            <input id="qty-{{ item.product_id }}" type="number" name="quantity" value="{{ item.quantity }}" min="1" max="999" required>
                            <button type="submit">수량 변경</button>
                        </form>
                        <form action="/cart/items/{{ item.product_id }}/remove" method="post">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <button type="submit" class="secondary">삭제</button>
                        </form>
                    </article>
                {% endfor %}
            </div>
            <aside class="order-summary" aria-label="장바구니 합계">
                <h2>주문 금액</h2>
                <p class="product-price">{{ "{:,}".format(cart.total_amount) }}원</p>
                <p class="hint">배송비 0원</p>
                <a class="button" href="/checkout">주문서 작성</a>
                <p><a href="/products">계속 쇼핑하기</a></p>
            </aside>
        </div>
    {% else %}
        <div class="empty-state">
            <p>장바구니가 비어 있습니다.</p>
            <a class="button" href="/products">상품 보러 가기</a>
        </div>
    {% endif %}
{% endblock %}
```

### templates/checkout.html

```html
{% extends "catalog_base.html" %}
{% block title %}주문서{% endblock %}
{% block content %}
    <h1>주문서</h1>
    <p class="hint">상품·수량·최종 금액을 확인하고 배송정보를 입력해 주세요.</p>
    <div class="shopping-layout">
        <section class="shopping-item">
            <h2>배송정보</h2>
            <form action="/orders" method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <input type="hidden" name="source" value="{{ checkout.source }}">
                <input type="hidden" name="cart_id" value="{{ checkout.cart_id or '' }}">
                <input type="hidden" name="product_id" value="{{ checkout.product_id or '' }}">
                <input type="hidden" name="quantity" value="{{ checkout.quantity }}">
                <input type="hidden" name="checkout_key" value="{{ checkout.checkout_key }}">
                <input type="hidden" name="fingerprint" value="{{ checkout.fingerprint }}">
                <label for="recipient-name">수령인</label>
                <input id="recipient-name" name="recipient_name" maxlength="50" autocomplete="shipping name" required>
                <label for="recipient-phone">연락처</label>
                <input id="recipient-phone" name="recipient_phone" type="tel" minlength="8" maxlength="30" autocomplete="shipping tel" placeholder="010-1234-5678" required>
                <label for="shipping-address">배송주소</label>
                <textarea id="shipping-address" name="shipping_address" minlength="5" maxlength="300" autocomplete="shipping street-address" rows="3" required></textarea>
                <button type="submit">주문 생성</button>
            </form>
        </section>
        <aside class="order-summary" aria-label="주문 상품과 합계">
            <h2>주문 상품</h2>
            {% for item in checkout['items'] %}
                <p>{{ item.product_name }} · {{ item.quantity }}개<br>{{ "{:,}".format(item.unit_price * item.quantity) }}원</p>
            {% endfor %}
            <hr>
            <p>배송비 0원</p>
            <p class="product-price">합계 {{ "{:,}".format(checkout.total_amount) }}원</p>
            <p class="hint">주문 생성 후 결제 대기 상태가 됩니다. 아직 결제되지는 않습니다.</p>
        </aside>
    </div>
{% endblock %}
```

### templates/order.html

```html
{% extends "catalog_base.html" %}
{% block title %}주문 {{ order.id }}{% endblock %}
{% block content %}
    <h1>주문 #{{ order.id }}</h1>
    <p class="stock-badge">{{ '결제 대기' if order.status == 'pending' else '결제 완료' }}</p>
    <div class="shopping-layout">
        <section class="shopping-item">
            <h2>주문 상품</h2>
            {% for item in order['items'] %}
                <p>{{ item.product_name }} · {{ item.quantity }}개<br>{{ "{:,}".format(item.unit_price) }}원 × {{ item.quantity }} = {{ "{:,}".format(item.unit_price * item.quantity) }}원</p>
            {% endfor %}
            <h2>배송정보</h2>
            <p>{{ order.recipient_name }} · {{ order.recipient_phone }}</p>
            <p class="product-description">{{ order.shipping_address }}</p>
        </section>
        <aside class="order-summary" aria-label="주문 금액">
            <h2>최종 금액</h2>
            <p class="product-price">{{ "{:,}".format(order.total_amount) }}원</p>
            <p class="hint">{{ '아직 결제되지 않았습니다.' if order.status == 'pending' else '결제된 주문입니다.' }}</p>
            <a class="button" href="/products">상품 목록으로</a>
        </aside>
    </div>
{% endblock %}
```

### templates/shopping_error.html

```html
{% extends "catalog_base.html" %}
{% block title %}요청 확인{% endblock %}
{% block content %}
    <section class="empty-state">
        <h1>요청을 확인해 주세요.</h1>
        <p class="error" role="alert">{{ message }}</p>
        <a class="button" href="{{ back_path }}">돌아가서 확인하기</a>
        <p><a href="/products">상품 목록으로</a></p>
    </section>
{% endblock %}
```

### sql/001_create_tables.sql — 추가 부분

orders의 id 컬럼 뒤에 checkout_key를 추가하고, 생성 후 고유 인덱스를 추가했습니다. 기존 DB에는 위 003 파일만 실행합니다.

```sql
-- orders의 컬럼 정의에 추가
checkout_key uuid,

-- orders 생성 이후 추가
CREATE UNIQUE INDEX orders_checkout_key_idx ON public.orders(checkout_key);
```

### app/session_auth.py와 app/routers/profile.py — 공통 함수 이동

profile.py에 있던 아래 함수를 session_auth.py로 옮겼습니다. profile.py에서는 기존 함수 정의를 삭제하고, session_auth import 목록의 hash_session_token을 lock_account로 교체했습니다.

```python
def lock_account(cursor, user_id: int, token: str):
    # 회원 → 세션 순서로 잠가 탈퇴·수정·주문이 엇갈리지 않게 한다.
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
        WHERE user_id = %s AND token_hash = %s AND expires_at > now() FOR UPDATE
        """,
        (user_id, hash_session_token(token)),
    )
    return user if cursor.fetchone() else None
```

### app/main.py — 추가·변경 부분

```python
from app.routers import accounts, auth, profile, products, shopping

app.include_router(shopping.router)
```

### app/routers/products.py — 변경 부분

import를 아래처럼 바꾸고 상세 함수를 수정했습니다.

```python
from app.session_auth import current_user, session_csrf_token, session_token

@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: ProductId):
    rows = read_products(product_id)
    user = current_user(request)
    return templates.TemplateResponse(
        request=request,
        name="product_detail.html",
        context={
            "product": product_view(rows[0]) if rows else None,
            "user": user,
            "csrf_token": session_csrf_token(session_token(request)) if user else "",
        },
        status_code=200 if rows else 404,
        headers={"Cache-Control": "no-store"},
    )
```

### templates/product_detail.html — 상품 설명 아래에 추가

```html
                {% if product.stock > 0 %}
                    <form action="/cart/items" method="post">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                        <input type="hidden" name="product_id" value="{{ product.id }}">
                        <label for="quantity">수량</label>
                        <input id="quantity" name="quantity" type="number" min="1"
                               max="{{ [product.stock, 999] | min }}" value="1" required>
                        <div class="action-row">
                            <button type="submit" name="action" value="cart">장바구니 담기</button>
                            <button type="submit" name="action" value="buy" class="secondary">바로 구매</button>
                        </div>
                    </form>
                {% endif %}
```

### templates/catalog_base.html과 templates/account.html — 링크 추가

공통 메뉴에 추가했습니다.

```html
<a href="/cart">장바구니</a>
```

회원정보 화면에도 추가했습니다.

```html
<p class="hint"><a href="/cart">장바구니 보기</a></p>
```

### static/style.css — 추가 부분

```css
/* 장바구니와 주문서는 모바일에서 세로로 배치한다. */
.shopping-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; margin-top: 24px; }
.shopping-items { display: grid; gap: 16px; }
.shopping-item, .order-summary { min-width: 0; padding: 24px; border: 1px solid #dce2ea; border-radius: 16px; background: #fff; overflow-wrap: anywhere; }
.shopping-item h2, .order-summary h2 { margin-top: 0; font-size: 1.15rem; }
.quantity-form { display: grid; grid-template-columns: auto minmax(64px, 100px) minmax(90px, 1fr); align-items: center; gap: 10px; }
.quantity-form label, .quantity-form input, .quantity-form button { margin: 0; }
.quantity-form button { padding: 10px; }
.action-row { display: flex; flex-wrap: wrap; gap: 12px; }
.action-row button { flex: 1 1 150px; }
.secondary { background: #e8edf4; color: #243855; }
.secondary:hover { background: #d8e1ee; }
textarea { width: 100%; margin-top: 6px; padding: 12px; border: 1px solid #8794a8; border-radius: 8px; font: inherit; resize: vertical; }
@media (min-width: 900px) {
    .shopping-layout { grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); align-items: start; }
    .order-summary { position: sticky; top: 24px; }
}
```

## 3. 요청 → 처리 → 응답

### ① 상품을 장바구니에 담기

상품 상세 → 수량 입력 → 장바구니 담기 → 로그인·CSRF 확인 → 회원·세션 잠금 및 재확인 → cart 주문 조회 또는 생성 → 상품 재고 검사 → order_items 저장 → 장바구니 이동.

`orders.status`는 `cart`, `orders.total_amount`는 0으로 유지합니다. 화면에 보여줄 합계는 현재 상품 가격 × 수량으로 계산합니다. 재고는 줄이지 않습니다.

여러 창에서 같은 회원의 장바구니를 동시에 변경해도 서로 덮어쓰지 않도록 회원을 먼저 잠급니다. 주문 처리와 탈퇴도 같은 회원 잠금 규칙을 사용합니다.

### ② 수량 변경·삭제

장바구니에서 수량 변경 또는 삭제 요청 → 로그인·CSRF 확인 → 본인의 cart 주문에서 해당 상품을 찾음 → 수량 갱신 또는 상세 행 삭제 → 장바구니 이동.

상품을 모두 삭제해도 빈 cart 행은 남을 수 있습니다. 회원당 활성 cart는 최대 하나이며 다음에 담을 때 재사용합니다. 결제 대기 주문은 이 경로로 수정하지 않습니다.

### ③ 주문서 작성

장바구니의 주문서 작성 → 상품·재고·현재 가격 조회 → 합계 표시 → 배송정보 입력 → 주문 생성.

주문서 조회만으로 pending 주문을 만들지는 않습니다. 폼 제출 시 다음 내용을 함께 저장합니다.

| 테이블 | 변화 |
|---|---|
| orders | cart → pending, 총액·배송정보·placed_at·checkout_key 저장 |
| order_items | 확정 시점 상품명·단가 사본 저장 |
| products | 재고 변경 없음 |
| payments | 아직 생성하지 않음 |

주문서를 본 뒤 상품명·가격·수량이 달라지면 fingerprint가 맞지 않으므로 다시 주문서를 열어 확인하게 합니다. 서버는 브라우저가 전달한 금액을 저장하지 않고 DB 가격으로 직접 계산합니다.

### ④ 바로 구매

상품 상세의 바로 구매 → 선택한 상품과 수량의 주문서 → 배송정보 입력 → 별도의 pending 주문 및 상세 생성.

기존 장바구니는 그대로 유지합니다. 장바구니 수량과 바로 구매 수량을 합치지 않습니다.

### ⑤ 비로그인 동작과 이전 화면 복귀

- 장바구니 메뉴 클릭: 로그인 후 `/cart`로 복귀합니다.
- 상품 상세에서 담기·바로 구매: 로그인 후 해당 상세 화면으로 복귀합니다. 수량을 다시 선택하고 버튼을 누릅니다.
- 직접 주문서나 주문 상세 URL 접근: 로그인 후 해당 화면으로 복귀합니다.

로그인 성공만으로 장바구니 추가나 주문 생성을 자동 실행하지 않습니다. 이전 POST 요청의 입력을 자동 재전송하지 않고 사용자가 다시 확인하도록 했습니다. `next`의 외부 주소 제한도 기존 공통 함수를 사용합니다.

### ⑥ 주문 중복과 권한

- 같은 주문서의 `checkout_key`로 같은 배송정보·상품 사본을 다시 제출하면 기존 주문을 반환합니다.
- 같은 키로 배송정보나 상품 사본을 바꾸면 오류로 거부합니다.
- 주문서를 새로 열면 새 키를 발급합니다. 새 주문서를 새로 제출하는 것은 별개의 주문입니다.
- cart 주문은 한 번 pending으로 전환하면 같은 장바구니로 다시 확정하지 않습니다.
- 주문 상세는 로그인한 회원 본인의 주문만 조회합니다. 다른 회원의 번호를 넣으면 404로 응답합니다.

## 4. 직접 실행·확인하는 방법

### ① Supabase에 컬럼 추가

서버를 다시 실행하기 전에 Supabase SQL Editor에서 **새 쿼리**를 열고 [003_order_checkout_key.sql](../sql/003_order_checkout_key.sql)의 전체 내용을 붙여넣어 실행하세요.

이 SQL은 기존 행을 삭제하거나 기존 `users`를 변경하지 않습니다. `orders`에 `checkout_key` 컬럼과 중복 방지 인덱스를 추가합니다. 기존 행의 해당 컬럼은 NULL입니다.

`001_create_tables.sql`이나 샘플 상품 SQL은 다시 실행하지 않습니다. `003`을 실행하지 않으면 주문 생성 시 DB 처리 오류가 발생합니다.

### ② 서버 다시 시작

기존 서버 터미널에서 `Ctrl + C`를 누른 뒤 같은 가상환경에서 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

아래는 사용자가 직접 확인할 기준이며 실행 결과를 대신 만들어 제시한 것이 아닙니다.

### ③ 장바구니 확인

1. [상품 목록](http://127.0.0.1:8000/products)에서 재고가 있는 상품을 선택합니다.
2. 로그인한 상태로 수량을 입력하고 **장바구니 담기**를 누릅니다.
3. [장바구니](http://127.0.0.1:8000/cart)에 상품과 합계가 보이는지 확인합니다.
4. 수량 변경을 저장해 합계가 바뀌는지 확인합니다.
5. 다른 상품을 담거나 삭제 버튼을 눌러 확인합니다.

품절 상품 상세에는 구매 폼을 표시하지 않습니다. 판매 중단·재고 부족은 서버에서도 검사합니다. 상품을 담는 것만으로 재고가 줄어들지 않는지 Supabase `products`에서 확인할 수 있습니다.

### ④ 주문 생성 확인

1. 장바구니에서 **주문서 작성**을 누릅니다.
2. 현재 상품·수량·합계를 확인합니다.
3. 학습용 수령인·연락처·주소를 입력합니다. 예: 학습회원, 010-1234-5678, 서울시 학습로 123.
4. **주문 생성**을 누릅니다.
5. `/orders/실제주문번호` 화면에서 **결제 대기**가 보이는지 확인합니다.
6. 주문 번호를 기록하거나 해당 탭을 유지합니다. 다음 결제 단계에서 사용할 수 있습니다.

연락처는 숫자 8~15자리를 포함해야 하며 숫자·공백·하이픈·괄호·더하기 기호를 허용합니다. 주소는 5~300자입니다. 학습 중에는 실제 개인정보 대신 예시 값을 사용해도 됩니다.

Supabase에서는 `orders`의 pending·총액·배송정보와 `order_items`의 상품 사본을 확인합니다. 상품 재고는 그대로이며 payments에는 이번 주문의 결제가 아직 없습니다.

### ⑤ 바로 구매와 비로그인 확인

| 시도 | 확인 기준 |
|---|---|
| 장바구니 상품을 남겨 두고 다른 상품 바로 구매 | 별도 주문 생성, 기존 장바구니 유지 |
| 로그아웃 후 장바구니 메뉴 클릭 | 로그인 화면 이동, 성공 후 장바구니 복귀 |
| 로그아웃 후 상품 담기 | 로그인 후 상품 상세 복귀, 다시 담기 필요 |
| 주문 화면 새로고침 | GET 조회만 반복, 새 주문 생성 안 함 |
| 주문 확정 후 장바구니 열기 | 해당 상품은 이전 cart에서 pending 주문으로 이동했으므로 활성 cart에는 없음 |

아직 결제 버튼과 구매내역 목록은 구현하지 않았습니다. 결제 대기 화면까지 확인하면 이번 단계의 목표를 달성한 것입니다.

### ⑥ API 주소와 직접 확인 방법

HTML 화면은 JSON API를 호출하지 않고 같은 파이썬 처리 함수를 사용합니다. 아래 API는 별도로 데이터를 확인하거나 호출할 때 사용할 수 있습니다.

| 메서드 | 주소 | 역할 |
|---|---|---|
| GET | /api/cart | 본인의 장바구니와 csrf_token 조회 |
| POST | /api/cart/items | product_id·quantity로 추가 |
| PATCH | /api/cart/items/{product_id} | quantity로 수량 교체 |
| DELETE | /api/cart/items/{product_id} | 삭제 |
| GET | /api/checkout | 장바구니 주문서 미리보기 |
| GET | /api/checkout?source=buy&product_id=실제번호&quantity=1 | 바로 구매 미리보기 |
| POST | /api/orders | 주문 생성 |
| GET | /api/orders/{order_id} | 본인 주문 조회 |

같은 브라우저로 로그인한 뒤 [장바구니 API](http://127.0.0.1:8000/api/cart)를 열 수 있습니다. API의 미로그인은 HTML 이동 대신 401 JSON으로 응답합니다. 상태 변경 API는 `GET /api/cart`에서 받은 `csrf_token`을 **X-CSRF-Token 헤더**에 넣어야 합니다. 이 값은 원본 로그인 쿠키와 다릅니다.

API 설명 화면 `/docs`에서 상태 변경 요청을 호출할 때도 해당 헤더가 필요합니다. 요청 본문 구조는 화면에 표시됩니다. 주문 생성에는 미리보기에서 받은 `source`, `cart_id` 또는 `product_id`, `quantity`, `checkout_key`, `fingerprint`와 배송정보를 사용합니다. 브라우저 폼에서는 이 값을 자동 전달하므로 처음에는 화면을 통한 확인만 해도 충분합니다.

## 5. 피드백 질문

먼저 **003 SQL 실행 → 서버 재시작 → 상품 한 개 장바구니 담기**까지 확인해 주세요.

- 장바구니에 상품과 금액이 보이나요?
- 수량 변경과 삭제가 되나요?
- 주문서에서 주문을 만들면 결제 대기 화면이 보이나요?
- 오류나 설명이 필요한 부분이 있나요?

확인 결과를 받기 전에는 STEP 6의 모의 결제와 구매내역으로 넘어가지 않습니다.

## 참고

- [PostgreSQL 공식 문서: 행 잠금](https://www.postgresql.org/docs/17/explicit-locking.html)
- [Psycopg 공식 문서: 트랜잭션과 컨텍스트](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)

이번 작업은 파일 작성만 수행했습니다. 패키지 설치·코드 실행·SQL 실행·DB 변경·테스트는 하지 않았습니다.
