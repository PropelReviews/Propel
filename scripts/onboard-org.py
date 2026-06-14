#!/usr/bin/env python3
"""Onboard a new customer organization onto Propel (Zitadel Model B).

Creates a Zitadel organization for the customer with a first admin user, grants
that org access to the per-environment Propel project, and assigns the admin the
``owner`` project role so they can authenticate immediately (the project gates
login on holding a role). The admin, as ORG_OWNER, can then invite teammates and
assign them roles from their own management console.

    scripts/onboard-org.py --env prod \\
        --org "Acme Corp" \\
        --admin-email admin@acme.com \\
        --admin-name "Ada Lovelace"

Auth/connection are resolved exactly like zitadel_bootstrap.py:
  * ZITADEL_ISSUER / ZITADEL_HOST_HEADER (preset per --env)
  * ZITADEL_MGMT_TOKEN, or the on-disk/container bootstrap PAT (local)
"""

from __future__ import annotations

import argparse
import secrets
import string
import sys

import zitadel_bootstrap as zb


def _strong_password() -> str:
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(20))
    # Guarantee the character classes Zitadel's default policy expects.
    return f"Aa1!{body}"


def _find_project_id(base: str, host: str, pat: str, name: str) -> str | None:
    payload = zb._request(
        base, host, pat, "POST", "/management/v1/projects/_search", {"queries": []}
    )
    for project in payload.get("result") or []:
        if project.get("name") == name:
            return str(project["id"])
    return None


def _setup_org(
    base: str,
    host: str,
    pat: str,
    *,
    org_name: str,
    domain: str,
    admin_email: str,
    first: str,
    last: str,
    password: str,
    org_roles: list[str],
) -> tuple[str, str]:
    """Create the org + first admin via admin/v1/orgs/_setup. Returns
    (org_id, user_id)."""
    human = {
        "userName": admin_email,
        "profile": {"firstName": first, "lastName": last},
        "email": {"email": admin_email, "isEmailVerified": True},
        "password": password,
    }
    org = {"name": org_name}
    if domain:
        org["domain"] = domain
    body = {"org": org, "human": human, "roles": org_roles}
    resp = zb._request(base, host, pat, "POST", "/admin/v1/orgs/_setup", body)
    org_id = str(resp.get("orgId") or resp.get("organizationId") or "")
    user_id = str(resp.get("userId") or "")
    if not org_id or not user_id:
        raise RuntimeError(f"unexpected _setup response: {resp}")
    return org_id, user_id


def _grant_project_to_org(
    base: str,
    host: str,
    pat: str,
    *,
    project_id: str,
    granted_org_id: str,
    role_keys: list[str],
) -> str:
    resp = zb._request(
        base,
        host,
        pat,
        "POST",
        f"/management/v1/projects/{project_id}/grants",
        {"grantedOrgId": granted_org_id, "roleKeys": role_keys},
    )
    return str(resp.get("grantId") or "")


def _grant_role_to_user(
    base: str,
    host: str,
    pat: str,
    *,
    user_id: str,
    project_id: str,
    project_grant_id: str,
    role_keys: list[str],
) -> None:
    body: dict = {"projectId": project_id, "roleKeys": role_keys}
    if project_grant_id:
        body["projectGrantId"] = project_grant_id
    zb._request(base, host, pat, "POST", f"/management/v1/users/{user_id}/grants", body)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=sorted(zb.ENV_PRESETS), default="prod")
    parser.add_argument("--org", required=True, help="Customer organization name")
    parser.add_argument("--admin-email", required=True, help="First admin's email")
    parser.add_argument("--admin-name", default="", help="First admin's display name")
    parser.add_argument("--domain", default="", help="Optional verified org domain")
    parser.add_argument(
        "--admin-password",
        default="",
        help="Initial password (generated + printed if omitted)",
    )
    parser.add_argument(
        "--project-roles",
        default="owner,admin,manager,member",
        help="Project roles delegated to the customer org (comma-separated)",
    )
    parser.add_argument(
        "--admin-role",
        default="owner",
        help="Project role assigned to the first admin (default: owner)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    zb._apply_env_preset(args.env)
    project_name = zb.PROJECT_NAMES.get(args.env, "Propel")

    base, host = zb._resolve_zitadel_base()
    zb._wait_for_zitadel(base, host)
    pat = zb._load_pat()

    project_id = _find_project_id(base, host, pat, project_name)
    if not project_id:
        raise RuntimeError(
            f"Project '{project_name}' not found — run zitadel_bootstrap.py "
            f"--env {args.env} first."
        )

    name_parts = (args.admin_name or args.admin_email.split("@")[0]).split(" ", 1)
    first = name_parts[0]
    last = name_parts[1] if len(name_parts) > 1 else first
    password = args.admin_password or _strong_password()
    project_roles = [r.strip() for r in args.project_roles.split(",") if r.strip()]

    org_id, user_id = _setup_org(
        base,
        host,
        pat,
        org_name=args.org,
        domain=args.domain,
        admin_email=args.admin_email,
        first=first,
        last=last,
        password=password,
        org_roles=["ORG_OWNER"],
    )
    print(f"==> Created org '{args.org}' ({org_id}) with admin {args.admin_email}")

    grant_id = _grant_project_to_org(
        base,
        host,
        pat,
        project_id=project_id,
        granted_org_id=org_id,
        role_keys=project_roles,
    )
    print(f"==> Granted project '{project_name}' to org ({grant_id or 'no-id'})")

    try:
        _grant_role_to_user(
            base,
            host,
            pat,
            user_id=user_id,
            project_id=project_id,
            project_grant_id=grant_id,
            role_keys=[args.admin_role],
        )
        print(f"==> Assigned '{args.admin_role}' role to {args.admin_email}")
    except RuntimeError as exc:
        print(
            f"WARNING: could not auto-assign the admin's project role ({exc}). "
            "Assign it in the console: Org -> Authorizations.",
            file=sys.stderr,
        )

    if not args.admin_password:
        print("")
        print(f"Initial password for {args.admin_email}: {password}")
        print("Share securely; the user should change it or sign in via GitHub SSO.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
