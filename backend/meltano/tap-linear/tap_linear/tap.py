"""tap-linear entrypoint."""

from __future__ import annotations

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_linear.streams import IssuesStream


class TapLinear(Tap):
    name = "tap-linear"

    config_jsonschema = th.PropertiesList(
        th.Property("auth_token", th.StringType, required=True, secret=True),
        th.Property(
            "start_date",
            th.DateTimeType,
            description="Only pull issues updated on or after this date.",
        ),
    ).to_dict()

    def discover_streams(self) -> list[IssuesStream]:
        return [IssuesStream(self)]


if __name__ == "__main__":
    TapLinear.cli()
