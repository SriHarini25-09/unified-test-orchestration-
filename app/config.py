from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime settings loaded from environment variables / .env file."""

    def __init__(self) -> None:
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        self.target_project_path: Path = Path(
            os.getenv("TARGET_PROJECT_PATH", "sample_project")
        ).resolve()

        self.api_base_url: str = os.getenv(
            "API_BASE_URL", "http://127.0.0.1:8001"
        ).rstrip("/")
        self.ui_base_url: str = os.getenv(
            "UI_BASE_URL", "http://127.0.0.1:8001"
        ).rstrip("/")

        # Cloud Run has a read-only filesystem except /tmp.
        runtime_root = (
            Path(tempfile.gettempdir())
            if os.getenv("K_SERVICE")
            else Path.cwd()
        )
        self.report_dir: Path = runtime_root / os.getenv("REPORT_DIR", "reports")
        self.pytest_timeout: int = int(os.getenv("PYTEST_TIMEOUT", "120"))

        self.report_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)
