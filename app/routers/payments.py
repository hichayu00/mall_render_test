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
