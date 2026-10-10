"""Manual collection and offline rebuild entry points."""

import argparse
import logging
import os
from pathlib import Path

import httpx

from .classify import load_settings
from .models import TRENDING_URL, now
from .network import request
from .publish import publish, writer_lock
from .report import make_report
from .trending import parse_trending

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成真实 GitHub Daily Trending 日报")
    parser.add_argument("command", choices=["generate", "rebuild"])
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("site"))
    parser.add_argument("--no-api", action="store_true", help="仅使用榜单数据，明确标记 API 未补充")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings = load_settings(args.config)
        with writer_lock(args.data_dir):
            if args.command == "rebuild":
                publish(None, None, args.data_dir, args.output, settings.report.ai_first)
                logger.info("已从存档重建日报：%s", args.output.resolve() / "index.html")
                return 0
            with httpx.Client(timeout=20, headers={"User-Agent": "GitHub-Radar/0.1"}) as client:
                logger.info("正在读取 GitHub Daily Trending")
                html = request(client, TRENDING_URL).text
                fetched_at = now()
                repos = parse_trending(html, settings.report.limit)
                report = make_report(
                    repos,
                    client,
                    settings,
                    fetched_at,
                    token=os.environ.get("GITHUB_TOKEN"),
                    skip_api=args.no_api,
                )
            publish(report, html, args.data_dir, args.output, settings.report.ai_first)
            logger.info(
                "已生成 %s 日报，共 %s 个项目：%s",
                report.report_date,
                len(report.repos),
                args.output.resolve() / "index.html",
            )
            for warning in report.warnings:
                logger.warning("%s", warning)
        return 0
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as error:
        # Never print request headers, tokens, or an upstream response body.
        reason = (
            f"HTTP {error.response.status_code}"
            if isinstance(error, httpx.HTTPStatusError)
            else type(error).__name__
            if isinstance(error, httpx.HTTPError)
            else str(error)
        )
        logger.error("日报未更新，上一份成功结果保留：%s", reason)
        return 1
