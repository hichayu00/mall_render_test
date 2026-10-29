# 샘플 상품 사진 등록

## 1. 이번 작업의 목표

기존 샘플 상품 5개에 맞는 **AI 생성 상품 사진**을 추가했습니다. 실제 판매 상품을 촬영한 사진이 아니라 학습용으로 만든 이미지입니다.

밝고 부드러운 배경의 상품 사진 스타일을 사용했습니다. 상품 목록과 상세 화면에 동일한 사진을 표시합니다. 다음 결제 단계로는 아직 진행하지 않습니다.

## 2. 생성·수정한 파일과 코드

### 상품 사진

모든 사진은 내장 이미지 생성 도구를 사용해 상품별로 한 장씩 생성하고, 아래 프로젝트 경로로 복사했습니다. 원본을 덮어쓰거나 이미지 편집 스크립트를 실행하지 않았습니다.

| 상품 코드 | 상품 | 저장 파일 |
|---|---|---|
| BAG-001 | 데일리 에코백 | [eco-bag.png](../static/images/products/eco-bag.png) |
| CUP-001 | 베이직 머그컵 | [mug.png](../static/images/products/mug.png) |
| NOTE-001 | 심플 노트 | [notebook.png](../static/images/products/notebook.png) |
| POUCH-001 | 미니 파우치 | [pouch.png](../static/images/products/pouch.png) |
| BOTTLE-001 | 스테인리스 텀블러 | [tumbler.png](../static/images/products/tumbler.png) |

사진은 `static/images/products/` 폴더에 들어 있습니다. Node.js나 새로운 파이썬 패키지를 설치할 필요가 없습니다.

### app/routers/products.py — 변경 부분

상품 코드별 기본 사진 경로를 추가했습니다.

```python
# DB 이미지가 비어 있으면 샘플 상품 코드에 맞는 기본 사진을 사용한다.
PRODUCT_IMAGES = {
    "BAG-001": "/static/images/products/eco-bag.png",
    "CUP-001": "/static/images/products/mug.png",
    "NOTE-001": "/static/images/products/notebook.png",
    "POUCH-001": "/static/images/products/pouch.png",
    "BOTTLE-001": "/static/images/products/tumbler.png",
}
```

`read_products`의 조회 결과 반환 부분을 다음과 같이 바꿨습니다. DB 값을 UPDATE하는 코드가 아니라, 응답에 사용할 이미지 경로를 채우는 코드입니다.

```python
rows = cursor.fetchall()
for row in rows:
    if not row["image_url"] or not row["image_url"].strip():
        row["image_url"] = PRODUCT_IMAGES.get(row["sku"])
return rows
```

기존 DB에 별도의 이미지 주소가 등록되어 있다면 그 주소를 우선 사용합니다. 샘플 코드가 아닌 다른 상품은 기본 사진이 없으므로 기존 대체 문구를 유지합니다.

### sql/002_seed_products.sql — 변경 부분

처음 DB를 구성하는 경우에도 이미지 경로가 들어가도록 각 샘플 상품의 `image_url`만 위 표의 경로로 바꿨습니다. 다른 값은 유지했습니다.

이미 상품을 등록했다면 이 파일을 다시 실행할 필요가 없습니다. 기존 파일의 `ON CONFLICT DO NOTHING`은 기존 상품을 갱신하지 않습니다.

### sql/004_product_images.sql — 선택 실행용 전체 코드

기존 상품의 이미지 경로를 DB에도 저장하고 싶을 때 사용하는 SQL입니다. 사진 표시만 확인하려면 실행하지 않아도 됩니다. 이미 별도 이미지 주소가 등록된 상품은 변경하지 않습니다.

```sql
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
```

## 3. 동작 방식

```text
상품 목록·상세 요청
    → DB에서 상품과 image_url 조회
    → image_url이 비었으면 SKU에 맞는 프로젝트 기본 사진 선택
    → HTML의 img 태그에 /static/images/products/... 경로 전달
    → 브라우저가 FastAPI에서 이미지 파일을 받아 표시
```

DB에 사진 파일 자체를 넣는 방식이 아닙니다. **파일은 프로젝트 폴더에 있고, DB에는 파일을 찾는 경로를 저장**합니다. 기본 사진 연결표도 같은 경로를 사용합니다.

상품 API의 `image_url`에도 화면에 사용할 기본 사진 경로가 반환됩니다. 이것은 조회 응답을 채우는 처리이며, 별도 SQL을 실행하기 전까지 Supabase의 기존 NULL 값을 실제로 바꾸지는 않습니다.

## 4. 직접 확인하는 방법

1. 서버 실행 중인 터미널에서 `Ctrl + C`로 종료합니다.
2. 기존 가상환경에서 서버를 다시 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

3. [상품 목록](http://127.0.0.1:8000/products)을 새로고침합니다.
4. 각 상품에 맞는 사진이 보이는지 확인합니다.
5. 상품 카드를 눌러 상세 화면에도 같은 사진이 보이는지 확인합니다.

캐시 때문에 이전 화면이 남아 있으면 `Ctrl + F5`로 새로고침합니다. 직접 이미지 경로도 열 수 있습니다. 예: [머그컵 사진](http://127.0.0.1:8000/static/images/products/mug.png).

DB에도 경로를 저장하려면 Supabase SQL Editor의 새 쿼리에서 [004_product_images.sql](../sql/004_product_images.sql)을 실행하고 `products.image_url`을 확인하세요. 기본 연결 덕분에 이 작업은 사진 확인의 필수 조건은 아닙니다.

이미지는 생성 후 내용과 구도를 눈으로 확인했습니다. 웹 서버·화면·SQL은 실행하거나 테스트하지 않았으며 DB 데이터도 직접 변경하지 않았습니다.

## 5. 피드백 질문

상품 목록과 상세 화면에서 에코백·머그컵·노트·파우치·텀블러 사진이 각각 보이나요? 색상이나 구도를 바꾸고 싶은 사진이 있으면 알려주세요. 확인 후 원래 순서인 STEP 6으로 이어갑니다.

## 이미지 생성 기록

- 사용 방식: 내장 `image_gen` 도구, 상품별 신규 생성 5회
- 배경: 불투명한 밝은 스튜디오 배경
- 참조 이미지: 없음
- 사용 범위: 학습용 쇼핑몰 샘플 상품
- 최종 저장 위치: 프로젝트의 `static/images/products/`
- 사용 스킬: [imagegen SKILL.md](C:/Users/Playdata/.codex/skills/.system/imagegen/SKILL.md)

### 실제 생성 프롬프트

아래는 각 사진 생성에 사용한 전체 프롬프트입니다.

### eco-bag

```text
Use case: product-mockup. Asset type: individual ecommerce product photograph for a small Korean learning shop. Generate exactly one photorealistic catalog photo, landscape 4:3 composition. Seamless warm light-gray/off-white studio backdrop, soft diffused daylight, subtle natural contact shadow, realistic material texture. Product centered, fully visible including edges with generous safe margins so both 4:3 and square crops work. Clean contemporary unbranded everyday goods, no people, no hands, no extra props, no packaging, no text, no logos, no watermark, no collage, no labels or price graphics. Subject: a single natural cream cotton canvas tote bag with two long matching fabric handles, visible fine woven cotton texture, standing upright with a little natural volume, front three-quarter view.
```

### mug

```text
Use case: product-mockup. Asset type: individual ecommerce product photograph for a small Korean learning shop. Generate exactly one photorealistic catalog photo, landscape 4:3 composition. Seamless warm light-gray/off-white studio backdrop, soft diffused daylight, subtle natural contact shadow, realistic material texture. Product centered, fully visible including edges with generous safe margins so both 4:3 and square crops work. Clean contemporary unbranded everyday goods, no people, no hands, no extra props, no packaging, no text, no logos, no watermark, no collage, no labels or price graphics. Subject: a single basic 350ml off-white ceramic mug, comfortable rounded handle, gently rounded cylinder, clean empty interior, satin glaze, three-quarter view slightly from above.
```

### notebook

```text
Use case: product-mockup. Asset type: individual ecommerce product photograph for a small Korean learning shop. Generate exactly one photorealistic catalog photo, landscape 4:3 composition. Seamless warm light-gray/off-white studio backdrop, soft diffused daylight, subtle natural contact shadow, realistic material texture. Product centered, fully visible including edges with generous safe margins so both 4:3 and square crops work. Clean contemporary unbranded everyday goods, no people, no hands, no extra props, no packaging, no text, no logos, no watermark, no collage, no labels or price graphics. Subject: a single simple sage-green ruled paper notebook, opened slightly with the front cover folded aside so clean evenly spaced fine horizontal ruling on blank cream pages is visible. No writing or letters. Slightly elevated three-quarter product view, the entire notebook in frame.
```

### pouch

```text
Use case: product-mockup. Asset type: individual ecommerce product photograph for a small Korean learning shop. Generate exactly one photorealistic catalog photo, landscape 4:3 composition. Seamless warm light-gray/off-white studio backdrop, soft diffused daylight, subtle natural contact shadow, realistic material texture. Product centered, fully visible including edges with generous safe margins so both 4:3 and square crops work. Clean contemporary unbranded everyday goods, no people, no hands, no extra props, no packaging, no text, no logos, no watermark, no collage, no labels or price graphics. Subject: a single small sand-beige woven fabric zippered pouch for everyday small belongings, horizontal rectangular shape with rounded corners, zipper closed, short matching zipper pull, realistic fine cotton fabric, three-quarter view.
```

### tumbler

```text
Use case: product-mockup. Asset type: individual ecommerce product photograph for a small Korean learning shop. Generate exactly one photorealistic catalog photo, landscape 4:3 composition. Seamless warm light-gray/off-white studio backdrop, soft diffused daylight, subtle natural contact shadow, realistic material texture. Product centered, fully visible including edges with generous safe margins so both 4:3 and square crops work. Clean contemporary unbranded everyday goods, no people, no hands, no extra props, no packaging, no text, no logos, no watermark, no collage, no labels or price graphics. Subject: a single 500ml brushed stainless-steel travel tumbler with a simple matte charcoal screw-on drinking lid, upright tall cylindrical silhouette gently tapered at bottom, no handle or straw, subtle realistic brushed steel reflections, three-quarter view.
```
