# 디자인 변경 — 포근하고 따뜻한 작은 쇼핑몰

## 1. 이번 작업의 목표

쇼핑몰 전체를 크림색·브라운·살구색 중심의 따뜻한 분위기로 변경했습니다. 화면의 표현을 바꾸는 작업이며 상품·회원·장바구니·주문·결제의 처리 방식은 유지합니다.

서버나 브라우저를 실행해 확인하지 않았습니다. SQL 실행·DB 접속·패키지 설치도 하지 않았습니다. 아래 설명은 작성한 디자인과 사용자가 직접 확인할 기준입니다.

### 디자인 방향

| 요소 | 적용 내용 |
|---|---|
| 배경 | 따뜻한 크림색, 회원 화면은 부드러운 배경 그라데이션 |
| 글자 | 짙은 브라운 본문과 차분한 갈색 보조 문구 |
| 버튼 | 브라운 기본 버튼과 크림색 보조 버튼 |
| 사진 | 앞서 생성한 상품 사진 재사용 |
| 상품 목록 | 머그컵 사진과 다정한 소개 문구, 여유 있는 카드 배치 |
| 회원 화면 | 둥근 종이 카드 같은 테두리와 그림자 |
| 장바구니·주문서·결제 | 크림색 요약 카드와 같은 버튼·입력창 스타일 |
| 상태 표시 | 성공은 차분한 연두색, 실패는 옅은 살구색 계열 |
| 공통 영역 | 작은 꽃 모양 장식, 안내 띠, 현재 메뉴 강조, 하단 인사말 |

외부 폰트나 이미지 서비스를 추가하지 않았습니다. 운영체제에 있는 글꼴과 기존 로컬 이미지를 사용하므로 설치할 도구가 없습니다. 제목 글꼴의 모양은 PC에 설치된 글꼴에 따라 조금 다를 수 있습니다.

## 2. 바뀐 파일과 코드

| 파일 | 변경 범위 |
|---|---|
| static/style.css | 전체 디자인 스타일 교체 |
| templates/catalog_base.html | 공통 상단·메뉴·푸터 표현 |
| templates/products.html | 소개 영역, 상품 목록 제목, 카드 제목 태그 |
| templates/signup.html | body의 디자인 클래스와 브랜드 장식 |
| templates/login.html | body의 디자인 클래스와 브랜드 장식 |
| templates/account.html | body의 디자인 클래스와 브랜드 장식 |
| templates/profile.html | body의 디자인 클래스와 브랜드 장식 |

장바구니·주문·결제·주문내역 HTML은 기존 공통 클래스를 사용하므로 CSS 변경만으로 같은 분위기가 적용됩니다. 파이썬 파일, SQL, 환경변수는 수정하지 않았습니다. 폼의 action·method·name·숨김 값과 기존 링크의 목적지는 유지했습니다.

아래에는 바뀐 CSS 전체와 템플릿 변경 부분을 담았습니다.

### static/style.css — 전체 교체

```css
/* 따뜻한 색과 공통 간격을 변수로 모아 전체 화면에 적용한다. */
:root {
    color-scheme: light;
    --paper: #faf6ef;
    --surface: #fffdf8;
    --cream: #f1e8dc;
    --line: #e5d9cc;
    --ink: #40342d;
    --muted: #79695d;
    --accent: #86513c;
    --accent-dark: #653c2c;
    --peach: #eddbcb;
    --sage: #edf0e5;
    --shadow: 0 12px 36px rgb(76 49 30 / 5%);
    --radius: 22px;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 24px; }
body {
    margin: 0;
    padding: 32px 16px;
    background: var(--paper);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: 16px;
    line-height: 1.75;
    word-break: keep-all;
    overflow-wrap: anywhere;
}
a { color: var(--accent); text-underline-offset: 5px; }
button, input, textarea { font: inherit; }
button, a, input, textarea { -webkit-tap-highlight-color: transparent; }
button, .button, a { touch-action: manipulation; }
:focus-visible { outline: 3px solid #a46943; outline-offset: 4px; }
h1, h2, h3 { line-height: 1.4; letter-spacing: -0.04em; }
h1 { margin: 10px 0 14px; font-size: clamp(1.7rem, 4vw, 2.3rem); font-weight: 650; }
h2 { font-weight: 650; }
p { margin: 12px 0; }
.hint { margin: 10px 0 18px; color: var(--muted); font-size: 0.9rem; }
.eyebrow { margin: 0 0 10px; color: var(--muted); font-size: 0.78rem; letter-spacing: 0.04em; }
.brand-mark { color: #ad7958; font-size: 2rem; line-height: 1; }

/* 회원 화면은 포근한 종이 카드처럼 표현한다. */
.account-body {
    min-height: 100vh;
    background: radial-gradient(ellipse at 15% 5%, #f0e2d2, transparent 52%), var(--paper);
}
.card {
    position: relative;
    width: 100%;
    max-width: 480px;
    margin: 12px auto;
    padding: 30px 24px;
    border: 1px solid var(--line);
    border-radius: 28px;
    background: var(--surface);
    box-shadow: var(--shadow);
}
.card::before { content: ""; display: block; width: 40px; height: 3px; margin: 0 auto 24px; border-radius: 4px; background: #d1ae90; }
.brand { display: flex; align-items: center; justify-content: center; gap: 10px; margin: 0 0 24px; color: var(--accent); font-size: 0.95rem; font-weight: 650; }
.card > h1 { text-align: center; }
.card > h1 + .hint { text-align: center; }
label { display: block; margin-top: 20px; font-size: 0.9rem; font-weight: 650; }
input, textarea {
    width: 100%;
    min-width: 0;
    margin-top: 8px;
    padding: 13px 15px;
    border: 1px solid #d8c6b5;
    border-radius: 12px;
    background: #fffefa;
    color: var(--ink);
    transition: border-color 160ms ease, box-shadow 160ms ease;
}
input { min-height: 50px; }
input[type="hidden"] { display: none; }
input::placeholder, textarea::placeholder { color: #8a796c; opacity: 1; }
input:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgb(134 81 60 / 9%); }
textarea { resize: vertical; line-height: 1.7; }
button, .button {
    display: block;
    width: 100%;
    min-height: 50px;
    margin-top: 24px;
    padding: 13px 18px;
    border: 1px solid transparent;
    border-radius: 12px;
    background: var(--accent);
    color: #fffdf9;
    font-weight: 650;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
    transition: background-color 160ms ease, box-shadow 160ms ease;
}
button:hover, .button:hover { background: var(--accent-dark); box-shadow: 0 5px 14px rgb(87 49 29 / 10%); }
.secondary { border-color: var(--line); background: var(--cream); color: #624c3e; }
.secondary:hover { background: #e8dac9; }
.danger { background: #965448; }
.danger:hover { background: #783e35; }
.error, .success { padding: 15px 18px; border-radius: 12px; font-size: 0.92rem; }
.error { border: 1px solid #ecd0c7; background: #fbefea; color: #8c3d2c; }
.success { border: 1px solid #d9dfcb; background: var(--sage); color: #4c5e3a; }
.success a { color: inherit; font-weight: 650; }
dt { margin-top: 20px; color: var(--muted); font-size: 0.85rem; }
dd { margin: 5px 0 0; padding-bottom: 14px; border-bottom: 1px solid var(--line); font-weight: 550; }
.check-label { display: flex; align-items: flex-start; gap: 12px; font-weight: 400; }
.check-label input { flex: 0 0 22px; width: 22px; min-height: 22px; margin-top: 4px; padding: 0; accent-color: var(--accent); }

/* 공통 메뉴와 푸터 */
.catalog-body { padding: 0; }
.announcement { padding: 9px 16px; background: #eee2d2; color: #715745; font-size: 0.75rem; text-align: center; letter-spacing: 0.05em; }
.site-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 16px 24px;
    max-width: 1240px;
    margin: 0 auto;
    padding: 22px 20px;
    border-bottom: 1px solid var(--line);
}
.site-logo { display: inline-flex; align-items: center; gap: 12px; color: var(--ink); font-size: 1.12rem; font-weight: 750; text-decoration: none; letter-spacing: -0.04em; }
.site-logo .brand-mark { font-size: 2.5rem; }
.site-logo small { display: block; margin-top: 2px; color: var(--muted); font-size: 0.66rem; font-weight: 400; letter-spacing: 0.02em; }
.site-header nav { display: flex; flex-wrap: wrap; gap: 4px 8px; }
.site-header nav a { display: inline-flex; align-items: center; min-height: 44px; padding: 6px 10px; border-radius: 8px; color: #6e5b4e; font-size: 0.85rem; text-decoration: none; }
.site-header nav a:hover, .site-header nav a[aria-current="page"] { background: var(--cream); color: var(--accent-dark); }
.catalog-main { max-width: 1240px; min-height: 52vh; margin: 0 auto; padding: 30px 20px 64px; }
.site-footer { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: end; gap: 24px; max-width: 1200px; margin: 0 auto; padding: 36px 20px; border-top: 1px solid var(--line); color: var(--muted); font-size: 0.8rem; }
.footer-brand { margin: 0 0 12px; color: var(--ink); font-size: 1rem; font-weight: 650; }
.footer-brand span { margin-right: 6px; color: #ad7958; }
.footer-note { font-size: 0.75rem; }

/* 상품 목록의 따뜻한 소개 영역과 카드 */
.welcome-hero { display: grid; grid-template-columns: minmax(0, 1fr); gap: 28px; padding: 6px 0 42px; }
.welcome-copy { align-self: center; }
.tiny-sun { margin-right: 7px; color: #a16a48; font-size: 1.05rem; }
.welcome-copy h1 { margin: 18px 0 20px; font-family: "Iowan Old Style", "Palatino Linotype", "Noto Serif KR", "Batang", serif; font-size: clamp(2rem, 5vw, 3.4rem); font-weight: 500; line-height: 1.4; letter-spacing: -0.065em; }
.welcome-copy h1 em { color: var(--accent); font-style: normal; }
.welcome-description { color: var(--muted); font-size: 0.88rem; line-height: 1.95; }
.hero-link { display: inline-flex; align-items: center; gap: 24px; min-height: 44px; margin-top: 14px; padding: 6px 0; border-bottom: 1px solid #b8997f; color: #76503a; font-size: 0.85rem; font-weight: 600; text-decoration: none; }
.hero-link span { font-size: 1.25rem; }
.welcome-visual { position: relative; width: 100%; max-width: 470px; aspect-ratio: 4 / 3; justify-self: center; overflow: hidden; border: 1px solid #e6d9c8; border-radius: 42% 42% 24px 24px; background: var(--cream); }
.hero-photo { display: block; width: 100%; height: 100%; object-fit: cover; }
.hero-caption { position: absolute; right: 14px; bottom: 14px; display: flex; align-items: center; gap: 10px; padding: 11px 16px; border: 1px solid rgb(229 217 204 / 75%); border-radius: 12px; background: rgb(255 251 244 / 94%); color: #71533f; font-size: 0.7rem; line-height: 1.65; }
.hero-caption > span:first-child { color: #ad7958; font-size: 1.7rem; }
.catalog-selection { padding-top: 30px; border-top: 1px solid var(--line); }
.catalog-heading { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 8px 20px; margin-bottom: 24px; }
.catalog-heading h2 { margin: 4px 0 0; font-size: 1.55rem; }
.catalog-heading .eyebrow { margin-bottom: 4px; }
.selection-count { margin: 0; color: var(--muted); font-size: 0.78rem; }
.selection-count span { margin-left: 8px; color: var(--accent); font-weight: 650; }
.product-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; }
.product-card { min-width: 0; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); transition: box-shadow 180ms ease, border-color 180ms ease; }
.product-card:hover { border-color: #c9aa8f; box-shadow: var(--shadow); }
.product-link { display: block; height: 100%; color: inherit; text-decoration: none; }
.product-link:focus-visible { outline-offset: -5px; border-radius: var(--radius); }
.product-image { display: grid; place-items: center; aspect-ratio: 4 / 3; overflow: hidden; background: #eee8df; }
.product-image img { display: block; width: 100%; height: 100%; object-fit: cover; }
.image-placeholder { padding: 18px; color: var(--muted); font-size: 0.85rem; text-align: center; }
.product-card-content { padding: 22px 22px 24px; }
.product-card h3 { margin: 14px 0 7px; font-size: 1.08rem; font-weight: 600; }
.product-link:hover h3 { color: var(--accent); }
.product-price { margin: 8px 0; color: #574034; font-size: 1.2rem; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.03em; }
.stock-badge { display: inline-block; margin: 0; padding: 4px 10px; border: 1px solid #dce0cf; border-radius: 7px; background: var(--sage); color: #566344; font-size: 0.73rem; }
.sold-out { border-color: #e2d7ca; background: #eee6db; color: #7a6754; }
.detail-link { display: block; margin-top: 18px; padding-top: 14px; border-top: 1px solid #ede4d9; color: #8b6650; font-size: 0.77rem; }
.back-link { margin: 0 0 24px; }
.back-link a { display: inline-flex; align-items: center; min-height: 44px; color: var(--muted); font-size: 0.85rem; text-decoration: none; }
.product-detail { display: grid; grid-template-columns: minmax(0, 1fr); overflow: hidden; border: 1px solid var(--line); border-radius: 26px; background: var(--surface); box-shadow: var(--shadow); }
.product-detail-content { min-width: 0; padding: 28px 24px; }
.product-detail h1 { font-size: clamp(1.75rem, 3vw, 2.4rem); }
.detail-price { margin: 18px 0; font-size: 1.85rem; }
.section-title { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--line); font-size: 0.95rem; }
.product-description { color: #746153; white-space: pre-line; line-height: 1.9; }
.empty-state { padding: 40px 24px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
.empty-state .button { max-width: 280px; }

/* 장바구니·주문·결제 화면 */
.shopping-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; margin-top: 28px; }
.shopping-items { display: grid; gap: 20px; }
.shopping-item, .order-summary { min-width: 0; padding: 24px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); overflow-wrap: anywhere; }
.shopping-item h2, .order-summary h2 { margin-top: 0; font-size: 1.1rem; }
.shopping-item h2:not(:first-child) { margin-top: 30px; }
.shopping-item h2 a { color: var(--ink); text-decoration: none; }
.order-summary { background: #f3eade; }
.order-summary .product-price { font-size: 1.45rem; }
.order-summary hr { height: 1px; margin: 24px 0; border: 0; background: #ddcbbb; }
.order-summary > p > a { font-size: 0.85rem; }
.quantity-form { display: grid; grid-template-columns: auto minmax(64px, 100px) minmax(90px, 1fr); align-items: center; gap: 10px; margin-top: 22px; }
.quantity-form label, .quantity-form input, .quantity-form button { margin: 0; }
.quantity-form button { padding: 11px 9px; font-size: 0.85rem; }
.action-row { display: flex; flex-wrap: wrap; gap: 12px; }
.action-row button { flex: 1 1 140px; }
.history-filters { display: flex; flex-wrap: wrap; gap: 10px; margin: 24px 0 28px; }
.history-filters a { display: inline-flex; align-items: center; min-height: 44px; padding: 9px 18px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: #735b49; font-size: 0.85rem; text-decoration: none; }
.history-filters a:hover { background: var(--cream); }
.history-filters a[aria-current="page"] { border-color: var(--accent); background: var(--accent); color: #fffdf9; }
.history-item { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; }
.history-item .eyebrow { font-size: 0.74rem; }
.history-item h2 { margin-bottom: 14px; }
.history-actions .button { margin-top: 12px; }
.pending-badge { border-color: #e7d4ac; background: #f8edcf; color: #7c5f27; }
.payment-history { margin-top: 28px; }
.payment-attempt + .payment-attempt { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line); }

/* 화면이 넓어질 때만 열 수와 간격을 늘린다. */
@media (max-width: 359px) {
    .quantity-form { grid-template-columns: auto minmax(0, 1fr); }
    .quantity-form button { grid-column: 1 / -1; }
    .site-header nav { gap: 0 3px; }
    .site-header nav a { padding-right: 8px; padding-left: 8px; }
}
@media (min-width: 600px) {
    .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .card { padding: 36px; }
}
@media (min-width: 768px) {
    .account-body { padding-top: 56px; padding-bottom: 56px; }
    .site-header { padding: 26px 32px; }
    .site-header nav { gap: 8px; }
    .catalog-main { padding: 40px 32px 80px; }
    .welcome-hero { grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); align-items: center; gap: 36px; padding: 10px 0 50px; }
    .welcome-visual { aspect-ratio: 1.13; }
    .welcome-description { font-size: 0.9rem; }
    .catalog-selection { padding-top: 38px; }
    .catalog-heading { margin-bottom: 28px; }
    .product-detail { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-items: start; }
    .product-detail-content { padding: 36px 32px; }
    .history-item { grid-template-columns: minmax(0, 1fr) 180px; align-items: center; gap: 24px; }
    .site-footer { padding: 40px 32px; }
}
@media (min-width: 900px) {
    .shopping-layout { grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); align-items: start; }
    .order-summary { position: sticky; top: 24px; }
}
@media (min-width: 1024px) {
    .product-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 28px; }
    .welcome-hero { gap: 72px; padding: 22px 16px 64px; }
    .welcome-copy h1 { font-size: 3.25rem; }
    .hero-caption { right: 22px; bottom: 22px; padding: 14px 20px; font-size: 0.76rem; }
}
@media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
    *, *::before, *::after { transition: none !important; }
}
```

### templates/catalog_base.html — 공통 표시 영역 변경

상단과 하단, 메뉴 표시를 변경한 현재 템플릿입니다. 기존 로그인 조건과 링크는 유지합니다.

```html
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}상품 목록{% endblock %} | 작은 쇼핑몰</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body class="catalog-body">
    <div class="announcement">작은 물건으로 채우는, 포근한 하루</div>
    <header class="site-header">
        <a class="site-logo" href="/products">
            <span class="brand-mark" aria-hidden="true">✳</span>
            <span>작은 쇼핑몰<small>일상에 머무는 작은 온기</small></span>
        </a>
        <nav aria-label="주요 메뉴">
            <a href="/products" {% if request.url.path.startswith('/products') %}aria-current="page"{% endif %}>상품 목록</a>
            <a href="/cart" {% if request.url.path == '/cart' %}aria-current="page"{% endif %}>장바구니</a>
            {% if user %}
                <a href="/account" {% if request.url.path.startswith('/account') %}aria-current="page"{% endif %}>회원정보</a>
                <a href="/orders" {% if request.url.path.startswith('/orders') %}aria-current="page"{% endif %}>주문내역</a>
            {% else %}
                <a href="/login?next={{ request.url.path | urlencode }}">로그인</a>
                <a href="/signup">회원가입</a>
            {% endif %}
        </nav>
    </header>
    <main class="catalog-main">
        {% block content %}{% endblock %}
    </main>
    <footer class="site-footer">
        <div>
            <p class="footer-brand"><span aria-hidden="true">✳</span> 작은 쇼핑몰</p>
            <p>매일 곁에 두고 싶은 물건,<br>그 안에 담긴 작은 따뜻함.</p>
        </div>
        <p class="footer-note">당신의 일상이 조금 더 포근해지기를.</p>
    </footer>
</body>
</html>
```

### templates/products.html — 목록 제목 영역 교체

기존 catalog-heading 부분을 아래 소개와 섹션 제목으로 교체했습니다. 기존 상품 반복문은 그대로 사용하고 마지막에 section 닫는 태그를 추가했습니다.

```html
    <section class="welcome-hero" aria-labelledby="welcome-title">
        <div class="welcome-copy">
            <p class="eyebrow"><span class="tiny-sun" aria-hidden="true">✳</span> 다정한 일상을 위한 작은 선택</p>
            <h1 id="welcome-title">매일의 작은 온기를<br><em>골라 담아요.</em></h1>
            <p class="welcome-description">좋아하는 컵에 담긴 한 잔의 여유,<br>가볍게 들고 나서는 가방 하나.<br>오래 곁에 두고 싶은 일상의 물건을 만나보세요.</p>
            <a class="hero-link" href="#product-list">천천히 둘러보기 <span aria-hidden="true">↗</span></a>
        </div>
        <div class="welcome-visual">
            <img class="hero-photo" src="{{ url_for('static', path='/images/products/mug.png') }}"
                 alt="부드러운 빛 아래 놓인 아이보리 머그컵" width="1448" height="1086" fetchpriority="high">
            <div class="hero-caption"><span aria-hidden="true">✳</span><span>작고 소박해서,<br>더 자주 손이 가는 것들.</span></div>
        </div>
    </section>
    <section id="product-list" class="catalog-selection" aria-labelledby="selection-title">
        <div class="catalog-heading">
            <div>
                <p class="eyebrow">일상에 스며드는 물건</p>
                <h2 id="selection-title">오늘의 작은 발견</h2>
            </div>
            <p class="selection-count">상품 목록 <span>{{ products | length }}개</span></p>
        </div>
```

카드 제목은 새 상품 목록 제목의 하위 제목이 되도록 바꿨습니다.

```html
<h3>{{ product.name }}</h3>
```

### signup.html · login.html · account.html · profile.html — 공통 변경 부분

기존 body와 brand 표시만 아래처럼 바꿨습니다. 각 파일의 나머지 폼과 안내는 유지합니다.

```html
<body class="account-body">
```

```html
<p class="brand"><span class="brand-mark" aria-hidden="true">✳</span> 작은 쇼핑몰</p>
```

## 3. 동작 방식 설명

브라우저가 기존 주소 요청 → FastAPI가 기존 데이터와 템플릿으로 HTML 응답 → 브라우저가 새 CSS와 기존 상품 사진을 읽어 디자인 표시.

CSS는 같은 내용을 어떤 색·크기·간격으로 보여줄지 정하는 옷이라고 생각하면 됩니다. 이번에는 그 옷을 바꾸고, 상품 목록의 소개와 공통 상단·하단을 꾸몄습니다.

소개 영역의 **천천히 둘러보기**는 같은 화면의 상품 목록으로 이동하는 앵커 링크입니다. 새 상품 검색이나 필터 기능을 만든 것이 아닙니다. 현재 메뉴 강조는 기존 URL을 읽어 표시만 바꾸며 화면 이동 규칙을 바꾸지 않습니다.

### 반응형 배치

- 좁은 모바일: 상품 1열, 소개 문구 아래 사진, 주문서 세로 배치
- 600px 이상: 상품 2열
- 768px 이상: 소개·상세의 사진과 글을 나란히 배치
- 900px 이상: 주문 내용과 금액 요약을 나란히 배치
- 1024px 이상: 상품 3열
- 작은 화면의 수량 변경 폼은 버튼을 아래 행으로 보내도록 처리

키보드 포커스 표시와 기존 입력 라벨을 유지합니다. 애니메이션 감소 설정을 사용하는 환경에서는 부드러운 스크롤과 전환 효과를 끕니다. 실제 기기·브라우저에서의 동작과 레이아웃은 아직 확인하지 않았습니다.

## 4. 직접 확인하는 방법

### 서버가 실행 중이라면

`--reload`로 실행 중이라도 HTML·CSS 변경만으로 서버 재시작이 자동 발생하지 않을 수 있습니다. 먼저 [상품 목록](http://127.0.0.1:8000/products)을 **Ctrl + F5**로 새로고침하세요. CSS도 다시 받아오게 하는 새로고침입니다.

### 서버가 종료되어 있다면

기존 가상환경에서 실행합니다.

```powershell
python -m uvicorn app.main:app --reload
```

### 확인할 화면

| 화면 | 확인할 디자인 |
|---|---|
| [상품 목록](http://127.0.0.1:8000/products) | 크림색 배경, 머그컵 소개 영역, 브라운 글자와 상품 카드 |
| 상품 상세 | 둥근 사진·정보 영역과 버튼·수량 입력창 |
| [로그인](http://127.0.0.1:8000/login) | 따뜻한 배경과 회원 카드 |
| [회원정보](http://127.0.0.1:8000/account) | 버튼·정보 표시의 일관성 |
| [장바구니](http://127.0.0.1:8000/cart) | 수량 입력·삭제 버튼과 크림색 합계 카드 |
| 주문서·결제 | 입력창·금액·성공 및 실패 안내의 가독성 |
| [주문내역](http://127.0.0.1:8000/orders) | 둥근 상태 필터와 주문 카드 |

브라우저 창을 좁혀 메뉴가 줄바꿈되고 가로 스크롤 없이 읽을 수 있는지도 확인해 주세요. 키보드 Tab으로 링크·입력창·버튼의 포커스 표시를 살펴볼 수 있습니다. 기능을 확인하려고 새 결제를 꼭 실행할 필요는 없으며 이미 생성한 화면부터 확인하면 됩니다.

## 5. 피드백 질문

포근하고 따뜻한 분위기로 느껴지나요? 색이 너무 진하거나 여백·글자 크기·소개 영역에서 조정하고 싶은 부분이 있으면 알려주세요.

이번 작업으로 STEP 7 점검을 완료했다고 간주하지 않습니다. 디자인 확인 결과를 받은 뒤 원래 진행 순서로 이어갑니다.
