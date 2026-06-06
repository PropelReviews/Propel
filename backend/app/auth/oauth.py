from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2

from app.config import get_settings

settings = get_settings()

google_oauth_client = GoogleOAuth2(
    settings.oauth_google_client_id,
    settings.oauth_google_client_secret,
)

github_oauth_client = GitHubOAuth2(
    settings.oauth_github_client_id,
    settings.oauth_github_client_secret,
)

OAUTH_STATE_SECRET = settings.jwt_secret
