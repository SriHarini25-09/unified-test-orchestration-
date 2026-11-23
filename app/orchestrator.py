from __future__ import annotations

from pathlib import Path

from .ai.analyzer import analyze
from .config import Settings
from .models import StageResult, Status, TestCaseResult, UnifiedReport
from .reporting import save_report
from .runners.api_runner import run_api_tests
from .runners.ui_runner import run_ui_tests
from .runners.unit_runner import run_unit_tests


async def run_orchestration(
    settings: Settings,
    *,
    project_path: Path | None = None,
    api_base_url: str | None = None,
    ui_base_url: str | None = None,
    stage_overrides: dict[str, StageResult] | None = None,
    extra_unit_cases: list[TestCaseResult] | None = None,
) -> UnifiedReport:
    """Run all test stages, merge results, then request AI failure analysis.

    Optional overrides let the dashboard test a user-submitted project without
    changing global settings. Overrides are used when a stage cannot run at all
    (for example, invalid JSON config) so the failure still appears in the report.
    """
    target = project_path or settings.target_project_path
    api_url = api_base_url or settings.api_base_url
    ui_url = ui_base_url or settings.ui_base_url

    unit, api, ui = await _run_stages(
        target, api_url, ui_url, settings.pytest_timeout, stage_overrides
    )

    for case in extra_unit_cases or []:
        unit.cases.insert(0, case)
        if case.status == Status.PASSED:
            unit.passed += 1
        elif case.status == Status.FAILED:
            unit.failed += 1
        elif case.status == Status.SKIPPED:
            unit.skipped += 1
        else:
            unit.errors += 1

    stages: dict[str, StageResult] = {
        unit.stage.value: unit,
        api.stage.value: api,
        ui.stage.value: ui,
    }

    report = UnifiedReport(
        project_path=str(target),
        stages=stages,
    )
    refresh_report_totals(report)

    report.ai = await analyze(report, settings)
    save_report(report, settings)
    return report


def refresh_report_totals(report: UnifiedReport) -> None:
    """Recalculate all summary counters from the stored test cases."""

    all_cases = [case for stage in report.stages.values() for case in stage.cases]
    report.total_tests = len(all_cases)
    report.total_passed = sum(1 for c in all_cases if c.status == Status.PASSED)
    report.total_failed = sum(1 for c in all_cases if c.status == Status.FAILED)
    report.total_skipped = sum(1 for c in all_cases if c.status == Status.SKIPPED)
    report.total_errors = sum(1 for c in all_cases if c.status == Status.ERROR)

    if report.total_failed or report.total_errors:
        report.overall_status = Status.FAILED
    elif report.total_passed:
        report.overall_status = Status.PASSED
    else:
        report.overall_status = Status.SKIPPED


async def _run_stages(
    target: Path,
    api_url: str,
    ui_url: str,
    timeout: int,
    overrides: dict[str, StageResult] | None = None,
):
    import asyncio

    chosen = overrides or {}

    async def resolve(name: str, runner, *args):
        if name in chosen:
            return chosen[name]
        return await runner(*args)

    return await asyncio.gather(
        resolve("unit", run_unit_tests, target, timeout),
        resolve("api", run_api_tests, target, api_url),
        resolve("ui", run_ui_tests, target, ui_url),
    )
