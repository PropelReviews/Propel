"""Schemas for per-user dashboard layout backups."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DashboardTile(BaseModel):
    i: str = Field(..., min_length=1, description="Metric id placed on the tile")
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., ge=1, le=24)
    h: int = Field(..., ge=1, le=24)


class DashboardLayoutV2(BaseModel):
    version: Literal[2] = 2
    range: str | None = None
    granularity: str | None = None
    tiles: list[DashboardTile] = Field(default_factory=list)

    @field_validator("tiles")
    @classmethod
    def _unique_tile_ids(cls, tiles: list[DashboardTile]) -> list[DashboardTile]:
        seen: set[str] = set()
        for tile in tiles:
            if tile.i in seen:
                raise ValueError(f"duplicate tile id {tile.i!r}")
            seen.add(tile.i)
        return tiles


class DashboardPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    layout: dict[str, Any]
    updated_at: datetime


class DashboardPreferencePut(BaseModel):
    layout: DashboardLayoutV2
