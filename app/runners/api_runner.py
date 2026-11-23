from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from ..models import Stage, StageResult, Status, TestCaseResult


async def run_api_tests(
    project_path: Path, base_url: str, timeout: float = 10.0
) -> StageResult:
    """Execute declarative HTTP tests from `api_tests.json`."""
    started = time.perf_counter()
    config_file = project_path / "api_tests.json"

    if not config_file.exists():
        return StageResult(
            stage=Stage.API,
            skipped=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="api-suite",
                    stage=Stage.API,
                    status=Status.SKIPPED,
                    message="api_tests.json not found",
                )
            ],
        )

    try:
        tests: list[dict[str, Any]] = json.loads(
            config_file.read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001
        return StageResult(
            stage=Stage.API,
            errors=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="api-config",
                    stage=Stage.API,
                    status=Status.ERROR,
                    message=f"Invalid api_tests.json: {exc}",
                )
            ],
        )

    if not tests:
        return StageResult(
            stage=Stage.API,
            skipped=1,
            duration_ms=(time.perf_counter() - started) * 1000,
            cases=[
                TestCaseResult(
                    name="api-suite",
                    stage=Stage.API,
                    status=Status.SKIPPED,
                    message="No API tests defined",
                )
            ],
        )

    cases: list[TestCaseResult] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        for test in tests:
            case_started = time.perf_counter()
            name = test.get("name", "api-test")
            try:
                method = test.get("method", "GET").upper()
                response = await client.request(
                    method,
                    test["path"],
                    json=test.get("json"),
                    headers=test.get("headers"),
                )
                expected = int(test.get("expected_status", 200))
                ok = response.status_code == expected
                message = "" if ok else (
                    f"expected status {expected}, got {response.status_code}"
                )

                subset = test.get("expected_json_subset")
                if ok and subset:
                    body = response.json()
                    ok = _matches_subset(body, subset)
                    if not ok:
                        message = f"response JSON did not match subset {subset}"

                cases.append(
                    TestCaseResult(
                        name=name,
                        stage=Stage.API,
                        status=Status.PASSED if ok else Status.FAILED,
                        duration_ms=(time.perf_counter() - case_started) * 1000,
                        message=message,
                        logs=response.text[:2000],
                        metadata={
                            "status_code": response.status_code,
                            "url": str(response.url),
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                cases.append(
                    TestCaseResult(
                        name=name,
                        stage=Stage.API,
                        status=Status.ERROR,
                        duration_ms=(time.perf_counter() - case_started) * 1000,
                        message=str(exc),
                    )
                )

    result = StageResult(
        stage=Stage.API,
        cases=cases,
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    _count(result)
    return result


def _matches_subset(body: Any, subset: dict[str, Any]) -> bool:
    if not isinstance(body, dict):
        return False
    for key, value in subset.items():
        if key not in body or body[key] != value:
            return False
    return True


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
