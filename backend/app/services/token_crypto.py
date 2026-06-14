"""Symmetric encryption for OAuth tool tokens stored at rest.

GitHub App installs mint short-lived tokens per run and never persist them.
OAuth tools (Linear, etc.) instead store an access/refresh token on
``connected_accounts``; those columns are encrypted with a Fernet key from
``TOKEN_ENCRYPTION_KEY`` so a database leak does not expose live credentials.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class TokenEncryptionError(RuntimeError):
    """Raised when the encryption key is missing or a token cannot be decrypted."""


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise TokenEncryptionError(
            "TOKEN_ENCRYPTION_KEY must be set to store OAuth tool tokens."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise TokenEncryptionError(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key (generate with "
            "Fernet.generate_key())."
        ) from exc


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenEncryptionError(
            "Stored token could not be decrypted (wrong TOKEN_ENCRYPTION_KEY?)."
        ) from exc
