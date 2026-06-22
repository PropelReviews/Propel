#!/usr/bin/env python3
"""Tests for the external-login config + strict-mode logic in zitadel_bootstrap.

Identity providers are defined manually in the Zitadel console; the bootstrap
only ensures the login policy + Actions V2 idp-intent webhook. These tests guard
that it never creates/purges IdPs.

Stdlib only (unittest + unittest.mock); the bootstrap is intentionally
dependency-free. Run directly (``python3 scripts/tests/test_zitadel_bootstrap_idp.py``)
or via pytest.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zitadel_bootstrap as zb  # noqa: E402

_BASE = "https://auth.example"
_HOST = "auth.example"
_PAT = "pat"


class EnsureExternalLoginConfigTest(unittest.TestCase):
    def test_configures_login_policy_and_webhook_without_touching_idps(self):
        recorded: list[tuple[str, str]] = []

        def request(base, host, pat, method, path, body=None):
            recorded.append((method, path))
            raise AssertionError(f"unexpected request: {method} {path}")

        with (
            mock.patch.object(zb, "_request", side_effect=request),
            mock.patch.object(zb, "_ensure_login_policy") as policy,
            mock.patch.object(
                zb, "_ensure_github_idp_mapping_v2", return_value="signing-key"
            ) as mapping,
        ):
            result = zb._ensure_external_login_config(
                _BASE, _HOST, _PAT, "https://api.example"
            )

        self.assertEqual(result, "signing-key")
        policy.assert_called_once()
        mapping.assert_called_once()
        # No IdP is ever created, purged, or activated.
        self.assertFalse(
            any("idps" in path for _, path in recorded),
            f"bootstrap must not touch IdPs, saw: {recorded}",
        )

    def test_propagates_webhook_signing_key_none(self):
        with (
            mock.patch.object(zb, "_ensure_login_policy"),
            mock.patch.object(zb, "_ensure_github_idp_mapping_v2", return_value=None),
        ):
            result = zb._ensure_external_login_config(
                _BASE, _HOST, _PAT, "https://api.example", strict=True
            )
        self.assertIsNone(result)


class GithubIdpMappingV2Test(unittest.TestCase):
    def test_reuses_existing_target_without_patch(self):
        recorded: list[tuple[str, str]] = []

        def request(base, host, pat, method, path, body=None):
            recorded.append((method, path))
            if method == "POST" and path == "/v2/actions/targets/search":
                return {
                    "targets": [
                        {"id": "tid", "name": zb.GITHUB_IDP_MAPPING_TARGET}
                    ]
                }
            if method == "PUT" and path == "/v2/actions/executions":
                return {}
            raise AssertionError(f"unexpected request: {method} {path}")

        with mock.patch.object(zb, "_request", side_effect=request):
            result = zb._ensure_github_idp_mapping_v2(
                _BASE, _HOST, _PAT, "https://api.example", strict=True
            )

        # Existing target → no key returned (already in Secrets Manager), but the
        # deploy must not fail and must never PATCH (405 on this instance).
        self.assertIsNone(result)
        self.assertFalse(
            any(method == "PATCH" for method, _ in recorded),
            f"must not PATCH an existing target, saw: {recorded}",
        )
        self.assertIn(("PUT", "/v2/actions/executions"), recorded)

    def test_creates_target_when_missing(self):
        def request(base, host, pat, method, path, body=None):
            if method == "POST" and path == "/v2/actions/targets/search":
                return {"targets": []}
            if method == "POST" and path == "/v2/actions/targets":
                return {"id": "new-tid", "signingKey": "sk"}
            if method == "PUT" and path == "/v2/actions/executions":
                return {}
            raise AssertionError(f"unexpected request: {method} {path}")

        with mock.patch.object(zb, "_request", side_effect=request):
            result = zb._ensure_github_idp_mapping_v2(
                _BASE, _HOST, _PAT, "https://api.example", strict=True
            )
        self.assertEqual(result, "sk")


class StrictModeTest(unittest.TestCase):
    def test_warn_or_raise(self):
        # Non-strict only warns (no exception); strict raises.
        zb._warn_or_raise("oops", strict=False)
        with self.assertRaises(RuntimeError):
            zb._warn_or_raise("oops", strict=True)

    def test_is_policy_noop_error(self):
        exc = RuntimeError(
            "PUT /admin/v1/policies/login failed (400): "
            '{"code":9,"message":"Default Login Policy has not been changed",'
            '"details":[{"id":"INSTANCE-5M9vdd"}]}'
        )
        self.assertTrue(zb._is_policy_noop_error(exc))

    def test_ensure_login_policy_treats_noop_as_success_in_strict_mode(self):
        activate_called = False

        def noop_put(base, host, pat, method, path, body=None):
            nonlocal activate_called
            if method == "GET" and path == "/admin/v1/policies/login":
                return {"policy": {"allowUsernamePassword": True}}
            if method == "PUT" and path == "/admin/v1/policies/login":
                raise RuntimeError(
                    "PUT /admin/v1/policies/login failed (400): INSTANCE-5M9vdd"
                )
            if method == "POST" and path == "/admin/v1/policies/login/_activate":
                activate_called = True
                return {}
            raise AssertionError(f"unexpected: {method} {path}")

        with mock.patch.object(zb, "_request", side_effect=noop_put):
            zb._ensure_login_policy(_BASE, _HOST, _PAT, strict=True)
        self.assertFalse(activate_called)

    def test_ensure_login_policy_activate_404_is_tolerated_after_update(self):
        def activate_404(base, host, pat, method, path, body=None):
            if method == "GET" and path == "/admin/v1/policies/login":
                return {"policy": {}}
            if method == "PUT" and path == "/admin/v1/policies/login":
                return {}
            if method == "POST" and path == "/admin/v1/policies/login/_activate":
                raise RuntimeError(
                    "POST /admin/v1/policies/login/_activate failed (404): Not Found"
                )
            raise AssertionError(f"unexpected: {method} {path}")

        with mock.patch.object(zb, "_request", side_effect=activate_404):
            zb._ensure_login_policy(_BASE, _HOST, _PAT, strict=True)

    def test_ensure_login_policy_preserves_fields_and_enables_password(self):
        put_body: dict = {}

        def request(base, host, pat, method, path, body=None):
            nonlocal put_body
            if method == "GET" and path == "/admin/v1/policies/login":
                # Simulate a policy where password login had been disabled and MFA
                # is forced — MFA must be preserved, password must be re-enabled.
                return {
                    "policy": {
                        "allowUsernamePassword": False,
                        "allowRegister": False,
                        "allowExternalIdp": True,
                        "forceMfa": True,
                        "passwordCheckLifetime": "240h0m0s",
                        # Not an UpdateLoginPolicy field — must be dropped.
                        "isDefault": True,
                    }
                }
            if method == "PUT" and path == "/admin/v1/policies/login":
                put_body = body or {}
                return {}
            if method == "POST" and path == "/admin/v1/policies/login/_activate":
                return {}
            raise AssertionError(f"unexpected: {method} {path}")

        with mock.patch.object(zb, "_request", side_effect=request):
            zb._ensure_login_policy(_BASE, _HOST, _PAT, strict=True)

        self.assertTrue(put_body["allowUsernamePassword"])
        self.assertTrue(put_body["allowRegister"])
        self.assertTrue(put_body["allowExternalIdp"])
        # Preserved from the existing policy.
        self.assertTrue(put_body["forceMfa"])
        self.assertEqual(put_body["passwordCheckLifetime"], "240h0m0s")
        # Non-update fields are not echoed back.
        self.assertNotIn("isDefault", put_body)


class ResetUserPasswordTest(unittest.TestCase):
    def test_posts_new_password_to_v2_user_api(self):
        recorded: list[tuple[str, str, dict]] = []

        def request(base, host, pat, method, path, body=None):
            recorded.append((method, path, body or {}))
            return {}

        with mock.patch.object(zb, "_request", side_effect=request):
            zb._reset_user_password(_BASE, _HOST, _PAT, "uid-1", "Sup3r!secret")

        self.assertEqual(len(recorded), 1)
        method, path, body = recorded[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/v2/users/uid-1/password")
        self.assertEqual(
            body,
            {"newPassword": {"password": "Sup3r!secret", "changeRequired": False}},
        )


if __name__ == "__main__":
    unittest.main()
