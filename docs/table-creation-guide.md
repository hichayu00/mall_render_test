# 기존 users를 보존하고 쇼핑몰 테이블 만들기

## 이번 변경의 목표

기존에 사용하던 `public.users`를 그대로 두고, 학습용 회원 테이블을 `public.shop_users`라는 이름으로 별도 생성합니다.

기존 `users`를 이름 변경하거나 회원정보를 복사하는 작업은 아닙니다. `shop_users`는 처음에는 비어 있으며, 이후 쇼핑몰 회원가입으로 데이터를 추가합니다.

## 바뀐 파일과 부분

| 파일 | 변경 내용 |
|---|---|
| [erd.mmd](erd.mmd) | 회원 테이블을 shop_users로 표시 |
| [table-definition.md](table-definition.md) | 테이블 정의·관계·구매 예시의 회원 테이블 이름 변경 |
| [001_create_tables.sql](../sql/001_create_tables.sql) | shop_users 생성 및 회원 외래키·RLS·권한 설정 대상 변경 |

생성 구문은 다음과 같이 바뀌었습니다. 아래는 변경 부분을 설명하는 발췌이며, 단독 실행용 SQL은 아닙니다.

```sql
CREATE TABLE public.shop_users (
    -- 전체 컬럼은 001_create_tables.sql 참고
);
```

주문과 세션에서 회원을 가리키는 부분도 바뀌었습니다.

```sql
-- sessions.user_id의 연결 대상
REFERENCES public.shop_users(id) ON DELETE CASCADE

-- orders.user_id의 연결 대상
REFERENCES public.shop_users(id) ON DELETE RESTRICT
```

`user_id`는 회원 번호를 담는 컬럼 이름입니다. 이 컬럼 이름은 그대로 두고 연결 대상만 바꿨습니다.

## 동작 흐름

쇼핑몰 회원가입 → `shop_users`에 저장 → 로그인 시 `sessions`에서 해당 회원 연결 → 주문 시 `orders.user_id`로 같은 회원 연결.

기존 `users`는 이 구매 흐름에서 사용하지 않습니다. 회원 샘플을 넣지 않는 상품 데이터 SQL은 수정할 필요가 없습니다.

## 직접 실행하고 확인하기

아직 생성 SQL을 성공적으로 실행하지 않은 상태를 가정합니다. 이전에 생성한 쇼핑몰 테이블이 이미 있다면 이 파일은 기존 구조를 바꾸는 마이그레이션이 아니므로 먼저 해당 상황을 알려주세요.

1. VSCode에서 수정된 [001_create_tables.sql](../sql/001_create_tables.sql)을 엽니다.
2. Supabase SQL Editor의 기존 쿼리 내용을 수정된 파일 전체 내용으로 교체합니다.
3. SQL을 실행합니다. 이전에 복사한 `users` 버전은 사용하지 마세요.
4. Table Editor에서 기존 `users`와 새로운 `shop_users`가 각각 있는지 확인합니다.
5. 성공한 다음 [002_seed_products.sql](../sql/002_seed_products.sql)을 실행합니다.

새로 생성할 학습용 테이블은 `shop_users`, `sessions`, `products`, `orders`, `order_items`, `payments`의 6개입니다. 다른 이름도 충돌한다면 기존 테이블을 삭제하지 말고 오류 메시지를 알려주세요.

## 확인 결과 공유

기존 `users`가 그대로 있고 `shop_users`가 새로 생겼는지 알려주세요. 오류가 있다면 오류 메시지를 보내주세요. 코드·SQL 실행 및 테스트는 사용자가 직접 진행하며, 다음 단계는 확인 후 진행합니다.
