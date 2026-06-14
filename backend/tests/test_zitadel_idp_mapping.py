"""Tests for Zitadel Actions V2 GitHub IdP mapping."""

import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app
from app.zitadel_actions.idp_mapping import (
    compute_zitadel_signature,
    map_github_idp_intent_response,
    verify_zitadel_signature,
)


def test_map_github_idp_intent_fills_profile_and_username():
    response = {
        "idpInformation": {
            "idpId": "1",
            "rawInformation": {
                "login": "octocat",
                "name": "Mona Octocat",
                "email": "octocat@github.com",
            },
        },
        "addHumanUser": {
            "profile": {},
            "idpLinks": [{"idpId": "1", "userId": "99", "userName": ""}],
        },
    }
    mapped = map_github_idp_intent_response(response)
    assert mapped["idpInformation"]["userName"] == "octocat@github.com"
    assert mapped["addHumanUser"]["username"] == "octocat@github.com"
    assert mapped["addHumanUser"]["email"]["isVerified"] is True
    assert mapped["addHumanUser"]["profile"]["givenName"] == "Mona"
    assert mapped["addHumanUser"]["profile"]["familyName"] == "Octocat"
    assert mapped["addHumanUser"]["idpLinks"][0]["userName"] == "octocat@github.com"


def test_map_github_idp_intent_snake_case_payload():
    response = {
        "idp_information": {
            "raw_information": {"login": "ghost", "email": "ghost@example.com"},
        },
        "add_human_user": {
            "profile": {},
            "idp_links": [{"user_name": ""}],
        },
    }
    mapped = map_github_idp_intent_response(response)
    assert mapped["idp_information"]["user_name"] == "ghost@example.com"
    assert mapped["add_human_user"]["profile"]["given_name"] == "ghost"
    assert mapped["add_human_user"]["profile"]["family_name"] == "ghost"
    assert mapped["add_human_user"]["idp_links"][0]["user_name"] == "ghost@example.com"


def test_map_github_idp_intent_uses_login_when_name_missing():
    response = {
        "idpInformation": {
            "rawInformation": {"login": "ghost", "email": ""},
        },
        "addHumanUser": {"profile": {}, "idpLinks": [{"userName": ""}]},
    }
    mapped = map_github_idp_intent_response(response)
    assert mapped["addHumanUser"]["profile"]["givenName"] == "ghost"
    assert mapped["addHumanUser"]["profile"]["familyName"] == "ghost"
    assert mapped["idpInformation"]["userName"] == "ghost"


def test_compute_zitadel_signature_matches_header_format():
    signing_key = "test-signing-key"
    payload = b'{"response":{}}'
    timestamp = 1700000000
    digest = compute_zitadel_signature(timestamp, payload, signing_key).hex()
    header = f"t={timestamp},v1={digest}"
    assert verify_zitadel_signature(header, payload, signing_key, tolerance_seconds=0)


@pytest.mark.asyncio
async def test_idp_intent_endpoint_maps_signed_payload(monkeypatch):
    signing_key = "test-signing-key-32chars-minimum!!"
    monkeypatch.setattr(get_settings(), "zitadel_actions_signing_key", signing_key)

    body = {
        "response": {
            "idpInformation": {
                "rawInformation": {"login": "ada", "email": "ada@example.com"},
            },
            "addHumanUser": {"profile": {}, "idpLinks": [{"userName": ""}]},
        }
    }
    raw = json.dumps(body)
    timestamp = int(time.time())
    signature = compute_zitadel_signature(timestamp, raw.encode(), signing_key).hex()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/zitadel/actions/idp-intent",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "ZITADEL-Signature": f"t={timestamp},v1={signature}",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["addHumanUser"]["profile"]["givenName"] == "ada"


@pytest.mark.asyncio
async def test_idp_intent_rejects_placeholder_signing_key(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "zitadel_actions_signing_key", "pending-bootstrap"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/zitadel/actions/idp-intent",
            content="{}",
            headers={"ZITADEL-Signature": "t=1,v1=ab"},
        )

    assert response.status_code == 503
