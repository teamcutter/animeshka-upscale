"""Password hashing (scrypt from the standard library) and session tokens."""

import hashlib
import hmac
import secrets

# 16 MiB of memory per hash: slow enough for brute force, fine for a login (~0.4 s measured).
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 32


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=KEY_LENGTH)


def hash_password(password: str) -> str:
    """Returns `scrypt$n$r$p$salt$key`, so the parameters can be raised later."""
    salt = secrets.token_bytes(16)
    key = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, key = stored.split("$")
        if algorithm != "scrypt":
            return False
        actual = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(actual, bytes.fromhex(key))


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # The token is random, so a plain SHA-256 is enough (no salt needed).
    return hashlib.sha256(token.encode()).hexdigest()
