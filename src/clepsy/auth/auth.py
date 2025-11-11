import os

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)  # 64 MB


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        ph.verify(stored_hash, password)
        return True
    except VerifyMismatchError:
        return False


def maybe_rehash(stored_hash: str) -> bool:
    """Return True if you should rehash with current params."""
    return ph.check_needs_rehash(stored_hash)


NONCE_LEN = 12  # GCM standard


def encrypt_secret(plaintext: str, master_key: bytes, *, aad: str | None) -> bytes:
    """
    AES-GCM encrypt. Returns one blob: nonce(12) || ciphertext||tag(16).
    Store directly in a BLOB/TEXT column.
    """
    if len(master_key) != 32:
        raise ValueError("master_key must be 32 bytes (256-bit)")
    aes = AESGCM(master_key)
    nonce = os.urandom(NONCE_LEN)  # NEVER reuse with same key
    token = aes.encrypt(nonce, plaintext.encode(), (aad or "").encode())
    return nonce + token


def decrypt_secret(blob: bytes, master_key: bytes, *, aad: str | None = None) -> str:
    """
    AES-GCM decrypt of blob produced by encrypt_secret.
    Raises on tamper/invalid key/AAD.
    """
    if len(master_key) != 32:
        raise ValueError("master_key must be 32 bytes (256-bit)")
    if not blob or len(blob) < NONCE_LEN + 16:
        raise ValueError("ciphertext too short")
    nonce, token = blob[:NONCE_LEN], blob[NONCE_LEN:]
    aes = AESGCM(master_key)
    return aes.decrypt(nonce, token, (aad or "").encode()).decode()
