"""Validated snapshot contracts shared by collection and rendering."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
TRENDING_URL = "https://github.com/trending?since=daily"


class Repository(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+$")
    trending_rank: int = Field(ge=1, strict=True)
    description_original: str | None = None
    description_source: Literal["trending", "github_api"] = "trending"
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    stars_total: int | None = Field(default=None, ge=0, strict=True)
    stars_today: int | None = Field(default=None, ge=0, strict=True)
    metadata_fetched_at: AwareDatetime | None = None
    category: str = "其他"
    ai_tags: list[str] = Field(default_factory=list)
    classification_reason: str | None = None

    @field_validator("full_name")
    @classmethod
    def reject_navigation_segments(cls, value: str) -> str:
        if value.split("/", 1)[1] in (".", ".."):
            raise ValueError("仓库名不能是路径导航片段")
        return value

    @computed_field
    @property
    def owner(self) -> str:
        return self.full_name.split("/", 1)[0]

    @computed_field
    @property
    def name(self) -> str:
        return self.full_name.split("/", 1)[1]

    @computed_field
    @property
    def html_url(self) -> str:
        return f"https://github.com/{self.full_name}"


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    report_date: date
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    fetched_at: AwareDatetime
    source_url: Literal["https://github.com/trending?since=daily"] = TRENDING_URL
    status: Literal["complete", "partial"] = "complete"
    warnings: list[str] = Field(default_factory=list)
    repos: list[Repository] = Field(min_length=1)

    @model_validator(mode="after")
    def check_snapshot(self) -> "Report":
        if self.report_date != self.fetched_at.astimezone(SHANGHAI).date():
            raise ValueError("报告日期必须与实际采集时间一致")
        names = [repo.full_name.casefold() for repo in self.repos]
        ranks = [repo.trending_rank for repo in self.repos]
        if len(set(names)) != len(names) or len(set(ranks)) != len(ranks):
            raise ValueError("日报包含重复仓库或名次")
        if bool(self.warnings) != (self.status == "partial"):
            raise ValueError("日报状态与告警不一致")
        return self


def now() -> datetime:
    return datetime.now(SHANGHAI)
