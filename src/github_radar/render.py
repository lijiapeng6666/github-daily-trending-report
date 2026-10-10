"""Render self-contained pages with autoescaped source text."""

from collections import Counter
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .models import SHANGHAI, Report

COLORS = {"AI / Agent": "#18744c", "开发工具": "#315da0", "基础设施": "#926623"}


def format_number(value: int | None) -> str:
    return "暂无数据" if value is None else f"{value:,}"


def render_site(reports: list[Report], destination: Path, ai_first: bool = True) -> None:
    resources = files("github_radar").joinpath("resources")
    environment = Environment(
        loader=FileSystemLoader(str(resources)),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
    )
    environment.filters["number"] = format_number
    assets = {
        name.replace(".", "_"): resources.joinpath(name).read_text(encoding="utf-8")
        for name in ("radar.css", "filters.js", "radar.js")
    }
    reports = sorted(reports, key=lambda report: report.report_date, reverse=True)
    if not reports:
        raise ValueError("没有已保存的日报可供渲染")
    (destination / "reports").mkdir(parents=True, exist_ok=True)
    template = environment.get_template("report.html")
    for report in reports:
        context = dict(
            report=report,
            repos=sorted(
                report.repos,
                key=lambda repo: (ai_first and repo.category != "AI / Agent", repo.trending_rank),
            ),
            reports=reports,
            counts=Counter(repo.category for repo in report.repos),
            languages=sorted({repo.language or "未标注" for repo in report.repos}),
            ai_count=sum(repo.category == "AI / Agent" for repo in report.repos),
            colors=COLORS,
            ai_first=ai_first,
            timestamp=report.fetched_at.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S CST"),
            data={
                "repos": [repo.model_dump(mode="json") for repo in report.repos],
                "aiFirst": ai_first,
            },
            **assets,
        )
        html = template.render(**context, prefix="../", report_prefix="")
        (destination / "reports" / f"{report.report_date}.html").write_text(html, encoding="utf-8")
        if report is reports[0]:
            (destination / "index.html").write_text(
                template.render(**context, prefix="", report_prefix="reports/"), encoding="utf-8"
            )
    (destination / "archive.html").write_text(
        environment.get_template("archive.html").render(reports=reports, **assets), encoding="utf-8"
    )
