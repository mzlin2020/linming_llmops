"""密码哈希：自有账号体系，使用 werkzeug 的 pbkdf2:sha256（带盐），不引第三方依赖。"""
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(plaintext: str) -> str:
    return generate_password_hash(plaintext)


def verify_password(plaintext: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    return check_password_hash(stored_hash, plaintext)
