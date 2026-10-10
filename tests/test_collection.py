from pathlib import Path

import pytest

from github_radar.classify import classify_repository, load_settings
from github_radar.models import Repository
from github_radar.trending import parse_number, parse_trending


def row(name="org/repo", language="Python", total="1,234", today="25", description="a tool"):
    lang = f'<span itemprop="programmingLanguage">{language}</span>' if language else ""
    star = f'<a href="/{name}/stargazers">{total}</a>' if total else ""
    growth = f'<span class="float-sm-right">{today} stars today</span>' if today else ""
    return (
        f'<article class="Box-row"><h2><a href="/{name}">{name}</a></h2>'
        f"<p>{description}</p>{lang}{star}{growth}</article>"
    )


@pytest.mark.parametrize("text,expected", [("1,284", 1284), ("0", 0), (None, None)])
def test_numbers_preserve_zero_and_missing(text, expected):
    assert parse_number(text) == expected


def test_invalid_number_is_not_zero():
    with pytest.raises(ValueError):
        parse_number("unknown")


def test_parse_source_fields():
    repo = parse_trending(row(), 20)[0]
    assert repo.full_name == "org/repo"
    assert repo.trending_rank == 1
    assert repo.stars_today == 25
    assert repo.stars_total == 1234
    assert repo.language == "Python"
    assert repo.html_url == "https://github.com/org/repo"


def test_deduplicate_without_changing_source_rank():
    repos = parse_trending(row() + row() + row("org/second"), 2)
    assert [(repo.full_name, repo.trending_rank) for repo in repos] == [
        ("org/repo", 1),
        ("org/second", 3),
    ]


def test_missing_fields_stay_missing():
    repo = parse_trending(row(language="", total="", today=""), 20)[0]
    assert repo.language is None
    assert repo.stars_total is None
    assert repo.stars_today is None


@pytest.mark.parametrize("html", ["<h1>temporarily unavailable</h1>", row("org/repo/issues")])
def test_reject_empty_or_malformed_source(html):
    with pytest.raises(ValueError):
        parse_trending(html, 20)


def test_reject_invalid_identity():
    with pytest.raises(ValueError):
        Repository(full_name="javascript:alert(1)", trending_rank=1)


@pytest.mark.parametrize("name", ["org/.", "org/.."])
def test_reject_navigation_segments_as_repository_name(name):
    with pytest.raises(ValueError):
        Repository(full_name=name, trending_rank=1)


def test_invalid_link_rejected_before_css_selector_use():
    html = '<article class="Box-row"><h2><a href="/org/repo&quot;]">repo</a></h2></article>'
    with pytest.raises(ValueError):
        parse_trending(html)


@pytest.mark.parametrize(
    "name,description,topics,expected",
    [
        ("org/mail", "email utilities", [], "其他"),
        ("org/x", "stateful agent workflows", [], "AI / Agent"),
        ("org/x", "a tool", ["large-language-models"], "AI / Agent"),
        ("org/x", "a code editor", [], "开发工具"),
        ("org/x", "a postgres database", [], "基础设施"),
        ("org/x", "a dashboard", [], "应用与内容"),
        ("org/x", "database for AI agents", [], "AI / Agent"),
        ("org/x", "智能体工作流", [], "AI / Agent"),
    ],
)
def test_classification_boundaries(name, description, topics, expected):
    repo = Repository(
        full_name=name, trending_rank=1, description_original=description, topics=topics
    )
    classified = classify_repository(repo, load_settings(Path("config.toml")).classification)
    assert classified.category == expected
    assert classified.trending_rank == 1
    if expected != "其他":
        assert classified.classification_reason


def test_configuration_rejects_out_of_range_limit(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[report]\nlimit = 0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(config)
