"""Map GitHub IdP intent payloads for Zitadel Login V2 (Actions V2 response hook)."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from app.config import PLACEHOLDER_SECRET_VALUES

# Zitadel rejects webhook timestamps older than 5 minutes.
_SIGNATURE_TOLERANCE_SECONDS = 300


def split_display_name(name: str, fallback: str) -> tuple[str, str]:
    cleaned = (name or "").strip()
    if not cleaned:
        local = fallback.split("@")[0] if "@" in fallback else fallback
        return local or "GitHub", "User"
    parts = cleaned.split(None, 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else parts[0]
    return first, last


def _field(obj: dict[str, Any], camel: str, snake: str) -> Any:
    if camel in obj:
        return obj[camel]
    return obj.get(snake)


def _set_field(obj: dict[str, Any], camel: str, snake: str, value: Any) -> None:
    obj[camel] = value
    obj[snake] = value


def _extract_github_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """GitHub user JSON is usually flat; some providers nest under User."""
    if "login" in raw or "email" in raw:
        return raw
    nested = raw.get("User") or raw.get("user")
    if isinstance(nested, dict):
        return nested
    return raw


def _github_fields(raw: dict[str, Any]) -> tuple[str, str, str, str]:
    data = _extract_github_raw(raw)
    login = str(data.get("login") or "").strip()
    email = str(data.get("email") or "").strip()
    display = str(data.get("name") or "").strip()
    if not display:
        display = login
    first, last = split_display_name(display, email or login)
    username = email or login
    return username, first, last, display


def _set_profile_fields(
    profile: dict[str, Any], first: str, last: str, display: str
) -> None:
    if not str(_field(profile, "givenName", "given_name") or "").strip():
        _set_field(profile, "givenName", "given_name", first)
    if not str(_field(profile, "familyName", "family_name") or "").strip():
        _set_field(profile, "familyName", "family_name", last)
    if not str(_field(profile, "displayName", "display_name") or "").strip():
        _set_field(profile, "displayName", "display_name", display)


def _fill_user_payload(
    target: dict[str, Any],
    *,
    username: str,
    link_name: str,
    first: str,
    last: str,
    display: str,
) -> None:
    """Fill username/email/profile on a Login V2 user-creation payload."""
    if username:
        _set_field(target, "username", "username", username)
    if link_name and username and "@" in username:
        email_obj = target.get("email")
        if not isinstance(email_obj, dict):
            email_obj = {}
            target["email"] = email_obj
        email_obj["email"] = username
        _set_field(email_obj, "isVerified", "is_verified", True)
    profile = target.get("profile")
    if not isinstance(profile, dict):
        profile = {}
        target["profile"] = profile
    _set_profile_fields(profile, first, last, display)


def map_github_idp_intent_response(response: dict[str, Any]) -> dict[str, Any]:
    """Fill profile + IdP link fields required by Login V2 user creation/linking."""
    idp_info = _field(response, "idpInformation", "idp_information")
    if not isinstance(idp_info, dict):
        return response

    raw = _field(idp_info, "rawInformation", "raw_information")
    if not isinstance(raw, dict):
        raw = {}

    username, first, last, display = _github_fields(raw)
    link_name = username or str(_field(idp_info, "userName", "user_name") or "").strip()

    if link_name:
        _set_field(idp_info, "userName", "user_name", link_name)

    add_human = _field(response, "addHumanUser", "add_human_user")
    if isinstance(add_human, dict):
        _fill_user_payload(
            add_human,
            username=username,
            link_name=link_name,
            first=first,
            last=last,
            display=display,
        )
        idp_links = _field(add_human, "idpLinks", "idp_links")
        if isinstance(idp_links, list) and idp_links and link_name:
            link = idp_links[0]
            if isinstance(link, dict):
                _set_field(link, "userName", "user_name", link_name)

    user_action = response.get("userAction") or response.get("user_action")
    if isinstance(user_action, dict):
        create_user = user_action.get("createUser") or user_action.get("create_user")
        if isinstance(create_user, dict):
            _fill_user_payload(
                create_user,
                username=username,
                link_name=link_name,
                first=first,
                last=last,
                display=display,
            )

    return response


def _parse_signature_header(header: str) -> tuple[int, list[bytes]] | None:
    if not header.strip():
        return None
    timestamp: int | None = None
    signatures: list[bytes] = []
    for part in header.split(","):
        key, _, value = part.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return None
        elif key == "v1" and value:
            try:
                signatures.append(bytes.fromhex(value))
            except ValueError:
                continue
    if timestamp is None or not signatures:
        return None
    return timestamp, signatures


def compute_zitadel_signature(
    timestamp: int, payload: bytes, signing_key: str
) -> bytes:
    """Match github.com/zitadel/zitadel/pkg/actions/signing.go."""
    mac = hmac.new(signing_key.encode(), digestmod=hashlib.sha256)
    mac.update(str(timestamp).encode())
    mac.update(b".")
    mac.update(payload)
    return mac.digest()


def verify_zitadel_signature(
    signature_header: str,
    raw_body: bytes,
    signing_key: str,
    *,
    tolerance_seconds: int = _SIGNATURE_TOLERANCE_SECONDS,
) -> bool:
    if not signature_header or not signing_key:
        return False
    if signing_key.strip() in PLACEHOLDER_SECRET_VALUES:
        return False

    parsed = _parse_signature_header(signature_header)
    if parsed is None:
        return False
    timestamp, signatures = parsed

    if tolerance_seconds > 0:
        age = abs(time.time() - timestamp)
        if age > tolerance_seconds:
            return False

    expected = compute_zitadel_signature(timestamp, raw_body, signing_key)
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def extract_actions_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the nested response object from an Actions V2 webhook payload."""
    response = payload.get("response")
    if isinstance(response, dict):
        return response
    return None
