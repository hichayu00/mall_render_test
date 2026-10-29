import secrets

import bcrypt


def hash_password(password: str) -> str:
    # 무작위 salt를 포함한 bcrypt 해시만 DB에 저장한다.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > 72 or "\x00" in password:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def is_valid_csrf_token(cookie_token: str | None, form_token: str) -> bool:
    # 쿠키와 폼의 토큰이 일치하는지 비교한다.
    if not cookie_token or not form_token or len(form_token) > 128:
        return False
    return secrets.compare_digest(
        cookie_token.encode("utf-8"), form_token.encode("utf-8")
    )
