import subprocess

import pytest
from test_reports import example_report

from github_radar.history import restore_history, save_history
from github_radar.publish import atomic_write


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(path)], check=True, capture_output=True)
    return str(path)


def report(data, day="2026-10-08", description="A tool"):
    atomic_write(
        data / "reports" / f"{day}.json",
        example_report(description, day).model_dump_json(indent=2),
    )
    atomic_write(data / "sources" / f"{day}.html", "<html>source</html>")


def test_first_run_bootstraps_then_restores_history(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "checkout"
    report(data)
    assert restore_history(remote, data, checkout) is False
    assert save_history(data, checkout) is True
    assert git(checkout, "log", "-1", "--format=%B").endswith(
        "Co-authored-by: Claude fable 5 (1M context) <noreply@anthropic.com>"
    )
    fresh = tmp_path / "fresh"
    assert restore_history(remote, fresh, tmp_path / "second") is True
    assert (fresh / "reports/2026-10-08.json").read_bytes() == (
        data / "reports/2026-10-08.json"
    ).read_bytes()
    assert (fresh / "sources/2026-10-08.html").exists()


def test_multiple_days_and_same_day_updates_preserve_previous(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "first"
    restore_history(remote, data, checkout)
    report(data)
    save_history(data, checkout)
    second = tmp_path / "second"
    restore_history(remote, data, second)
    report(data, "2026-10-09")
    report(data, description="Updated")
    save_history(data, second)
    fresh = tmp_path / "fresh"
    restore_history(remote, fresh, tmp_path / "third")
    assert sorted(p.name for p in (fresh / "reports").glob("*.json")) == [
        "2026-10-08.json",
        "2026-10-09.json",
    ]
    assert "Updated" in (fresh / "reports/2026-10-08.json").read_text()
    assert save_history(fresh, tmp_path / "third") is False


def test_unavailable_remote_is_not_treated_as_empty(tmp_path):
    data = tmp_path / "data"
    report(data)
    before = (data / "reports/2026-10-08.json").read_bytes()
    with pytest.raises(RuntimeError, match="Git"):
        restore_history(str(tmp_path / "missing.git"), data, tmp_path / "checkout")
    assert (data / "reports/2026-10-08.json").read_bytes() == before


def test_invalid_data_cannot_be_saved(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "checkout"
    restore_history(remote, data, checkout)
    atomic_write(data / "reports/2026-10-08.json", "{}")
    with pytest.raises(ValueError):
        save_history(data, checkout)
    assert git(checkout, "ls-remote", "origin", "refs/heads/report-data") == ""


def test_invalid_remote_does_not_overwrite_local_data(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "checkout"
    restore_history(remote, data, checkout)
    report(data)
    save_history(data, checkout)
    atomic_write(checkout / "reports/2026-10-08.json", "{}")
    git(checkout, "add", "reports")
    git(
        checkout,
        "commit",
        "-m",
        "test: invalid history fixture\n\n"
        "Co-authored-by: Claude fable 5 (1M context) <noreply@anthropic.com>",
    )
    git(checkout, "push", "origin", "HEAD:refs/heads/report-data")
    before = (data / "reports/2026-10-08.json").read_bytes()
    with pytest.raises(ValueError):
        restore_history(remote, data, tmp_path / "fresh")
    assert (data / "reports/2026-10-08.json").read_bytes() == before


def test_stale_writer_cannot_force_overwrite_new_history(remote, tmp_path):
    first_data, second_data = tmp_path / "data1", tmp_path / "data2"
    first, second = tmp_path / "first", tmp_path / "second"
    restore_history(remote, first_data, first)
    report(first_data)
    save_history(first_data, first)
    restore_history(remote, second_data, second)
    report(first_data, "2026-10-09")
    save_history(first_data, first)
    report(second_data, "2026-10-10")
    with pytest.raises(RuntimeError, match="Git"):
        save_history(second_data, second)
    fresh = tmp_path / "fresh"
    restore_history(remote, fresh, tmp_path / "third")
    assert (fresh / "reports/2026-10-09.json").exists()
    assert not (fresh / "reports/2026-10-10.json").exists()


def test_deleted_local_history_is_rejected(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "checkout"
    restore_history(remote, data, checkout)
    report(data)
    save_history(data, checkout)
    (data / "reports/2026-10-08.json").unlink()
    report(data, "2026-10-09")
    with pytest.raises(ValueError, match="history"):
        save_history(data, checkout)


def test_unrelated_files_are_not_published(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "checkout"
    restore_history(remote, data, checkout)
    report(data)
    atomic_write(data / ".env", "SECRET=never-publish")
    atomic_write(data / "sources/private.txt", "secret")
    save_history(data, checkout)
    assert git(checkout, "ls-tree", "-r", "--name-only", "HEAD").splitlines() == [
        "reports/2026-10-08.json",
        "sources/2026-10-08.html",
    ]


def test_snapshot_symlinks_are_rejected(remote, tmp_path):
    data, checkout = tmp_path / "data", tmp_path / "checkout"
    restore_history(remote, data, checkout)
    report(data)
    source = data / "sources/2026-10-08.html"
    source.unlink()
    source.symlink_to(tmp_path / "secret")
    with pytest.raises(ValueError, match="symbolic"):
        save_history(data, checkout)


def test_existing_checkout_is_not_overwritten(remote, tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    atomic_write(checkout / "private.txt", "keep")
    with pytest.raises(ValueError, match="empty"):
        restore_history(remote, tmp_path / "data", checkout)
    assert (checkout / "private.txt").read_text() == "keep"
