import pytest
from fastapi_users.exceptions import InvalidPasswordException

from app.auth.password import MIN_PASSWORD_LENGTH, validate_password_strength


def test_accepts_password_at_minimum_length():
    validate_password_strength("a" * MIN_PASSWORD_LENGTH)


def test_rejects_short_password():
    with pytest.raises(InvalidPasswordException) as exc:
        validate_password_strength("short")
    assert str(MIN_PASSWORD_LENGTH) in exc.value.reason
