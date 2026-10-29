BEGIN;

INSERT INTO public.products (
    sku,
    name,
    description,
    price,
    stock,
    image_url,
    is_active
)
VALUES
    (
        'BAG-001',
        '데일리 에코백',
        '가볍게 들고 다니기 좋은 면 소재 에코백입니다.',
        15000,
        30,
        '/static/images/products/eco-bag.png',
        true
    ),
    (
        'CUP-001',
        '베이직 머그컵',
        '집과 사무실에서 사용하기 좋은 350ml 머그컵입니다.',
        12000,
        40,
        '/static/images/products/mug.png',
        true
    ),
    (
        'NOTE-001',
        '심플 노트',
        '공부와 업무 기록에 사용할 수 있는 줄 노트입니다.',
        5000,
        100,
        '/static/images/products/notebook.png',
        true
    ),
    (
        'POUCH-001',
        '미니 파우치',
        '작은 소지품을 정리하는 지퍼형 파우치입니다.',
        9000,
        20,
        '/static/images/products/pouch.png',
        true
    ),
    (
        'BOTTLE-001',
        '스테인리스 텀블러',
        '일상에서 사용하기 좋은 500ml 텀블러입니다.',
        25000,
        0,
        '/static/images/products/tumbler.png',
        true
    )
ON CONFLICT (sku) DO NOTHING;

COMMIT;
