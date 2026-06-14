"""Minimal GitHub OAuth client for account linking (not login)."""

from httpx_oauth.clients.github import GitHubOAuth2

from app.config import get_settings

settings = get_settings()

github_oauth_client = GitHubOAuth2(
    settings.github_oauth_client_id,
    settings.github_oauth_client_secret,
)
