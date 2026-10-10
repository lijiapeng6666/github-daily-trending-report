"""Editable, evidence-bearing classification with keyword boundaries."""

import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .models import Repository


class ReportSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=100, strict=True)
    ai_first: bool = True


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: ReportSettings = Field(default_factory=ReportSettings)
    classification: dict[str, list[str]] = Field(default_factory=dict)


def load_settings(path: Path) -> Settings:
    with path.open("rb") as source:
        settings = Settings.model_validate(tomllib.load(source))
    if any(
        not category.strip() or any(not word.strip() for word in words)
        for category, words in settings.classification.items()
    ):
        raise ValueError("分类名和关键词不能为空")
    return settings


def normalize(text: str) -> str:
    return text.casefold().replace("-", " ").replace("_", " ")


def classify_repository(repo: Repository, rules: dict[str, list[str]]) -> Repository:
    text = normalize(" ".join([repo.full_name, repo.description_original or "", *repo.topics]))
    ordered = sorted(rules.items(), key=lambda item: item[0] != "AI / Agent")
    for category, keywords in ordered:
        for keyword in keywords:
            if re.search(r"(?<![a-z0-9])" + re.escape(normalize(keyword)) + r"(?![a-z0-9])", text):
                tags = [
                    tag.upper() if tag != "agent" else "Agent"
                    for tag in ("agent", "llm", "rag", "mcp")
                    if re.search(r"(?<![a-z0-9])" + tag + r"s?(?![a-z0-9])", text)
                ]
                return repo.model_copy(
                    update={
                        "category": category,
                        "classification_reason": f"关键词：{keyword}",
                        "ai_tags": tags if category == "AI / Agent" else [],
                    }
                )
    return repo
