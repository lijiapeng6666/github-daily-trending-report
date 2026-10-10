"""Stage the full site and preserve snapshots across repeated local runs."""

import fcntl
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import Report
from .render import render_site


@contextmanager
def writer_lock(data_dir: Path) -> Iterator[None]:
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / ".generate.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("另一个日报任务正在运行，请稍后重试") from error
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def load_reports(data_dir: Path) -> list[Report]:
    reports = []
    for path in sorted((data_dir / "reports").glob("*.json")):
        report = Report.model_validate_json(path.read_text(encoding="utf-8"))
        if path.stem != str(report.report_date):
            raise ValueError(f"日报文件名与日期不一致：{path.name}")
        reports.append(report)
    return reports


def replace_site(staged: Path, output: Path) -> None:
    backup = staged.parent / "previous-site"
    if output.exists():
        output.rename(backup)
    try:
        staged.rename(output)
    except OSError:
        if backup.exists():
            backup.rename(output)
        raise


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".radar-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def publish(
    report: Report | None,
    source_html: str | None,
    data_dir: Path,
    output: Path,
    ai_first: bool = True,
) -> None:
    data_dir, output = data_dir.resolve(), output.resolve()
    if output == data_dir or output in data_dir.parents or data_dir in output.parents:
        raise ValueError("日报输出目录不能与数据目录重叠")
    if output.exists() and not (output / ".github-radar-site").exists():
        raise ValueError("输出目录已存在且不是 Radar 生成目录，请使用空目录")
    reports = {str(item.report_date): item for item in load_reports(data_dir)}
    if report is not None:
        reports[str(report.report_date)] = report
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".radar-build-", dir=output.parent) as work:
        staged = Path(work) / "site"
        render_site(list(reports.values()), staged, ai_first)
        (staged / ".github-radar-site").touch()
        # Render first: parse or template errors cannot alter the last successful report.
        previous_files: dict[Path, str | None] = {}
        try:
            if report is not None:
                writes = {
                    data_dir / "reports" / f"{report.report_date}.json": report.model_dump_json(
                        indent=2
                    )
                }
                if source_html is not None:
                    writes[data_dir / "sources" / f"{report.report_date}.html"] = source_html
                for path, content in writes.items():
                    previous_files[path] = (
                        path.read_text(encoding="utf-8") if path.exists() else None
                    )
                    atomic_write(path, content)
            replace_site(staged, output)
        except Exception:
            for path, content in previous_files.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, content)
            raise
