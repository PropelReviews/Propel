#!/usr/bin/env python3
"""Bootstrap Zitadel OIDC app + optional GitHub IdP for Propel."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_NAME = "Propel BFF"
GITHUB_IDP_NAME = "GitHub"

# Single shared Zitadel instance: each environment is a *project* inside the
# Propel company org (Model B). The OIDC app + roles live on the per-env project;
# beta + prod bootstrap against the same instance and only touch their own
# project. See docs/deployment/zitadel.md.
PROJECT_NAMES = {
    "local": "Propel Local",
    "beta": "Propel Beta",
    "prod": "Propel Prod",
}
# Environments whose bootstrap also owns instance-level config (GitHub IdP,
# branding, super-admin). The local stack is its own instance; prod hosts the
# single shared cloud instance. Beta consumes prod and must not redo these.
INSTANCE_OWNER_ENVS = {"local", "prod"}

# Project roles mirrored into Propel membership roles by app.auth.reconcile.
# Keep the keys in sync with reconcile._ROLE_MAP.
PROJECT_ROLES = [
    ("owner", "Owner", "propel"),
    ("admin", "Admin", "propel"),
    ("manager", "Manager", "propel"),
    ("member", "Member", "propel"),
]

# Human user granted IAM_OWNER (instance super-admin) so a person can use the
# management console at <issuer>/ui/console. Configured via env; skipped if unset.
ADMIN_EMAIL_ENV = "ZITADEL_ADMIN_EMAIL"
ADMIN_NAME_ENV = "ZITADEL_ADMIN_NAME"
# Auto-create GitHub users so login is one click. GitHub often omits given_name,
# which would otherwise fail Zitadel profile validation and show a registration
# screen — the FILL_NAMES_ACTION below guarantees non-empty first/last names.
GITHUB_IDP_PROVIDER_OPTIONS = {
    "isLinkingAllowed": True,
    "isCreationAllowed": True,
    "isAutoCreation": True,
    "isAutoUpdate": True,
    "autoLinking": "AUTO_LINKING_OPTION_EMAIL",
}

# v1 Action: on external (GitHub) registration, fill first/last name from the
# IdP info — or a safe fallback — so auto-creation never stalls on the
# profile-completion screen. allowedToFail keeps login working if the Actions
# feature is unavailable. Bound to External Authentication (flow 1) / Pre
# Creation (trigger 2).
FILL_NAMES_ACTION_NAME = "propelFillExternalNames"
FILL_NAMES_ACTION_SCRIPT = """
function propelFillExternalNames(ctx, api) {
  var first = "";
  var last = "";
  try {
    var ext = ctx && ctx.v1 && ctx.v1.externalUser ? ctx.v1.externalUser() : null;
    if (ext) {
      first = ext.firstName || "";
      last = ext.lastName || "";
      if ((!first || !last) && ext.displayName) {
        var parts = ext.displayName.split(" ");
        first = first || parts[0] || "";
        last = last || (parts.length > 1 ? parts.slice(1).join(" ") : parts[0]);
      }
      if ((!first || !last) && ext.email) {
        var local = ext.email.split("@")[0];
        first = first || local;
        last = last || local;
      }
    }
  } catch (e) {}
  api.setFirstName(first || "GitHub");
  api.setLastName(last || "User");
}
"""
EXTERNAL_AUTH_FLOW_TYPE = "1"
PRE_CREATION_TRIGGER_TYPE = "2"

# Hosted Login UI v2 branding (Zitadel "Label Policy"). Hex values are derived
# from the Propel Tailwind theme tokens in frontend/src/index.css (a neutral
# palette: near-black primary on light, near-white primary on dark) so the login
# page matches the app. Applied to the instance default policy.
LABEL_POLICY = {
    "primaryColor": "#171717",
    "backgroundColor": "#ffffff",
    "warnColor": "#e5484d",
    "fontColor": "#0a0a0a",
    "primaryColorDark": "#e5e5e5",
    "backgroundColorDark": "#0a0a0a",
    "warnColorDark": "#ff6369",
    "fontColorDark": "#fafafa",
    "hideLoginNameSuffix": True,
    "disableWatermark": True,
    "themeMode": "THEME_MODE_AUTO",
}
# Optional brand assets, uploaded when the file exists (skipped otherwise so
# colors-only branding still applies). Drop PNGs into BRANDING_DIR.
BRANDING_DIR = (
    Path(__file__).resolve().parent.parent / "infrastructure" / "zitadel" / "branding"
)
LABEL_ASSETS = {
    "logo.png": "/assets/v1/instance/policy/label/logo",
    "logo-dark.png": "/assets/v1/instance/policy/label/logo/dark",
    "icon.png": "/assets/v1/instance/policy/label/icon",
    "icon-dark.png": "/assets/v1/instance/policy/label/icon/dark",
}
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

ENV_PRESETS: dict[str, dict[str, str]] = {
    "local": {
        "ZITADEL_ISSUER": "http://localhost:8080",
        "ZITADEL_INTERNAL_ISSUER": "http://zitadel:8080",
        "ZITADEL_HOST_HEADER": "localhost",
        "OAUTH_CALLBACK_BASE_URL": "http://localhost:8000",
        "FRONTEND_BASE_URL": "http://localhost:5173",
    },
    "beta": {
        # Beta consumes the single shared Zitadel hosted in prod — its OIDC app
        # (redirect/logout below) is registered on the "Propel Beta" project of
        # that instance, not a separate beta auth domain.
        "ZITADEL_ISSUER": "https://auth.propel.ninja",
        "ZITADEL_HOST_HEADER": "auth.propel.ninja",
        "OAUTH_CALLBACK_BASE_URL": "https://api.beta.propel.ninja",
        "FRONTEND_BASE_URL": "https://app.beta.propel.ninja",
    },
    "prod": {
        "ZITADEL_ISSUER": "https://auth.propel.ninja",
        "ZITADEL_HOST_HEADER": "auth.propel.ninja",
        "OAUTH_CALLBACK_BASE_URL": "https://api.propel.ninja",
        "FRONTEND_BASE_URL": "https://app.propel.ninja",
    },
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _read_env_file_values() -> dict[str, str]:
    if not ENV_FILE.is_file():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _apply_env_preset(env_name: str) -> None:
    for key, value in ENV_PRESETS.get(env_name, {}).items():
        os.environ.setdefault(key, value)


def _resolve_zitadel_base() -> tuple[str, str]:
    """Return (api_base_url, host_header)."""
    issuer = _env("ZITADEL_ISSUER", "http://localhost:8080").rstrip("/")
    host_header = _env("ZITADEL_HOST_HEADER", "localhost")

    if issuer.startswith("https://"):
        return issuer, host_header

    # When localhost is unreachable (e.g. script runs inside devcontainer), use
    # the compose service name.
    if "localhost" in issuer or "127.0.0.1" in issuer:
        try:
            req = urllib.request.Request(
                f"{issuer}/.well-known/openid-configuration",
                headers={"Host": host_header},
            )
            with urllib.request.urlopen(req, timeout=2):
                return issuer, host_header
        except OSError:
            internal = _env("ZITADEL_INTERNAL_ISSUER", "http://zitadel:8080").rstrip(
                "/"
            )
            return internal, host_header
    return issuer, host_header


def _request(
    base: str,
    host_header: str,
    pat: str,
    method: str,
    path: str,
    body: dict | None = None,
) -> dict:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Host": host_header,
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        if exc.code == 403 and "AUTH-5mWD2" in detail:
            raise RuntimeError(
                "The bootstrap PAT lacks permission to create OIDC applications.\n"
                "Recreate the Zitadel database and bootstrap volume (see "
                "docs/self-hosting.md) or create the Propel BFF OIDC app manually "
                "in the Zitadel console."
            ) from exc
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {detail}") from exc


def _wait_for_zitadel(base: str, host_header: str) -> None:
    for _ in range(60):
        try:
            req = urllib.request.Request(
                f"{base}/debug/ready",
                headers={"Host": host_header},
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.read().decode().strip('"') == "ok":
                    return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError(f"Zitadel not ready at {base}")


def _wait_for_login_ui() -> None:
    login_port = _env("ZITADEL_LOGIN_PORT", "3002")
    url = f"http://127.0.0.1:{login_port}/ui/v2/login/healthy"
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            try:
                with urllib.request.urlopen(
                    "http://zitadel-login:3000/ui/v2/login/healthy", timeout=2
                ):
                    return
            except OSError:
                pass
        time.sleep(2)


def _read_pat_from_container(path: str) -> str | None:
    for container in ("propel-zitadel-login", "propel-zitadel"):
        try:
            result = subprocess.run(
                ["docker", "exec", container, "cat", path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except OSError:
            continue
    local = Path(path)
    if local.is_file():
        return local.read_text(encoding="utf-8").strip()
    return None


def _load_pat() -> str:
    mgmt_token = _env("ZITADEL_MGMT_TOKEN")
    if mgmt_token:
        return mgmt_token

    for path in (
        "/zitadel/bootstrap/admin.pat",
        "/zitadel/bootstrap/login-client.pat",
    ):
        pat = _read_pat_from_container(path)
        if pat:
            return pat
    raise RuntimeError(
        "No Zitadel management token found.\n"
        "Local: recreate the Zitadel database and bootstrap volume (see "
        "docs/self-hosting.md) or run inside compose after zitadel-oidc-init.\n"
        "Cloud: export ZITADEL_MGMT_TOKEN (IAM_OWNER PAT from Zitadel setup) and "
        "re-run with --env beta|prod --print-secrets."
    )


def _find_default_org_id(base: str, host_header: str, pat: str) -> str | None:
    for path in ("/admin/v1/orgs/_search", "/management/v1/orgs/_search"):
        try:
            payload = _request(
                base,
                host_header,
                pat,
                "POST",
                path,
                {"queries": []},
            )
        except RuntimeError:
            continue
        orgs = payload.get("result") or []
        if orgs:
            return str(orgs[0]["id"])
    return None


def _ensure_named_project(base: str, host_header: str, pat: str, name: str) -> str:
    """Find or create the per-environment project, then ensure it asserts roles
    and restricts authentication to users that hold a project role.

    ``projectRoleAssertion`` puts the granted roles into the OIDC token (read by
    app.auth.reconcile); ``projectRoleCheck`` is Zitadel's "Only authorized users
    can authenticate", and ``hasProjectCheck`` requires the user's org to hold a
    grant for the project — together they gate access to onboarded customers.
    """
    payload = _request(
        base,
        host_header,
        pat,
        "POST",
        "/management/v1/projects/_search",
        {"queries": []},
    )
    project_id = None
    for project in payload.get("result") or []:
        if project.get("name") == name:
            project_id = str(project["id"])
            break

    body = {
        "name": name,
        "projectRoleAssertion": True,
        "projectRoleCheck": True,
        "hasProjectCheck": True,
    }
    if project_id is None:
        created = _request(
            base, host_header, pat, "POST", "/management/v1/projects", body
        )
        project_id = str(created["id"])
        print(f"==> Created project '{name}'")
    else:
        # Keep the auth-gating flags in sync on re-runs (best-effort).
        try:
            _request(
                base,
                host_header,
                pat,
                "PUT",
                f"/management/v1/projects/{project_id}",
                body,
            )
        except RuntimeError as exc:
            print(
                f"WARNING: could not update project '{name}' settings: {exc}",
                file=sys.stderr,
            )

    _ensure_project_roles(base, host_header, pat, project_id)
    return project_id


def _ensure_project_roles(
    base: str, host_header: str, pat: str, project_id: str
) -> None:
    """Add the Propel project roles (owner/admin/manager/member) idempotently."""
    try:
        existing_payload = _request(
            base,
            host_header,
            pat,
            "POST",
            f"/management/v1/projects/{project_id}/roles/_search",
            {"queries": []},
        )
        existing = {
            str(role.get("key"))
            for role in existing_payload.get("result") or []
            if role.get("key")
        }
    except RuntimeError:
        existing = set()

    # NB: the _bulk endpoint expects "key" (the single-role endpoint uses
    # "roleKey"); mismatching it yields a 500 InvalidArgument.
    missing = [
        {"key": key, "displayName": display, "group": group}
        for key, display, group in PROJECT_ROLES
        if key not in existing
    ]
    if not missing:
        return
    try:
        _request(
            base,
            host_header,
            pat,
            "POST",
            f"/management/v1/projects/{project_id}/roles/_bulk",
            {"roles": missing},
        )
        print(f"==> Ensured project roles: {', '.join(r['key'] for r in missing)}")
    except RuntimeError as exc:
        print(f"WARNING: could not create project roles: {exc}", file=sys.stderr)


def _find_existing_app(
    base: str, host_header: str, pat: str, project_id: str
) -> dict | None:
    payload = _request(
        base,
        host_header,
        pat,
        "POST",
        f"/management/v1/projects/{project_id}/apps/_search",
        {"queries": []},
    )
    for app in payload.get("result") or []:
        if app.get("name") == APP_NAME and app.get("oidcConfig"):
            return app
    return None


def _create_oidc_app(
    base: str,
    host_header: str,
    pat: str,
    project_id: str,
    redirect_uri: str,
    logout_uri: str,
    *,
    dev_mode: bool,
) -> tuple[str, str, bool]:
    existing = _find_existing_app(base, host_header, pat, project_id)
    if existing is not None:
        client_id = existing["oidcConfig"]["clientId"]
        env_values = _read_env_file_values()
        env_client_id = _env("ZITADEL_CLIENT_ID") or env_values.get(
            "ZITADEL_CLIENT_ID", ""
        )
        env_client_secret = env_values.get("ZITADEL_CLIENT_SECRET", "")
        if env_client_id == client_id and env_client_secret:
            print(
                f"==> OIDC app '{APP_NAME}' already exists — reusing .env credentials"
            )
            return client_id, env_client_secret, False
        raise RuntimeError(
            f"OIDC app '{APP_NAME}' already exists (client_id={client_id}) but "
            "the client secret cannot be retrieved. Delete the app in the Zitadel "
            "console or recreate the bootstrap volume, then re-run this script."
        )

    payload = _request(
        base,
        host_header,
        pat,
        "POST",
        f"/management/v1/projects/{project_id}/apps/oidc",
        {
            "name": APP_NAME,
            "redirectUris": [redirect_uri],
            "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
            "grantTypes": [
                "OIDC_GRANT_TYPE_AUTHORIZATION_CODE",
                "OIDC_GRANT_TYPE_REFRESH_TOKEN",
            ],
            "appType": "OIDC_APP_TYPE_WEB",
            "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
            "postLogoutRedirectUris": [logout_uri],
            "version": "OIDC_VERSION_1_0",
            "devMode": dev_mode,
            "accessTokenType": "OIDC_TOKEN_TYPE_BEARER",
            "idTokenRoleAssertion": True,
            "idTokenUserinfoAssertion": True,
            "clockSkew": "0s",
        },
    )
    client_id = payload["clientId"]
    client_secret = payload["clientSecret"]
    if not client_id or not client_secret:
        raise RuntimeError(f"Unexpected create-app response: {payload}")
    return client_id, client_secret, True


def _find_github_idp_id(base: str, host_header: str, pat: str) -> str | None:
    for path in ("/admin/v1/idps/_search", "/management/v1/idps/_search"):
        try:
            payload = _request(
                base,
                host_header,
                pat,
                "POST",
                path,
                {"queries": []},
            )
        except RuntimeError:
            continue
        for idp in payload.get("result") or []:
            if idp.get("name") == GITHUB_IDP_NAME:
                return str(idp["id"])
    return None


def _ensure_github_idp(base: str, host_header: str, pat: str) -> None:
    client_id = _env("GITHUB_APP_CLIENT_ID") or _env("OAUTH_GITHUB_CLIENT_ID")
    client_secret = _env("GITHUB_APP_CLIENT_SECRET") or _env(
        "OAUTH_GITHUB_CLIENT_SECRET"
    )
    if not client_id or not client_secret:
        print("==> Skipping GitHub IdP (GITHUB_APP_CLIENT_ID/SECRET not set)")
        return

    body = {
        "name": GITHUB_IDP_NAME,
        "clientId": client_id,
        "clientSecret": client_secret,
        "scopes": ["read:user", "user:email"],
        "providerOptions": GITHUB_IDP_PROVIDER_OPTIONS,
    }

    existing_id = _find_github_idp_id(base, host_header, pat)
    if existing_id is not None:
        updated = False
        for prefix in ("/admin/v1/idps/github", "/management/v1/idps/github"):
            try:
                _request(base, host_header, pat, "PUT", f"{prefix}/{existing_id}", body)
                updated = True
                break
            except RuntimeError:
                continue
        if not updated:
            raise RuntimeError(
                f"Found GitHub IdP {existing_id} but could not update provider options"
            )
        print("==> GitHub IdP updated (auto-create enabled)")
    else:
        created = _request(
            base,
            host_header,
            pat,
            "POST",
            "/admin/v1/idps/github",
            body,
        )
        idp_id = created.get("id")
        if not idp_id:
            raise RuntimeError(f"Unexpected GitHub IdP response: {created}")

        _request(
            base,
            host_header,
            pat,
            "POST",
            "/admin/v1/policies/login/idps",
            {"idpId": idp_id},
        )
        print("==> GitHub IdP configured and activated on login policy")

    _ensure_external_name_action(base, host_header, pat)


def _ensure_external_name_action(base: str, host_header: str, pat: str) -> None:
    """Bind a v1 Action that fills first/last name on external registration.

    Best-effort: if the Actions feature is unavailable the GitHub login still
    works (users without a display name just see the completion screen once).
    """
    body = {
        "name": FILL_NAMES_ACTION_NAME,
        "script": FILL_NAMES_ACTION_SCRIPT,
        "timeout": "10s",
        "allowedToFail": True,
    }
    try:
        search = _request(
            base, host_header, pat, "POST", "/management/v1/actions/_search", {}
        )
        action_id = None
        for action in search.get("result") or []:
            if action.get("name") == FILL_NAMES_ACTION_NAME:
                action_id = str(action["id"])
                break
        if action_id is None:
            created = _request(
                base, host_header, pat, "POST", "/management/v1/actions", body
            )
            action_id = str(created.get("id") or "")
        else:
            _request(
                base,
                host_header,
                pat,
                "PUT",
                f"/management/v1/actions/{action_id}",
                body,
            )
        if not action_id:
            raise RuntimeError("no action id returned")
        _request(
            base,
            host_header,
            pat,
            "POST",
            f"/management/v1/flows/{EXTERNAL_AUTH_FLOW_TYPE}"
            f"/trigger/{PRE_CREATION_TRIGGER_TYPE}",
            {"actionIds": [action_id]},
        )
        print("==> External-registration name Action bound (one-click GitHub signup)")
    except RuntimeError as exc:
        print(
            f"WARNING: could not bind external-name Action (Actions feature may be "
            f"disabled): {exc}",
            file=sys.stderr,
        )


def _ensure_super_admin(base: str, host_header: str, pat: str) -> None:
    """Grant a human user IAM_OWNER so they can run the management console.

    Configured via ZITADEL_ADMIN_EMAIL (skipped if unset). The user is created
    with a verified email if missing — they sign in through the GitHub IdP
    (auto-linked by email) or an init mail. Best-effort: failures never block the
    OIDC/IdP bootstrap.
    """
    email = _env(ADMIN_EMAIL_ENV)
    if not email:
        print(f"==> Skipping super-admin grant ({ADMIN_EMAIL_ENV} not set)")
        return

    local_part = email.split("@")[0]
    display = _env(ADMIN_NAME_ENV) or local_part
    name_parts = display.split(" ", 1)
    first = name_parts[0] or local_part
    last = name_parts[1] if len(name_parts) > 1 else local_part

    try:
        user_id = _find_user_id_by_email(base, host_header, pat, email)
        if user_id is None:
            created = _request(
                base,
                host_header,
                pat,
                "POST",
                "/management/v1/users/human",
                {
                    "userName": email,
                    "profile": {"firstName": first, "lastName": last},
                    "email": {"email": email, "isEmailVerified": True},
                },
            )
            user_id = str(created.get("userId") or created.get("id") or "")
            if not user_id:
                raise RuntimeError(f"unexpected create-user response: {created}")
            print(f"==> Created admin user {email}")

        _request(
            base,
            host_header,
            pat,
            "POST",
            "/admin/v1/members",
            {"userId": user_id, "roles": ["IAM_OWNER"]},
        )
        print(f"==> Granted IAM_OWNER to {email} (management console super-admin)")
    except RuntimeError as exc:
        detail = str(exc)
        # Already-a-member is success; everything else is a best-effort warning.
        if "already" in detail.lower():
            print(f"==> {email} is already an instance admin")
            return
        print(
            f"WARNING: could not grant super-admin to {email}: {exc}",
            file=sys.stderr,
        )


def _find_user_id_by_email(
    base: str, host_header: str, pat: str, email: str
) -> str | None:
    try:
        payload = _request(
            base,
            host_header,
            pat,
            "POST",
            "/management/v1/users/_search",
            {
                "queries": [
                    {
                        "emailQuery": {
                            "emailAddress": email,
                            "method": "TEXT_QUERY_METHOD_EQUALS_IGNORE_CASE",
                        }
                    }
                ]
            },
        )
    except RuntimeError:
        return None
    for user in payload.get("result") or []:
        uid = user.get("userId") or user.get("id")
        if uid:
            return str(uid)
    return None


def _ensure_branding(base: str, host_header: str, pat: str) -> None:
    """Apply Propel branding to the hosted Login UI v2 (instance label policy).

    Best-effort: a failure never blocks the OIDC/IdP bootstrap.
    """
    try:
        _request(
            base, host_header, pat, "PUT", "/admin/v1/policies/label", LABEL_POLICY
        )
    except RuntimeError as exc:
        print(f"WARNING: could not set login branding colors: {exc}", file=sys.stderr)
        return

    uploaded = _upload_label_assets(base, host_header, pat)

    try:
        _request(
            base, host_header, pat, "POST", "/admin/v1/policies/label/_activate", {}
        )
    except RuntimeError as exc:
        print(f"WARNING: could not activate login branding: {exc}", file=sys.stderr)
        return

    print(f"==> Login UI branding applied{' + assets' if uploaded else ''}")


def _upload_label_assets(base: str, host_header: str, pat: str) -> bool:
    uploaded = False
    for filename, path in LABEL_ASSETS.items():
        asset = BRANDING_DIR / filename
        if not asset.is_file():
            continue
        try:
            _upload_asset(base, host_header, pat, path, asset)
            uploaded = True
        except (RuntimeError, OSError) as exc:
            print(f"WARNING: could not upload {filename}: {exc}", file=sys.stderr)
    return uploaded


def _upload_asset(
    base: str, host_header: str, pat: str, path: str, asset: Path
) -> None:
    """multipart/form-data upload of a single brand asset (field name 'file')."""
    boundary = "----propel" + secrets.token_hex(8)
    mime = "image/png" if asset.suffix.lower() == ".png" else "image/svg+xml"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{asset.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            asset.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers={
            "Host": host_header,
            "Authorization": f"Bearer {pat}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        response.read()


def _merge_env(path: Path, updates: dict[str, str]) -> None:
    lines: list[str] = []
    seen: set[str] = set()
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()

    out: list[str] = []
    for line in lines:
        matched = False
        for key, value in updates.items():
            if re.match(rf"^{re.escape(key)}=", line):
                out.append(f"{key}={value}")
                seen.add(key)
                matched = True
                break
        if not matched:
            out.append(line)

    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _already_configured_local() -> bool:
    values = _read_env_file_values()
    return bool(values.get("ZITADEL_CLIENT_ID") and values.get("ZITADEL_CLIENT_SECRET"))


def _write_secrets_json(
    path: str, *, client_id: str, client_secret: str, issuer: str
) -> None:
    """Emit the freshly-minted OIDC credentials as JSON for the deploy script to
    push into Secrets Manager (scripts/deploy-zitadel.sh). Kept out of Python so
    this stays a stdlib-only script (no boto3); the deploy job has the AWS CLI."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "issuer": issuer,
    }
    Path(path).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    print(f"==> Wrote OIDC credentials JSON to {path}")


def _print_secrets(
    *,
    client_id: str,
    client_secret: str,
    mgmt_token: str,
    issuer: str,
) -> None:
    print("")
    print("=== Paste into GitHub Environment (beta or prod) ===")
    print("")
    print("Variables:")
    print(f"  ZITADEL_ISSUER={issuer}")
    print(f"  ZITADEL_CLIENT_ID={client_id}")
    print("")
    print("Secrets (Actions → Environment secrets → deploy via Terraform app_secrets):")
    print(f"  ZITADEL_CLIENT_SECRET={client_secret}")
    print(f"  ZITADEL_MGMT_TOKEN={mgmt_token}")
    print("")
    print("SESSION_SECRET is generated by Terraform — do not paste it here.")
    print("")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env",
        choices=sorted(ENV_PRESETS),
        default="local",
        help="Target environment presets (default: local)",
    )
    parser.add_argument(
        "--print-secrets",
        action="store_true",
        help="Print GitHub/Terraform secret values instead of writing .env (cloud)",
    )
    parser.add_argument(
        "--emit-json",
        metavar="PATH",
        default="",
        help=(
            "Cloud: write the minted OIDC client id/secret to PATH as JSON for "
            "deploy-zitadel.sh to push into Secrets Manager (implies cloud mode)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run bootstrap even when .env already has OIDC credentials (local)",
    )
    return parser.parse_args()


def _ensure_instance_config(
    base: str, host_header: str, pat: str, *, instance_owner: bool
) -> None:
    """Instance-wide setup shared by all projects: GitHub IdP, login branding,
    and the human super-admin. Only the instance-owning environment (local or
    prod) runs these — beta consumes the shared prod instance and must not redo
    them."""
    if not instance_owner:
        print(
            "==> Skipping instance-level config "
            "(GitHub IdP / branding / super-admin owned by prod)"
        )
        return
    try:
        _ensure_github_idp(base, host_header, pat)
    except RuntimeError as exc:
        print(f"WARNING: GitHub IdP setup failed: {exc}", file=sys.stderr)
    _ensure_branding(base, host_header, pat)
    _ensure_super_admin(base, host_header, pat)


def main() -> int:
    args = _parse_args()
    _apply_env_preset(args.env)
    instance_owner = args.env in INSTANCE_OWNER_ENVS
    project_name = PROJECT_NAMES.get(args.env, "Propel")

    if args.env == "local" and not args.force and _already_configured_local():
        print(f"==> OIDC already configured in {ENV_FILE} — skipping OIDC app setup")
        base, host_header = _resolve_zitadel_base()
        _wait_for_zitadel(base, host_header)
        try:
            pat = _load_pat()
            _ensure_instance_config(base, host_header, pat, instance_owner=True)
        except RuntimeError as exc:
            print(f"WARNING: instance config failed: {exc}", file=sys.stderr)
        return 0

    redirect_uri = (
        _env("OAUTH_CALLBACK_BASE_URL", "http://localhost:8000").rstrip("/")
        + "/api/v1/auth/callback"
    )
    logout_uri = _env("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    issuer = _env("ZITADEL_ISSUER", "http://localhost:8080")
    cloud = args.env in {"beta", "prod"}

    base, host_header = _resolve_zitadel_base()
    print(f"==> Waiting for Zitadel at {base} (Host: {host_header})...")
    _wait_for_zitadel(base, host_header)
    print("==> Zitadel API is ready")
    if not cloud:
        _wait_for_login_ui()
        print("==> Zitadel login UI is ready")

    pat = _load_pat()
    org_id = _find_default_org_id(base, host_header, pat)
    project_id = _ensure_named_project(base, host_header, pat, project_name)
    print(f"==> Using project '{project_name}' ({project_id})")
    if org_id:
        print(f"==> Using org {org_id}")

    client_id, client_secret, created = _create_oidc_app(
        base,
        host_header,
        pat,
        project_id,
        redirect_uri,
        logout_uri,
        dev_mode=not cloud,
    )
    if created:
        print(f"==> Created OIDC app '{APP_NAME}'")

    if cloud or args.print_secrets or args.emit_json:
        _ensure_instance_config(base, host_header, pat, instance_owner=instance_owner)
        if args.emit_json:
            _write_secrets_json(
                args.emit_json,
                client_id=client_id,
                client_secret=client_secret,
                issuer=issuer.rstrip("/"),
            )
        else:
            _print_secrets(
                client_id=client_id,
                client_secret=client_secret,
                mgmt_token=pat,
                issuer=issuer.rstrip("/"),
            )
        return 0

    session_secret = secrets.token_hex(32)
    updates = {
        "ZITADEL_ISSUER": issuer,
        "ZITADEL_INTERNAL_ISSUER": _env(
            "ZITADEL_INTERNAL_ISSUER", "http://zitadel:8080"
        ),
        "ZITADEL_CLIENT_ID": client_id,
        "ZITADEL_CLIENT_SECRET": client_secret,
        "ZITADEL_MGMT_TOKEN": pat,
        "SESSION_SECRET": session_secret,
        "OAUTH_CALLBACK_BASE_URL": _env(
            "OAUTH_CALLBACK_BASE_URL", "http://localhost:8000"
        ),
        "FRONTEND_BASE_URL": logout_uri,
    }
    if org_id:
        updates["ZITADEL_ORG_ID"] = org_id
    _merge_env(ENV_FILE, updates)
    print(f"==> Wrote OIDC credentials to {ENV_FILE}")

    try:
        _ensure_instance_config(base, host_header, pat, instance_owner=instance_owner)
    except RuntimeError as exc:
        print(f"WARNING: instance config failed: {exc}", file=sys.stderr)
        print("WARNING: OIDC credentials were written; restart backend anyway.")

    print("==> Restart the backend: docker compose restart backend")
    return 0


if __name__ == "__main__":
    for env_path in (ENV_FILE, REPO_ROOT / ".env.ingestion.local"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
