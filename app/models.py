from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Stage(str, Enum):
    UNIT = "unit"
    API = "api"
    UI = "ui"


class Status(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestCaseResult(BaseModel):
    name: str
    stage: Stage
    status: Status
    duration_ms: float = 0.0
    message: str = ""
    logs: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel):
    stage: Stage
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    cases: list[TestCaseResult] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)


class RootCause(BaseModel):
    test: str
    cause: str
    confidence: float = 0.0


class AIInsight(BaseModel):
    enabled: bool = True
    summary: str = ""
    root_causes: list[RootCause] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    generated_test_cases: list[str] = Field(default_factory=list)
    error: str | None = None


class UnifiedReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    project_path: str
    stages: dict[str, StageResult] = Field(default_factory=dict)
    ai: AIInsight = Field(default_factory=AIInsight)
    overall_status: Status = Status.PASSED
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_errors: int = 0
