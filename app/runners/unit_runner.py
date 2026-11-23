from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from ..models import Stage, StageResult, Status, TestCaseResult


async def run_unit_tests(project_path: Path, timeout: int = 120) -> StageResult:
    """Run pytest in the target project and parse its built-in JUnit XML report."""
    started = time.perf_counter()

    fd, xml_path = tempfile.mkstemp(prefix="orchestrator-pytest-", suffix=".xml")
    os.close(fd)

    try:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={xml_path}",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return StageResult(
                stage=Stage.UNIT,
                errors=1,
                duration_ms=(time.perf_counter() - started) * 1000,
                cases=[
                    TestCaseResult(
                        name="pytest-timeout",
                        stage=Stage.UNIT,
                        status=Status.ERROR,
                        message=f"pytest exceeded {timeout}s timeout",
                    )
                ],
            )

        logs = (
            stdout.decode(errors="replace") + "\n" + stderr.decode(errors="replace")
        ).strip()
        cases = _parse_junit(Path(xml_path))

        result = StageResult(
            stage=Stage.UNIT,
            cases=cases,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

        for case in cases:
            if case.status == Status.PASSED:
                result.passed += 1
            elif case.status == Status.FAILED:
                result.failed += 1
            elif case.status == Status.SKIPPED:
                result.skipped += 1
            else:
                result.errors += 1

        if not cases and proc.returncode not in (0, 5):
            result.errors += 1
            result.cases.append(
                TestCaseResult(
                    name="pytest-execution",
                    stage=Stage.UNIT,
                    status=Status.ERROR,
                    message=f"pytest exited with code {proc.returncode}",
                    logs=logs,
                )
            )

        return result
    finally:
        Path(xml_path).unlink(missing_ok=True)


def _parse_junit(path: Path) -> list[TestCaseResult]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    cases: list[TestCaseResult] = []
    root = ET.parse(path).getroot()

    for suite in root.iter("testsuite"):
        for tc in suite.findall("testcase"):
            name = tc.get("name", "test")
            classname = tc.get("classname", "")
            full_name = f"{classname}::{name}" if classname else name

            failure = tc.find("failure")
            error = tc.find("error")
            skipped = tc.find("skipped")

            if failure is not None:
                status = Status.FAILED
                message = failure.get("message", "")
                logs = failure.text or ""
            elif error is not None:
                status = Status.ERROR
                message = error.get("message", "")
                logs = error.text or ""
            elif skipped is not None:
                status = Status.SKIPPED
                message = skipped.get("message", "")
                logs = ""
            else:
                status = Status.PASSED
                message = ""
                logs = ""

            try:
                duration_ms = float(tc.get("time", "0") or 0) * 1000
            except ValueError:
                duration_ms = 0.0

            cases.append(
                TestCaseResult(
                    name=full_name,
                    stage=Stage.UNIT,
                    status=status,
                    duration_ms=duration_ms,
                    message=message,
                    logs=logs[:4000],
                    metadata={"file": tc.get("file", ""), "line": tc.get("line", "")},
                )
            )

    return cases
