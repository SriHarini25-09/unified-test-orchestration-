from __future__ import annotations

import ast
import json

from .models import AIInsight, RootCause, Stage, Status, TestCaseResult, UnifiedReport


def generate_basic_unit_tests(source_code: str) -> str:
    """Generate simple pytest smoke tests without any external service.

    This is used when the user does not paste unit tests and no OpenAI key is
    available. It checks that the module imports and that public functions and
    classes exist, but it does not verify business logic.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return (
            "def test_source_syntax():\n"
            f"    raise AssertionError({str(exc)!r})\n"
        )

    functions: list[str] = []
    classes: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                classes.append(node.name)

    lines = [
        "import source",
        "",
        "",
        "def test_module_imports():",
        "    assert source is not None",
        "",
    ]

    if functions:
        lines.append("def test_public_functions_exist():")
        for name in functions:
            lines.append(f"    assert callable(getattr(source, {name!r}))")
        lines.append("")

    if classes:
        lines.append("def test_public_classes_exist():")
        for name in classes:
            lines.append(f"    assert isinstance(getattr(source, {name!r}), type)")
        lines.append("")

    if not functions and not classes:
        lines.extend(
            [
                "def test_source_has_public_members():",
                "    public = [n for n in dir(source) if not n.startswith('_')]",
                "    assert public, 'no public functions or classes found'",
                "",
            ]
        )

    return "\n".join(lines)


def check_source_syntax(source_code: str) -> TestCaseResult:
    """Validate the submitted Python source without needing an AI provider."""

    if not source_code.strip():
        return TestCaseResult(
            name="python-source",
            stage=Stage.UNIT,
            status=Status.ERROR,
            message="Source code is empty. Paste Python code or leave every field blank to run the no-AI fallback checks.",
        )

    try:
        ast.parse(source_code)
    except SyntaxError as exc:
        return TestCaseResult(
            name="python-syntax",
            stage=Stage.UNIT,
            status=Status.ERROR,
            message=f"SyntaxError: {exc.msg} (line {exc.lineno})",
            logs=source_code[:1000],
        )

    return TestCaseResult(
        name="python-syntax",
        stage=Stage.UNIT,
        status=Status.PASSED,
        message="Valid Python syntax.",
    )


def find_embedded_tests(source_code: str) -> list[str]:
    """Find pytest-style tests declared inside the submitted source file."""

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    found: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                found.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name.startswith("test"):
                        found.append(f"{node.name}::{child.name}")

    for node in tree.body:
        if isinstance(node, ast.Assert):
            found.append("module-assert")
            break

    return found


def find_embedded_configs(
    source_code: str,
) -> tuple[list[dict], list[dict], str, str]:
    """Read API/UI tests and base URLs declared inside the submitted source."""

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return [], [], "", ""

    api_tests: list[dict] = []
    ui_tests: list[dict] = []
    api_base_url = ""
    ui_base_url = ""
    names = {
        "API_TESTS",
        "API_TESTS_JSON",
        "UI_TESTS",
        "UI_TESTS_JSON",
        "API_BASE_URL",
        "UI_BASE_URL",
    }

    for node in tree.body:
        target_name: str | None = None
        value: ast.expr | None = None

        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target_name = node.targets[0].id
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            target_name = node.target.id
            value = node.value

        if target_name not in names or value is None:
            continue

        try:
            parsed = ast.literal_eval(value)
        except Exception:  # noqa: BLE001
            continue

        if target_name in ("API_BASE_URL", "UI_BASE_URL"):
            if isinstance(parsed, str):
                cleaned = parsed.strip().rstrip("/")
                if target_name == "API_BASE_URL":
                    api_base_url = cleaned
                else:
                    ui_base_url = cleaned
            continue

        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:  # noqa: BLE001
                continue

        if not isinstance(parsed, list) or not all(
            isinstance(item, dict) for item in parsed
        ):
            continue

        if target_name.startswith("API_"):
            api_tests.extend(parsed)
        else:
            ui_tests.extend(parsed)

    return api_tests, ui_tests, api_base_url, ui_base_url


def analyze_fallback(
    report: UnifiedReport, *, error: str | None = None
) -> AIInsight:
    """Rule-based failure analysis used when OpenAI is not configured."""
    problematic = [
        case
        for stage in report.stages.values()
        for case in stage.cases
        if case.status in ("failed", "error")
    ]

    if not problematic:
        return AIInsight(
            enabled=False,
            summary="All executed tests passed. No failure analysis needed.",
            root_causes=[],
            fix_suggestions=[],
            generated_test_cases=[],
            error=error or "Rule-based mode (no OPENAI_API_KEY configured).",
        )

    root_causes: list[RootCause] = []
    fixes: list[str] = []
    generated: list[str] = []

    for case in problematic:
        message = case.message or ""
        logs = case.logs or ""
        first_line = message.splitlines()[0] if message else "no error message"

        if "assert" in message.lower() or "==" in message:
            cause = f"Assertion mismatch: {first_line}"
            fix = (
                f"Check the implementation used by {case.name}. "
                "The actual value did not match the expected value."
            )
            suggestion = (
                f"Add an explicit expected-value test for {case.name}, "
                "including a boundary case."
            )
        elif (
            "ImportError" in logs
            or "ModuleNotFoundError" in logs
            or "No module named" in message
        ):
            cause = "Missing import or module dependency"
            fix = "Install the missing package or correct the import path in source.py."
            suggestion = "Add an import smoke test to catch missing dependencies early."
        elif case.status == "error" or "Traceback" in logs:
            cause = f"Runtime error: {first_line[:120]}"
            fix = "Inspect the traceback in the logs and fix the runtime exception."
            suggestion = f"Add a regression test that reproduces the error in {case.name}."
        else:
            cause = f"Unexpected result: {first_line[:120]}"
            fix = f"Review the failing test and the logic used by {case.name}."
            suggestion = f"Add a test covering the scenario in {case.name}."

        root_causes.append(RootCause(test=case.name, cause=cause, confidence=0.6))
        fixes.append(fix)
        generated.append(suggestion)

    return AIInsight(
        enabled=False,
        summary=(
            f"{len(problematic)} test(s) failed. "
            "Rule-based analysis was used because no OpenAI key is configured."
        ),
        root_causes=root_causes,
        fix_suggestions=fixes,
        generated_test_cases=generated,
        error=error or "Rule-based mode (no OPENAI_API_KEY configured).",
    )
