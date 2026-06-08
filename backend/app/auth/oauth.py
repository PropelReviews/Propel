from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2

from app.config import get_settings

settings = get_settings()

google_oauth_client = GoogleOAuth2(
    settings.oauth_google_client_id,
    settings.oauth_google_client_secret,
)

# Login/link OAuth client. Prefers the ingestion GitHub App's user-authorization
# credentials (reuse one app) and falls back to a standalone GitHub OAuth app.
github_oauth_client = GitHubOAuth2(
    settings.github_oauth_client_id,
    settings.github_oauth_client_secret,
)
