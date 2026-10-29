import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.config import BASE_DIR
from app.database import get_connection
from app.routers import accounts, auth, profile, products, shopping, payments


app = FastAPI(title="학습용 쇼핑몰")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(accounts.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(products.router)
app.include_router(shopping.router)
app.include_router(payments.router)


@app.get("/")
def home():
    return RedirectResponse("/products", status_code=303)


@app.get("/health")
def server_health():
    return {"status": "ok"}


@app.get("/health/db")
def database_health():
    try:
        # 연결은 처리가 끝나면 자동으로 닫힌다.
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM public.products")
                product_count = cursor.fetchone()[0]
    except (psycopg.Error, ValidationError):
        # DB 접속정보와 상세 오류를 응답에 노출하지 않는다.
        raise HTTPException(
            status_code=503,
            detail="DB 연결 또는 설정을 확인해 주세요.",
        ) from None

    return {"status": "ok", "product_count": product_count}
