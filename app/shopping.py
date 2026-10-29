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
        raise HTTPException(503, "장바구니·주문·결제를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.") from None


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
        cursor.execute(
            """
            SELECT id, status, amount, failure_reason, created_at
            FROM public.payments WHERE order_id = %s ORDER BY id DESC
            """,
            (order_id,),
        )
        order["payments"] = cursor.fetchall()
        return order
