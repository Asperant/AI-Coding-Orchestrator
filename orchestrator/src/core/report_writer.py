from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNSAFE_FILENAME_CHARS = re.compile(r"[^a-z0-9._-]+")


class ReportWriterError(RuntimeError):
    """Raised when a report cannot be written safely."""


def _app_reports_root() -> Path:
    return (PROJECT_ROOT / "reports").resolve()


def sanitize_report_name(report_name: str) -> str:
    sanitized_name = UNSAFE_FILENAME_CHARS.sub("-", report_name.strip().lower()).strip("._-")
    if not sanitized_name:
        raise ReportWriterError("Report type/name is empty after sanitization.")

    return sanitized_name


def resolve_reports_dir(reports_dir: str | Path) -> Path:
    raw_reports_dir = Path(reports_dir).expanduser()
    if raw_reports_dir.is_absolute():
        resolved_reports_dir = raw_reports_dir.resolve()
    else:
        resolved_reports_dir = (PROJECT_ROOT / raw_reports_dir).resolve()

    try:
        resolved_reports_dir.relative_to(_app_reports_root())
    except ValueError as exc:
        raise ReportWriterError(
            f"Reports directory must stay inside the app reports directory: {resolved_reports_dir}"
        ) from exc

    return resolved_reports_dir


def write_report(
    report_text: str,
    report_name: str,
    reports_dir: str | Path,
    timestamp: datetime | None = None,
) -> Path:
    reports_root = resolve_reports_dir(reports_dir)
    reports_root.mkdir(parents=True, exist_ok=True)

    safe_report_name = sanitize_report_name(report_name)
    report_timestamp = timestamp or datetime.now(timezone.utc)
    timestamp_text = report_timestamp.strftime("%Y%m%d-%H%M%S")
    report_path = (reports_root / f"{timestamp_text}-{safe_report_name}.md").resolve()

    try:
        report_path.relative_to(reports_root)
    except ValueError as exc:
        raise ReportWriterError(f"Report path escapes reports directory: {report_path}") from exc

    report_path.write_text(report_text, encoding="utf-8")
    return report_path
