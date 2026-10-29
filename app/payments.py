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
