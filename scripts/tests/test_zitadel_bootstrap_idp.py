#!/usr/bin/env python3
"""Tests for the GitHub IdP purge/create + strict-mode logic in zitadel_bootstrap.

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


class _FakeZitadel:
    """Records calls and answers _request() from canned responses keyed by path."""

    def __init__(self, idps: list[dict], policy_idp_ids: list[str]):
        self._idps = idps
        self._policy_idp_ids = policy_idp_ids
        self.calls: list[tuple[str, str]] = []
        self.created_github: list[dict] = []
        self.deleted_idps: list[str] = []
        self.removed_from_policy: list[str] = []
        self.activated_idps: list[str] = []

    def request(self, base, host, pat, method, path, body=None):
        self.calls.append((method, path))
        if method == "POST" and path == "/admin/v1/idps/_search":
            return {"result": self._idps}
        if method == "POST" and path == "/admin/v1/policies/login/idps/_search":
            return {"result": [{"idpId": i} for i in self._policy_idp_ids]}
        if method == "DELETE" and path.startswith("/admin/v1/policies/login/idps/"):
            self.removed_from_policy.append(path.rsplit("/", 1)[-1])
            return {}
        if method == "DELETE" and path.startswith("/admin/v1/idps/"):
            self.deleted_idps.append(path.rsplit("/", 1)[-1])
            return {}
        if method == "POST" and path == "/admin/v1/idps/github":
            self.created_github.append(body or {})
            return {"id": "new-idp"}
        if method == "POST" and path == "/admin/v1/policies/login/idps":
            self.activated_idps.append((body or {}).get("idpId", ""))
            return {}
        raise AssertionError(f"unexpected request: {method} {path}")


class PurgeGithubIdpsTest(unittest.TestCase):
    def test_purges_every_github_idp_only(self):
        fake = _FakeZitadel(
            idps=[
                {"id": "a", "type": "IDP_TYPE_GITHUB"},
                {"id": "b", "name": "GitHub"},
                {"id": "c", "name": "GitHub"},
                {"id": "x", "name": "Google", "type": "IDP_TYPE_OIDC"},
            ],
            # "c" exists but is not attached to the login policy.
            policy_idp_ids=["a", "b"],
        )
        with mock.patch.object(zb, "_request", side_effect=fake.request):
            removed = zb._purge_all_github_idps(_BASE, _HOST, _PAT)

        self.assertEqual(removed, 3)
        self.assertEqual(sorted(fake.deleted_idps), ["a", "b", "c"])
        # Only the two that were actually on the policy are detached first.
        self.assertEqual(sorted(fake.removed_from_policy), ["a", "b"])
        self.assertNotIn("x", fake.deleted_idps)

    def test_no_github_idps_is_a_noop(self):
        fake = _FakeZitadel(
            idps=[{"id": "x", "name": "Google", "type": "IDP_TYPE_OIDC"}],
            policy_idp_ids=[],
        )
        with mock.patch.object(zb, "_request", side_effect=fake.request):
            removed = zb._purge_all_github_idps(_BASE, _HOST, _PAT)
        self.assertEqual(removed, 0)
        self.assertEqual(fake.deleted_idps, [])

    def test_raises_when_idp_delete_fails(self):
        def failing(base, host, pat, method, path, body=None):
            if method == "POST" and path == "/admin/v1/idps/_search":
                return {"result": [{"id": "a", "name": "GitHub"}]}
            if method == "POST" and path == "/admin/v1/policies/login/idps/_search":
                return {"result": []}
            if method == "DELETE":
                raise RuntimeError("DELETE /admin/v1/idps/a failed (500)")
            raise AssertionError(f"unexpected: {method} {path}")

        with (
            mock.patch.object(zb, "_request", side_effect=failing),
            self.assertRaises(RuntimeError),
        ):
            zb._purge_all_github_idps(_BASE, _HOST, _PAT)


class EnsureGithubIdpTest(unittest.TestCase):
    def _env(self):
        return mock.patch.dict(
            os.environ,
            {"GITHUB_APP_CLIENT_ID": "cid", "GITHUB_APP_CLIENT_SECRET": "secret"},
            clear=False,
        )

    def test_purges_then_creates_exactly_one(self):
        fake = _FakeZitadel(
            idps=[
                {"id": "old1", "name": "GitHub"},
                {"id": "old2", "name": "GitHub"},
            ],
            policy_idp_ids=["old1", "old2"],
        )
        with (
            self._env(),
            mock.patch.object(zb, "_request", side_effect=fake.request),
            mock.patch.object(zb, "_ensure_login_policy"),
            mock.patch.object(
                zb, "_ensure_github_idp_mapping_v2", return_value="signing-key"
            ) as mapping,
        ):
            result = zb._ensure_github_idp(_BASE, _HOST, _PAT, "https://api.example")

        self.assertEqual(result, "signing-key")
        # Old duplicates removed, and exactly one new IdP created + activated.
        self.assertEqual(sorted(fake.deleted_idps), ["old1", "old2"])
        self.assertEqual(len(fake.created_github), 1)
        self.assertEqual(fake.activated_idps, ["new-idp"])
        mapping.assert_called_once()

    def test_creates_one_when_none_exist(self):
        fake = _FakeZitadel(idps=[], policy_idp_ids=[])
        with (
            self._env(),
            mock.patch.object(zb, "_request", side_effect=fake.request),
            mock.patch.object(zb, "_ensure_login_policy"),
            mock.patch.object(zb, "_ensure_github_idp_mapping_v2", return_value="sk"),
        ):
            zb._ensure_github_idp(_BASE, _HOST, _PAT, "https://api.example")
        self.assertEqual(len(fake.created_github), 1)


class StrictModeTest(unittest.TestCase):
    def test_warn_or_raise(self):
        # Non-strict only warns (no exception); strict raises.
        zb._warn_or_raise("oops", strict=False)
        with self.assertRaises(RuntimeError):
            zb._warn_or_raise("oops", strict=True)

    def test_missing_github_creds_strict_raises(self):
        cleared = {"GITHUB_APP_CLIENT_ID": "", "GITHUB_APP_CLIENT_SECRET": ""}
        with (
            mock.patch.dict(os.environ, cleared, clear=False),
            self.assertRaises(RuntimeError),
        ):
            zb._ensure_github_idp(
                _BASE, _HOST, _PAT, "https://api.example", strict=True
            )

    def test_missing_github_creds_non_strict_returns_none(self):
        cleared = {"GITHUB_APP_CLIENT_ID": "", "GITHUB_APP_CLIENT_SECRET": ""}
        with mock.patch.dict(os.environ, cleared, clear=False):
            result = zb._ensure_github_idp(
                _BASE, _HOST, _PAT, "https://api.example", strict=False
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
