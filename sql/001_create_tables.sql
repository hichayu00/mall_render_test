BEGIN;

-- 1. 회원
-- Supabase Auth 대신 FastAPI에서 직접 인증한다.
CREATE TABLE public.shop_users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text UNIQUE,
    password_hash text,
    name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,

    CONSTRAINT shop_users_email_format CHECK (
        email IS NULL
        OR (
            email = lower(btrim(email))
            AND email <> ''
        )
    ),

    -- 탈퇴 시 개인정보와 비밀번호 해시를 제거한다.
    CONSTRAINT shop_users_account_state CHECK (
        (
            deleted_at IS NULL
            AND email IS NOT NULL
            AND password_hash IS NOT NULL
            AND name IS NOT NULL
            AND btrim(password_hash) <> ''
            AND btrim(name) <> ''
        )
        OR
        (
            deleted_at IS NOT NULL
            AND email IS NULL
            AND password_hash IS NULL
            AND name IS NULL
        )
    )
);

-- 2. 로그인 세션
CREATE TABLE public.sessions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL
        REFERENCES public.shop_users(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,

    CONSTRAINT sessions_token_hash_format
        CHECK (token_hash ~ '^[0-9a-f]{64}$'),

    CONSTRAINT sessions_expiration
        CHECK (expires_at > created_at)
);

CREATE INDEX sessions_user_id_idx
    ON public.sessions(user_id);

CREATE INDEX sessions_expires_at_idx
    ON public.sessions(expires_at);

-- 3. 상품
CREATE TABLE public.products (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    price bigint NOT NULL,
    stock integer NOT NULL DEFAULT 0,
    image_url text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT products_sku_not_blank
        CHECK (btrim(sku) <> ''),

    CONSTRAINT products_name_not_blank
        CHECK (btrim(name) <> ''),

    CONSTRAINT products_price_positive
        CHECK (price > 0),

    CONSTRAINT products_stock_nonnegative
        CHECK (stock >= 0)
);

-- 4. 장바구니 및 주문
CREATE TABLE public.orders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    checkout_key uuid,
    user_id bigint NOT NULL
        REFERENCES public.shop_users(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'cart',
    total_amount bigint NOT NULL DEFAULT 0,

    -- 주문 시 배송정보 사본을 저장한다.
    -- 탈퇴 시 익명화할 수 있도록 NULL을 허용한다.
    recipient_name text,
    recipient_phone text,
    shipping_address text,

    created_at timestamptz NOT NULL DEFAULT now(),
    placed_at timestamptz,
    paid_at timestamptz,

    CONSTRAINT orders_status_valid
        CHECK (status IN ('cart', 'pending', 'paid')),

    CONSTRAINT orders_total_nonnegative
        CHECK (total_amount >= 0),

    CONSTRAINT orders_state_fields CHECK (
        (
            status = 'cart'
            AND total_amount = 0
            AND placed_at IS NULL
            AND paid_at IS NULL
        )
        OR
        (
            status = 'pending'
            AND total_amount > 0
            AND placed_at IS NOT NULL
            AND paid_at IS NULL
        )
        OR
        (
            status = 'paid'
            AND total_amount > 0
            AND placed_at IS NOT NULL
            AND paid_at IS NOT NULL
            AND paid_at >= placed_at
        )
    )
);

-- 회원당 활성 장바구니는 최대 하나다.
CREATE UNIQUE INDEX orders_checkout_key_idx
    ON public.orders(checkout_key);

CREATE UNIQUE INDEX orders_one_cart_per_user_idx
    ON public.orders(user_id)
    WHERE status = 'cart';

CREATE INDEX orders_user_history_idx
    ON public.orders(user_id, created_at DESC);

-- 5. 주문 상세
CREATE TABLE public.order_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL
        REFERENCES public.orders(id) ON DELETE RESTRICT,
    product_id bigint NOT NULL
        REFERENCES public.products(id) ON DELETE RESTRICT,

    -- 주문 확정 시 서버에서 최신 상품정보로 다시 저장한다.
    product_name text NOT NULL,
    unit_price bigint NOT NULL,
    quantity integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT order_items_order_product_unique
        UNIQUE (order_id, product_id),

    CONSTRAINT order_items_name_not_blank
        CHECK (btrim(product_name) <> ''),

    CONSTRAINT order_items_price_positive
        CHECK (unit_price > 0),

    CONSTRAINT order_items_quantity_positive
        CHECK (quantity > 0)
);

CREATE INDEX order_items_product_id_idx
    ON public.order_items(product_id);

-- 6. 결제 시도
CREATE TABLE public.payments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL
        REFERENCES public.orders(id) ON DELETE RESTRICT,

    -- 같은 결제 요청을 재전송해도 중복 처리하지 않는다.
    idempotency_key uuid NOT NULL UNIQUE,

    method text NOT NULL DEFAULT 'mock',
    status text NOT NULL,
    amount bigint NOT NULL,
    failure_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT payments_method_valid
        CHECK (method = 'mock'),

    CONSTRAINT payments_status_valid
        CHECK (status IN ('succeeded', 'failed')),

    CONSTRAINT payments_amount_positive
        CHECK (amount > 0),

    CONSTRAINT payments_result_fields CHECK (
        (
            status = 'succeeded'
            AND failure_reason IS NULL
        )
        OR
        (
            status = 'failed'
            AND failure_reason IS NOT NULL
            AND btrim(failure_reason) <> ''
        )
    )
);

-- 주문 하나의 성공 결제는 최대 하나다.
CREATE UNIQUE INDEX payments_one_success_per_order_idx
    ON public.payments(order_id)
    WHERE status = 'succeeded';

CREATE INDEX payments_order_history_idx
    ON public.payments(order_id, created_at DESC);

-- 브라우저에서 Supabase Data API로 테이블에 직접 접근하지 않는다.
ALTER TABLE public.shop_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES
    ON TABLE
        public.shop_users,
        public.sessions,
        public.products,
        public.orders,
        public.order_items,
        public.payments
    FROM anon, authenticated;

COMMIT;
