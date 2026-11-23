from __future__ import annotations

import json

from openai import AsyncOpenAI

from ..config import Settings
from ..fallback import analyze_fallback
from ..models import AIInsight, RootCause, UnifiedReport

SYSTEM_PROMPT = """You are an expert QA engineer and debugging assistant.
You receive a unified test report containing unit, API and UI test results.

Your job:
1. Summarise overall quality in 2-3 sentences.
2. For every failed or errored test, infer the most likely root cause.
3. Give concrete fix suggestions.
4. Suggest additional test cases that would prevent similar regressions.

Respond with ONLY a JSON object using this exact shape:
{
  "summary": "string",
  "root_causes": [
    {"test": "test name", "cause": "likely cause", "confidence": 0.0-1.0}
  ],
  "fix_suggestions": ["string"],
  "generated_test_cases": ["string"]
}
Do not include markdown or any text outside the JSON object."""


async def analyze(report: UnifiedReport, settings: Settings) -> AIInsight:
    """Send failing test context to OpenAI and return structured insights."""
    if not settings.ai_enabled:
        return analyze_fallback(report)

    problematic = []
    for stage in report.stages.values():
        for case in stage.cases:
            if case.status in ("failed", "error"):
                problematic.append(
                    {
                        "stage": case.stage.value,
                        "test": case.name,
                        "status": case.status.value,
                        "message": case.message,
                        "logs": case.logs[:1500],
                    }
                )

    user_payload = {
        "project_path": report.project_path,
        "overall_status": report.overall_status.value,
        "totals": {
            "tests": report.total_tests,
            "passed": report.total_passed,
            "failed": report.total_failed,
            "skipped": report.total_skipped,
            "errors": report.total_errors,
        },
        "problematic_tests": problematic,
    }

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, indent=2),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)

        return AIInsight(
            enabled=True,
            summary=str(data.get("summary", "")),
            root_causes=[
                RootCause(
                    test=str(rc.get("test", "")),
                    cause=str(rc.get("cause", "")),
                    confidence=_safe_float(rc.get("confidence", 0.0)),
                )
                for rc in data.get("root_causes", [])
                if isinstance(rc, dict)
            ],
            fix_suggestions=[str(item) for item in data.get("fix_suggestions", [])],
            generated_test_cases=[
                str(item) for item in data.get("generated_test_cases", [])
            ],
        )
    except Exception as exc:  # noqa: BLE001
        return analyze_fallback(report, error=f"OpenAI analysis failed: {exc}")


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def generate_unit_tests(source_code: str, settings: Settings) -> str:
    """Ask OpenAI to write a pytest module for the submitted source code.

    The submitted source is saved as `source.py` in the generated project,
    so the generated tests must import from that module.
    """
    if not settings.ai_enabled:
        raise ValueError(
            "OPENAI_API_KEY is required to generate test cases from source code."
        )

    prompt = f"""You are an expert Python test engineer.

The following Python source code will be saved as a file named `source.py`.
Write a complete pytest test module that tests all public functions and important
edge cases in this source.

Rules:
- Import from `source`, for example: `from source import add`
- Use only `pytest` and the Python standard library.
- Do not call network or external services.
- Return ONLY valid Python code.
- Do not wrap the code in markdown fences.

SOURCE CODE:
{source_code}
"""

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "You generate clean pytest test files."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    code = (response.choices[0].message.content or "").strip()
    if code.startswith("```"):
        lines = code.splitlines()
        lines = lines[1:] if lines and lines[0].strip().startswith("```") else lines
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code
