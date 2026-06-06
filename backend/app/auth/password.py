from fastapi_users import schemas
from fastapi_users.exceptions import InvalidPasswordException

from app.models.user import User

MIN_PASSWORD_LENGTH = 8


def validate_password_strength(
    password: str, user: schemas.UC | User | None = None
) -> None:
    """Enforce password rules on registration and password changes."""
    del user  # reserved for future user-specific rules (e.g. not equal to email)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidPasswordException(
            reason=f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
