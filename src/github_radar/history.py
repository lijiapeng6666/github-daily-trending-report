"""Persist validated report snapshots on a dedicated, non-force-pushed branch."""

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from .publish import load_reports

BRANCH = "report-data"
SNAPSHOT = re.compile(r"(?:reports/\d{4}-\d{2}-\d{2}\.json|sources/\d{4}-\d{2}-\d{2}\.html)")
COAUTHOR = "Co-authored-by: Claude fable 5 (1M context) <noreply@anthropic.com>"


def git(checkout: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(checkout), *args], capture_output=True, text=True, check=False
    )
    if result.returncode not in allowed:
        raise RuntimeError(f"Git {args[0]} failed: {result.stderr.strip()}")
    return result


def snapshots(data: Path, *, required: bool = True) -> list[Path]:
    if data.is_symlink() or any((data / part).is_symlink() for part in ("reports", "sources")):
        raise ValueError("Snapshot directories must not be symbolic links")
    if any(path.is_symlink() for path in (data / "reports").glob("*.json")):
        raise ValueError("Snapshots must not be symbolic links")
    reports = load_reports(data)
    if required and not reports:
        raise ValueError("No valid report history to publish")
    paths = []
    for report in reports:
        for folder, suffix in (("reports", "json"), ("sources", "html")):
            path = data / folder / f"{report.report_date}.{suffix}"
            if path.is_symlink():
                raise ValueError("Snapshots must not be symbolic links")
            if path.exists():
                paths.append(path.relative_to(data))
    return paths


def restore_history(remote: str, data: Path, checkout: Path) -> bool:
    if checkout.exists():
        raise ValueError("Use a new, empty history checkout path")
    data_path, checkout_path = data.resolve(), checkout.resolve()
    if (
        checkout_path == data_path
        or checkout_path in data_path.parents
        or data_path in checkout_path.parents
    ):
        raise ValueError("History checkout and data directory must not overlap")
    snapshots(data, required=False)
    checkout.mkdir(parents=True)
    git(checkout, "init", "--initial-branch", BRANCH)
    git(checkout, "remote", "add", "origin", remote)
    git(checkout, "config", "credential.helper", "!gh auth git-credential")
    git(checkout, "config", "user.name", "github-actions[bot]")
    git(checkout, "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git(checkout, "config", "commit.gpgsign", "false")
    git(checkout, "config", "core.hooksPath", "/dev/null")
    result = git(
        checkout, "ls-remote", "--exit-code", "origin", f"refs/heads/{BRANCH}", allowed=(0, 2)
    )
    if result.returncode == 2:
        return False
    git(checkout, "fetch", "--no-tags", "origin", f"refs/heads/{BRANCH}")
    git(checkout, "checkout", "-B", BRANCH, "FETCH_HEAD")
    tracked = git(checkout, "ls-files", "-z").stdout.split("\0")
    if any(name and not SNAPSHOT.fullmatch(name) for name in tracked):
        raise ValueError("Unexpected files on the report-data branch")
    paths = snapshots(checkout)
    # Validate the entire remote before replacing any local seed snapshots.
    for path in paths:
        destination = data / path
        if destination.is_symlink():
            raise ValueError("Snapshots must not be symbolic links")
    for path in paths:
        destination = data / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checkout / path, destination)
    return True


def save_history(data: Path, checkout: Path) -> bool:
    paths = snapshots(data)
    previous = snapshots(checkout, required=False)
    old_reports = {path for path in previous if path.suffix == ".json"}
    if not old_reports.issubset(paths):
        raise ValueError("Refusing to delete previous report history")
    for path in paths:
        destination = checkout / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(data / path, destination)
    git(checkout, "add", "--", *(str(path) for path in paths))
    if not git(checkout, "diff", "--cached", "--name-only").stdout.strip():
        return False
    git(checkout, "commit", "-m", f"chore(reports): update daily snapshots\n\n{COAUTHOR}")
    git(checkout, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("restore", "save"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--remote")
    args = parser.parse_args()
    if args.operation == "restore" and not args.remote:
        parser.error("restore requires --remote")
    try:
        if args.operation == "restore":
            restored = restore_history(args.remote, args.data_dir, args.checkout)
            print("History restored" if restored else "First run: using repository seed reports")
        else:
            changed = save_history(args.data_dir, args.checkout)
            print("History saved" if changed else "History unchanged")
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
