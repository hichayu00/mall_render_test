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
