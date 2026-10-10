"""Build an honest snapshot even when repository metadata is unavailable."""

import logging
from datetime import datetime

import httpx

from .classify import Settings, classify_repository
from .models import SHANGHAI, Report, Repository, now
from .network import request

logger = logging.getLogger(__name__)


def enrich_repository(
    repo: Repository, client: httpx.Client, token: str | None = None
) -> Repository:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = request(
        client, f"https://api.github.com/repos/{repo.full_name}", headers=headers
    ).json()
    if not isinstance(payload, dict):
        raise ValueError("仓库 API 返回格式错误")
    fields = repo.model_dump(exclude={"owner", "name", "html_url"})
    for key, source in (
        ("stars_total", "stargazers_count"),
        ("language", "language"),
        ("topics", "topics"),
    ):
        if source in payload:
            fields[key] = payload[source]
    if payload.get("description"):
        fields["description_original"] = payload["description"]
        fields["description_source"] = "github_api"
    fields["metadata_fetched_at"] = now()
    return Repository.model_validate(fields)


def make_report(
    repos: list[Repository],
    client: httpx.Client,
    settings: Settings,
    fetched_at: datetime,
    *,
    token: str | None = None,
    skip_api: bool = False,
) -> Report:
    warnings = []
    if len(repos) < settings.report.limit:
        warnings.append(f"榜单仅采集到 {len(repos)} 个项目，目标为 {settings.report.limit} 个。")
    if skip_api:
        warnings.append("本次未补充 GitHub API 元数据，保留榜单原始信息。")
    result = []
    api_blocked = skip_api
    for repo in repos:
        logger.info("处理仓库 %s", repo.full_name)
        if not api_blocked:
            try:
                repo = enrich_repository(repo, client, token)
            except httpx.HTTPStatusError as error:
                code = error.response.status_code
                warnings.append(f"{repo.full_name}：API 补充失败（HTTP {code}），保留榜单数据。")
                if code in (401, 403, 429):
                    api_blocked = True
                    warnings.append("API 暂时不可用，剩余项目保留榜单数据。")
            except (httpx.TransportError, ValueError):
                warnings.append(f"{repo.full_name}：API 网络或数据格式错误，保留榜单数据。")
        if repo.stars_today is None or repo.stars_total is None:
            warnings.append(f"{repo.full_name}：部分 Star 数据缺失。")
        result.append(classify_repository(repo, settings.classification))
    return Report(
        report_date=fetched_at.astimezone(SHANGHAI).date(),
        fetched_at=fetched_at,
        status="partial" if warnings else "complete",
        warnings=warnings,
        repos=result,
    )
