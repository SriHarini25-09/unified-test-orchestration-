from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..models import Stage, StageResult, Status, TestCaseResult


async def run_ui_tests(project_path: Path, base_url: str) -> StageResult:
    """Execute declarative browser tests from `ui_tests.json` using Playwright."""
    started = time.perf_counter()
    config_file = project_path / "ui_tests.json"

    if not config_file.exists():
        return StageResult(
            stage=Stage.UI,
            skipped=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="ui-suite",
                    stage=Stage.UI,
                    status=Status.SKIPPED,
                    message="ui_tests.json not found",
                )
            ],
        )

    try:
        tests: list[dict[str, Any]] = json.loads(
            config_file.read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001
        return StageResult(
            stage=Stage.UI,
            errors=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="ui-config",
                    stage=Stage.UI,
                    status=Status.ERROR,
                    message=f"Invalid ui_tests.json: {exc}",
                )
            ],
        )

    if not tests:
        return StageResult(
            stage=Stage.UI,
            skipped=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="ui-suite",
                    stage=Stage.UI,
                    status=Status.SKIPPED,
                    message="No UI tests defined",
                )
            ],
        )

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return StageResult(
            stage=Stage.UI,
            errors=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="ui-playwright",
                    stage=Stage.UI,
                    status=Status.ERROR,
                    message="playwright is not installed (pip install playwright)",
                )
            ],
        )

    cases: list[TestCaseResult] = []

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()

            for test in tests:
                case_started = time.perf_counter()
                name = test.get("name", "ui-test")
                try:
                    await page.goto(
                        base_url + test["path"], wait_until="domcontentloaded"
                    )

                    selector = test.get("selector")
                    if selector:
                        await page.wait_for_selector(
                            selector, timeout=int(test.get("timeout_ms", 5000))
                        )

                    expected_text = test.get("expected_text")
                    if expected_text:
                        target = selector or "body"
                        text = await page.text_content(target)
                        if expected_text not in (text or ""):
                            raise AssertionError(
                                f"expected text {expected_text!r} not found in {target!r}"
                            )

                    cases.append(
                        TestCaseResult(
                            name=name,
                            stage=Stage.UI,
                            status=Status.PASSED,
                            duration_ms=(time.perf_counter() - case_started) * 1000,
                            logs=(await page.content())[:1000],
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    cases.append(
                        TestCaseResult(
                            name=name,
                            stage=Stage.UI,
                            status=Status.FAILED,
                            duration_ms=(time.perf_counter() - case_started) * 1000,
                            message=str(exc),
                        )
                    )

            await browser.close()
    except Exception as exc:  # noqa: BLE001
        cases.append(
            TestCaseResult(
                name="ui-browser",
                stage=Stage.UI,
                status=Status.ERROR,
                message=f"Could not launch browser: {exc}. "
                "Run: playwright install chromium",
            )
        )

    result = StageResult(
        stage=Stage.UI,
        cases=cases,
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    _count(result)
    return result


def _count(result: StageResult) -> None:
    for case in result.cases:
        if case.status == Status.PASSED:
            result.passed += 1
        elif case.status == Status.FAILED:
            result.failed += 1
        elif case.status == Status.SKIPPED:
            result.skipped += 1
        else:
            result.errors += 1
