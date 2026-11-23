from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .ai.analyzer import generate_unit_tests
from .config import Settings
from .fallback import (
    check_source_syntax,
    find_embedded_configs,
    find_embedded_tests,
    generate_basic_unit_tests,
)
from .models import AIInsight, Stage, StageResult, Status, TestCaseResult, UnifiedReport
from .orchestrator import run_orchestration
from .reporting import list_reports, load_report

settings = Settings()
BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Unified Test Orchestration")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

latest_report: UnifiedReport | None = None
# Cloud Run only allows writes under /tmp.
USER_PROJECTS_DIR = (
    Path(tempfile.gettempdir()) / "user_projects"
    if os.getenv("K_SERVICE")
    else BASE_DIR / "user_projects"
)
USER_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


class CustomRunRequest(BaseModel):
    name: str = "My Project"
    source_code: str
    unit_tests: str = ""
    api_tests: str = ""
    ui_tests: str = ""
    api_base_url: str = ""
    ui_base_url: str = ""


def _error_stage(stage: Stage, name: str, message: str) -> StageResult:
    """Build a reportable stage failure instead of rejecting the whole request."""

    return StageResult(
        stage=stage,
        errors=1,
        cases=[
            TestCaseResult(
                name=name,
                stage=stage,
                status=Status.ERROR,
                message=message,
            )
        ],
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    saved = list_reports(settings)

    # No saved report is restored automatically. Before the first run we pass a
    # zero-filled report so every metric and stage panel is visible with 0s.
    has_report = latest_report is not None
    display_report = latest_report
    if not has_report:
        display_report = UnifiedReport(
            project_path="",
            stages={stage.value: StageResult(stage=stage) for stage in Stage},
            ai=AIInsight(
                enabled=False,
                summary="No analysis yet. Run a test to see AI failure analysis.",
            ),
            overall_status=Status.SKIPPED,
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "report": display_report,
            "has_report": has_report,
            "saved_reports": [p.name for p in saved[:10]],
        },
    )


@app.post("/api/run")
async def run_tests() -> JSONResponse:
    global latest_report
    latest_report = await run_orchestration(settings)
    return JSONResponse(latest_report.model_dump(mode="json"))


@app.post("/api/run-custom")
async def run_custom(payload: CustomRunRequest) -> JSONResponse:
    global latest_report

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", payload.name).strip("_") or "project"
    project_dir = USER_PROJECTS_DIR / f"{safe_name}_{uuid.uuid4().hex[:8]}"
    project_dir.mkdir(parents=True, exist_ok=True)

    source_code = payload.source_code
    (project_dir / "source.py").write_text(source_code, encoding="utf-8")

    source_check = check_source_syntax(source_code)
    overrides: dict[str, StageResult] = {}
    extra_unit_cases: list[TestCaseResult] = []
    embedded_tests: list[str] = []
    embedded_api_tests: list[dict] = []
    embedded_ui_tests: list[dict] = []
    embedded_api_base_url = ""
    embedded_ui_base_url = ""

    if source_check.status == Status.ERROR:
        overrides[Stage.UNIT.value] = _error_stage(
            Stage.UNIT,
            source_check.name,
            source_check.message or "Invalid source code.",
        )
        generation_mode = "fallback"
        (project_dir / "test_source.py").write_text("", encoding="utf-8")
    else:
        extra_unit_cases.append(source_check)
        embedded_tests = find_embedded_tests(source_code)
        (
            embedded_api_tests,
            embedded_ui_tests,
            embedded_api_base_url,
            embedded_ui_base_url,
        ) = find_embedded_configs(source_code)

        if embedded_tests:
            (project_dir / "test_source_self.py").write_text(
                source_code, encoding="utf-8"
            )

        # Tests embedded in the source always win over stale/separate fields.
        unit_tests = "" if embedded_tests else payload.unit_tests.strip()
        generation_mode = "source-self-tests" if embedded_tests else "manual"

        if not unit_tests and not embedded_tests:
            if settings.ai_enabled:
                try:
                    unit_tests = await generate_unit_tests(source_code, settings)
                    generation_mode = "ai"
                except Exception:  # noqa: BLE001
                    unit_tests = generate_basic_unit_tests(source_code)
                    generation_mode = "fallback"
            else:
                unit_tests = generate_basic_unit_tests(source_code)
                generation_mode = "fallback"

        (project_dir / "test_source.py").write_text(unit_tests, encoding="utf-8")

    for filename, content, stage in (
        ("api_tests.json", payload.api_tests, Stage.API),
        ("ui_tests.json", payload.ui_tests, Stage.UI),
    ):
        embedded = embedded_api_tests if stage == Stage.API else embedded_ui_tests
        parsed: list[dict] = []

        # Embedded API/UI configs take priority; separate JSON is only a fallback.
        if not embedded:
            try:
                parsed = json.loads(content) if content.strip() else []
                if not isinstance(parsed, list):
                    raise ValueError("must be a JSON list")
            except Exception as exc:  # noqa: BLE001
                overrides[stage.value] = _error_stage(
                    stage, f"{stage.value}-config", f"Invalid {filename}: {exc}"
                )
                parsed = []

        combined = embedded or parsed
        (project_dir / filename).write_text(
            json.dumps(combined, indent=2), encoding="utf-8"
        )

    custom_settings = copy.copy(settings)
    custom_settings.target_project_path = project_dir
    api_base = embedded_api_base_url or payload.api_base_url.strip()
    ui_base = embedded_ui_base_url or payload.ui_base_url.strip()
    if api_base:
        custom_settings.api_base_url = api_base.rstrip("/")
    if ui_base:
        custom_settings.ui_base_url = ui_base.rstrip("/")

    latest_report = await run_orchestration(
        custom_settings,
        stage_overrides=overrides,
        extra_unit_cases=extra_unit_cases,
    )
    body = latest_report.model_dump(mode="json")
    body["project_id"] = project_dir.name
    body["test_generation"] = generation_mode
    body["embedded_tests"] = embedded_tests
    body["embedded_api_tests"] = len(embedded_api_tests)
    body["embedded_ui_tests"] = len(embedded_ui_tests)
    return JSONResponse(body)


@app.post("/api/reset")
async def reset_dashboard() -> JSONResponse:
    """Clear the active report so the dashboard returns to its blank start state."""

    global latest_report
    latest_report = None
    return JSONResponse({"status": "reset"})


@app.get("/api/reports")
async def reports() -> JSONResponse:
    return JSONResponse([p.name for p in list_reports(settings)])


@app.get("/api/reports/{filename}")
async def report_detail(filename: str) -> JSONResponse:
    safe_name = Path(filename).name
    path = settings.report_dir / safe_name
    if not path.exists():
        return JSONResponse({"error": "report not found"}, status_code=404)
    return JSONResponse(load_report(path).model_dump(mode="json"))
