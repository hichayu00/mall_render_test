from typing import Annotated
from urllib.parse import urlsplit

import psycopg
from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row
from pydantic import BaseModel, ValidationError

from app.config import BASE_DIR
from app.database import get_connection
from app.payments import paid_confirmation
from app.session_auth import current_user, session_csrf_token, session_token


router = APIRouter(tags=["상품"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")
ProductId = Annotated[int, Path(gt=0, le=9_223_372_036_854_775_807)]

# DB 이미지가 비어 있으면 샘플 상품 코드에 맞는 기본 사진을 사용한다.
PRODUCT_IMAGES = {
    "BAG-001": "/static/images/products/eco-bag.png",
    "CUP-001": "/static/images/products/mug.png",
    "NOTE-001": "/static/images/products/notebook.png",
    "POUCH-001": "/static/images/products/pouch.png",
    "BOTTLE-001": "/static/images/products/tumbler.png",
}


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
                rows = cursor.fetchall()
                for row in rows:
                    if not row["image_url"] or not row["image_url"].strip():
                        row["image_url"] = PRODUCT_IMAGES.get(row["sku"])
                return rows
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
