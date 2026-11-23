"""Container entrypoint for Google Cloud Run.

Starts the demo target app on 8001 (used by the sample API/UI tests) and then
serves the orchestrator on the port Cloud Run provides via the PORT variable.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import uvicorn

from app.main import app

PORT = int(os.getenv("PORT", "8000"))

# The built-in sample API/UI tests call http://127.0.0.1:8001.
demo = subprocess.Popen(
    [sys.executable, "demo_target.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

# Give the demo target a moment to bind its port.
time.sleep(1)

try:
    uvicorn.run(app, host="0.0.0.0", port=PORT)
finally:
    demo.terminate()
    try:
        demo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        demo.kill()
