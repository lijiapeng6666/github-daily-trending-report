from pathlib import Path

import httpx

from github_radar.cli import main
from github_radar.publish import writer_lock


def arguments(tmp_path):
    return [
        "generate",
        "--config",
        str(Path("config.toml").resolve()),
        "--data-dir",
        str(tmp_path / "data"),
        "--output",
        str(tmp_path / "site"),
    ]


def test_invalid_config_does_not_create_output(tmp_path):
    assert main(["generate", "--config", str(tmp_path / "missing.toml")]) == 1
    assert not (tmp_path / "site").exists()


def test_empty_source_preserves_previous_output(tmp_path, monkeypatch):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("previous")
    monkeypatch.setattr("github_radar.cli.request", lambda *args: httpx.Response(200, text="empty"))
    assert main(arguments(tmp_path)) == 1
    assert (site / "index.html").read_text() == "previous"


def test_locked_writer_makes_no_network_call(tmp_path, monkeypatch):
    def reject(*args):
        raise AssertionError("network called while locked")

    monkeypatch.setattr("github_radar.cli.request", reject)
    with writer_lock(tmp_path / "data"):
        assert main(arguments(tmp_path)) == 1
