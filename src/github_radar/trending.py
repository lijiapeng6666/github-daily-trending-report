"""Read daily rankings without substituting search results."""

import re

from bs4 import BeautifulSoup

from .models import Repository


def parse_number(text: str | None) -> int | None:
    if text is None or not text.strip():
        return None
    value = text.strip()
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", value):
        raise ValueError(f"无法识别 Star 数值：{value}")
    return int(value.replace(",", ""))


def parse_trending(html: str, limit: int = 20) -> list[Repository]:
    if not 1 <= limit <= 100:
        raise ValueError("抓取数量必须在 1 至 100 之间")
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("article.Box-row")
    if not rows:
        raise ValueError("未找到 Trending 仓库，可能是网络返回或网页结构发生变化")
    repos: list[Repository] = []
    seen: set[str] = set()
    for rank, row in enumerate(rows, start=1):
        link = row.select_one("h2 a[href]")
        if link is None:
            raise ValueError(f"榜单第 {rank} 项缺少仓库链接")
        href = str(link.get("href"))
        if not href.startswith("/") or href.startswith("//"):
            raise ValueError(f"榜单第 {rank} 项仓库链接格式不正确")
        full_name = href[1:]
        description = row.select_one("p")
        language = row.select_one('[itemprop="programmingLanguage"]')
        total = row.find("a", href=f"/{full_name}/stargazers")
        daily = row.select_one("span.float-sm-right")
        daily_text = daily.get_text(" ", strip=True) if daily else None
        match = re.fullmatch(r"([\d,]+)\s+stars? today", daily_text) if daily_text else None
        if daily_text and match is None:
            raise ValueError(f"榜单第 {rank} 项当日增长格式发生变化")
        repo = Repository(
            full_name=full_name,
            trending_rank=rank,
            description_original=description.get_text(" ", strip=True) if description else None,
            language=language.get_text(strip=True) if language else None,
            stars_total=parse_number(total.get_text(strip=True) if total else None),
            stars_today=parse_number(match.group(1) if match else None),
        )
        if full_name.casefold() in seen:
            continue
        seen.add(full_name.casefold())
        repos.append(repo)
        if len(repos) == limit:
            break
    if not repos:
        raise ValueError("Trending 解析结果为空")
    return repos
