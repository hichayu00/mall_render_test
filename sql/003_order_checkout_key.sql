BEGIN;

-- 주문 생성 버튼을 다시 눌러도 같은 주문을 반환하기 위한 요청 번호다.
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS checkout_key uuid;
CREATE UNIQUE INDEX IF NOT EXISTS orders_checkout_key_idx
    ON public.orders(checkout_key);

COMMIT;
