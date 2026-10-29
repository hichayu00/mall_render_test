BEGIN;

-- 기존 샘플 상품에서 비어 있는 이미지 경로만 채운다.
UPDATE public.products AS p
SET image_url = photos.image_url
FROM (
    VALUES
        ('BAG-001', '/static/images/products/eco-bag.png'),
        ('CUP-001', '/static/images/products/mug.png'),
        ('NOTE-001', '/static/images/products/notebook.png'),
        ('POUCH-001', '/static/images/products/pouch.png'),
        ('BOTTLE-001', '/static/images/products/tumbler.png')
) AS photos(sku, image_url)
WHERE p.sku = photos.sku
  AND (p.image_url IS NULL OR btrim(p.image_url) = '');

COMMIT;
