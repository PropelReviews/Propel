"""tap-linear entrypoint."""

from __future__ import annotations

from singer_sdk import Stream, Tap
from singer_sdk import typing as th

from tap_linear.streams import (
    CommentsStream,
    IssueDescriptionEditsStream,
    IssuesStream,
    ProjectsStream,
)


class TapLinear(Tap):
    name = "tap-linear"

    config_jsonschema = th.PropertiesList(
        th.Property("auth_token", th.StringType, required=True, secret=True),
        th.Property(
            "start_date",
            th.DateTimeType,
            description=(
                "Only pull records updated on or after this date "
                "(issues, comments, projects, description edits)."
            ),
        ),
    ).to_dict()

    def discover_streams(self) -> list[Stream]:
        return [
            IssuesStream(self),
            CommentsStream(self),
            ProjectsStream(self),
            IssueDescriptionEditsStream(self),
        ]


if __name__ == "__main__":
    TapLinear.cli()
