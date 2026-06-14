"""Zitadel Actions V2 webhook endpoints (called by the auth instance)."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import get_settings
from app.zitadel_actions.idp_mapping import (
    extract_actions_response,
    map_github_idp_intent_response,
    verify_zitadel_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/zitadel/actions", tags=["zitadel-actions"])

_SIGNATURE_HEADERS = (
    "zitadel-signature",
    "ZITADEL-Signature",
    "X-Zitadel-Signature",
)


def _read_signature_header(request: Request) -> str:
    for name in _SIGNATURE_HEADERS:
        value = request.headers.get(name)
        if value:
            return value
    return ""


@router.post("/idp-intent")
async def map_idp_intent(request: Request) -> Response:
    """Actions V2 response hook for RetrieveIdentityProviderIntent (Login V2 GitHub)."""
    settings = get_settings()
    signing_key = settings.zitadel_actions_signing_key_effective
    if not signing_key:
        logger.warning(
            "Zitadel Actions idp-intent called but signing key is not configured"
        )
        raise HTTPException(status_code=503, detail="ZITADEL_ACTIONS_NOT_CONFIGURED")

    raw_body = await request.body()
    signature = _read_signature_header(request)
    if not verify_zitadel_signature(signature, raw_body, signing_key):
        logger.warning("Zitadel Actions idp-intent signature verification failed")
        raise HTTPException(status_code=400, detail="INVALID_SIGNATURE")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="INVALID_JSON") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="INVALID_PAYLOAD")

    response = extract_actions_response(payload)
    if response is None:
        raise HTTPException(status_code=400, detail="MISSING_RESPONSE")

    mapped = map_github_idp_intent_response(response)
    return Response(content=json.dumps(mapped), media_type="application/json")
