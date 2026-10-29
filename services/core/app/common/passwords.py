"""密码哈希与强度校验：标准库 scrypt（不引入额外依赖），格式 scrypt$n$r$p$salt$hash。"""

import base64
import hashlib
import hmac
import re
import secrets

N, R, P = 2**14, 8, 1
MIN_LENGTH = 8
# 临时密码去掉容易看错的 0/O、1/l/I
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, base64.b64decode(digest))


def weakness(password: str) -> str | None:
    """不合格时返回原因：至少 8 位，同时包含字母和数字。"""
    if len(password) < MIN_LENGTH:
        return f"密码至少 {MIN_LENGTH} 位"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "密码要同时包含字母和数字"
    return None


def temp_password() -> str:
    """管理员新建成员 / 重置密码时生成的临时密码（10 位，保证有字母和数字）。"""
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        if weakness(candidate) is None:
            return candidate
