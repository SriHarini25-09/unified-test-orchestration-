from __future__ import annotations

import json
from pathlib import Path

from .config import Settings
from .models import UnifiedReport


def save_report(report: UnifiedReport, settings: Settings) -> Path:
    """Persist a report as JSON and update the `latest.json` pointer."""
    payload = report.model_dump(mode="json")

    path = settings.report_dir / f"report_{report.id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    (settings.report_dir / "latest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return path


def list_reports(settings: Settings) -> list[Path]:
    """Return saved reports, newest first."""
    return sorted(
        settings.report_dir.glob("report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def load_report(path: Path) -> UnifiedReport:
    return UnifiedReport.model_validate_json(path.read_text(encoding="utf-8"))
