"""tap-github-copilot entrypoint."""

from __future__ import annotations

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_github_copilot.streams import CopilotUsageStream


class TapGitHubCopilot(Tap):
    name = "tap-github-copilot"

    config_jsonschema = th.PropertiesList(
        th.Property("org", th.StringType, required=True),
        th.Property("auth_token", th.StringType, required=True, secret=True),
    ).to_dict()

    def discover_streams(self) -> list[CopilotUsageStream]:
        return [CopilotUsageStream(self)]


if __name__ == "__main__":
    TapGitHubCopilot.cli()
