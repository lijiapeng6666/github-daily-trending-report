from datetime import datetime
from pathlib import Path

import httpx
import pytest

from github_radar.classify import load_settings
from github_radar.models import Report, Repository
from github_radar.publish import publish, writer_lock
from github_radar.report import enrich_repository, make_report


def example_report(description="A tool", day="2026-10-08"):
    repo = Repository(full_name="org/repo", trending_rank=1, description_original=description)
    return Report(
        report_date=day,
        fetched_at=f"{day}T08:17:00+08:00",
        repos=[repo],
    )


def test_api_enrichment_keeps_daily_growth():
    repo = Repository(full_name="org/repo", trending_rank=3, stars_today=10, stars_total=80)
    payload = {
        "stargazers_count": 90,
        "description": "Description",
        "language": "Rust",
        "topics": ["cli"],
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as client:
        result = enrich_repository(repo, client)
    assert result.stars_today == 10
    assert result.stars_total == 90
    assert result.trending_rank == 3
    assert result.description_source == "github_api"
    assert result.metadata_fetched_at is not None


def test_partial_api_failure_preserves_source_data():
    repo = Repository(full_name="org/repo", trending_rank=1, stars_today=0, stars_total=50)
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        report = make_report(
            [repo],
            client,
            load_settings(Path("config.toml")),
            datetime.fromisoformat("2026-10-08T08:17:00+08:00"),
        )
    assert report.status == "partial"
    assert report.repos[0].stars_total == 50
    assert report.repos[0].stars_today == 0
    assert report.warnings


@pytest.mark.parametrize("payload", [{"stargazers_count": -1}, {"topics": "not-a-list"}])
def test_invalid_api_payload_is_rejected(payload):
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(ValueError):
            enrich_repository(Repository(full_name="org/repo", trending_rank=1), client)


def test_report_date_requires_matching_aware_collection_time():
    with pytest.raises(ValueError):
        Report(report_date="2026-10-08", fetched_at="2026-10-07T08:00:00+08:00", repos=[])


def test_publication_escapes_untrusted_content_and_script_data(tmp_path):
    report = example_report('</script><img src=x onerror="alert(1)">')
    publish(report, "source", tmp_path / "data", tmp_path / "site")
    html = (tmp_path / "site/index.html").read_text()
    assert "&lt;/script&gt;" in html
    assert '<img src=x onerror="alert(1)">' not in html
    assert "暂无数据" in html
    assert '<article class="repo"' in html


def test_history_survives_rebuild_and_same_day_replacement(tmp_path):
    data, site = tmp_path / "data", tmp_path / "site"
    publish(example_report(day="2026-10-07"), "first", data, site)
    publish(example_report(), "second", data, site)
    publish(example_report("updated"), "third", data, site)
    assert len(list((data / "reports").glob("*.json"))) == 2
    assert (site / "reports/2026-10-07.html").exists()
    assert "updated" in (site / "index.html").read_text()
    assert "2026-10-07" in (site / "archive.html").read_text()


def test_failed_render_leaves_previous_data_and_site(tmp_path, monkeypatch):
    data, site = tmp_path / "data", tmp_path / "site"
    publish(example_report("before"), "first", data, site)
    before = (site / "index.html").read_bytes()
    before_json = (data / "reports/2026-10-08.json").read_bytes()

    def fail(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr("github_radar.publish.render_site", fail)
    with pytest.raises(RuntimeError):
        publish(example_report("after"), "second", data, site)
    assert (site / "index.html").read_bytes() == before
    assert (data / "reports/2026-10-08.json").read_bytes() == before_json


def test_writer_lock_excludes_concurrent_generation(tmp_path):
    with writer_lock(tmp_path):
        with pytest.raises(RuntimeError, match="正在"):
            with writer_lock(tmp_path):
                pass


def test_zero_and_missing_have_different_display(tmp_path):
    report = example_report().model_copy(
        update={
            "repos": [
                Repository(full_name="org/repo", trending_rank=1, stars_today=0, stars_total=0)
            ]
        }
    )
    publish(report, "source", tmp_path / "data", tmp_path / "site")
    html = (tmp_path / "site/index.html").read_text()
    assert "+0" in html
    assert "0 Star" in html


def test_failed_site_replacement_rolls_back_snapshot(tmp_path, monkeypatch):
    data, site = tmp_path / "data", tmp_path / "site"
    publish(example_report("before"), "first", data, site)
    before = (data / "reports/2026-10-08.json").read_bytes()

    def fail(*args):
        raise OSError("replacement failed")

    monkeypatch.setattr("github_radar.publish.replace_site", fail)
    with pytest.raises(OSError):
        publish(example_report("after"), "second", data, site)
    assert (data / "reports/2026-10-08.json").read_bytes() == before
    assert (data / "sources/2026-10-08.html").read_text() == "first"


def test_refuse_to_overwrite_unrelated_folder(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    (output / "user-file.txt").write_text("keep")
    with pytest.raises(ValueError, match="不是 Radar"):
        publish(example_report(), "source", tmp_path / "data", output)
    assert (output / "user-file.txt").read_text() == "keep"
