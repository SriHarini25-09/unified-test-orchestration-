# AI-Powered Unified Test Orchestrator

A single controller that runs **unit**, **API**, and **UI** tests, merges their results into one report, and uses **OpenAI** to analyse failures, suggest root causes, propose fixes, and recommend new test cases. A lightweight FastAPI dashboard displays everything in one place.

---

## 1. Project structure

```
ai-test-orchestrator/
├── app/
│   ├── ai/analyzer.py          # OpenAI failure analysis
│   ├── runners/
│   │   ├── unit_runner.py      # pytest + JUnit XML parsing
│   │   ├── api_runner.py       # httpx declarative API tests
│   │   └── ui_runner.py        # Playwright browser tests
│   ├── config.py               # environment settings
│   ├── models.py               # Pydantic data models
│   ├── orchestrator.py         # coordinates all stages
│   ├── reporting.py            # JSON report persistence
│   └── main.py                 # FastAPI app + REST API
├── sample_project/             # demo project under test
│   ├── calc.py
│   ├── test_calc.py
│   ├── api_tests.json
│   └── ui_tests.json
├── templates/dashboard.html
├── static/style.css
├── demo_target.py              # small app the API/UI tests hit
├── run_orchestrator.py
├── requirements.txt
└── .env.example
```

---

## 2. Setup

```powershell
cd ai-test-orchestrator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Copy `.env.example` to `.env` and add your key:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
OPENAI_API_KEY=sk-your-real-key-here
OPENAI_MODEL=gpt-4o-mini
```

> AI analysis is **OpenAI-only**. Without a key, the system uses a local fallback: it generates basic pytest smoke tests from your source with `ast` and produces rule-based failure suggestions.

---

## 3. Run the demo

### Terminal 1 — start the target app

```powershell
python demo_target.py
```

It listens on `http://127.0.0.1:8001`.

### Terminal 2 — start the orchestrator

```powershell
python run_orchestrator.py
```

Open **http://127.0.0.1:8000** and click **Run all tests**.

---

## 4. What you will see

- Unit tests run through `pytest`.
- API tests from `sample_project/api_tests.json` run through `httpx`.
- UI tests from `sample_project/ui_tests.json` run through Playwright Chromium.
- Results are merged into a single `UnifiedReport`.
- OpenAI receives the failing tests and returns:
  - quality summary
  - likely root causes with confidence
  - fix suggestions
  - suggested new test cases
- Reports are saved under `reports/` as JSON.

### Intentional demo failure

`sample_project/calc.py` contains a deliberate bug in `add()`:

```python
return a - b   # should be a + b
```

This makes `test_add` fail so the AI analysis has something to investigate. Fix it to turn the suite green.

---

## 5. REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | HTML dashboard |
| `POST` | `/api/run` | Run all stages and return the unified report |
| `GET` | `/api/reports` | List saved report filenames |
| `GET` | `/api/reports/{filename}` | Fetch one saved report as JSON |

Example:

```powershell
curl -X POST http://127.0.0.1:8000/api/run
```

---

## 6. Testing your own source from the website

The dashboard now includes a **Test Your Own Source** form:

1. Paste your Python source code.
2. Optionally paste your own pytest unit tests.
   - If left blank, OpenAI generates the pytest cases automatically.
3. Optionally paste `api_tests.json` and `ui_tests.json` content.
4. Set the API/UI base URLs you want to test against.
5. Click **Run custom tests**.

The submission is saved under `user_projects/<name>_<id>/` and the same orchestration pipeline runs on it. The resulting report appears in the dashboard and in `reports/`.

> Only run code you trust. The orchestrator executes submitted Python source locally.

---

## 7. Using your own project

1. Put or point `TARGET_PROJECT_PATH` at your test project.
2. Add `api_tests.json` and `ui_tests.json` in that folder if you want those stages.
3. Adjust `API_BASE_URL` and `UI_BASE_URL` in `.env`.
4. Unit tests are discovered automatically by `pytest`.

---

## 8. Deploy to Google Cloud Run

The project includes a `Dockerfile` and `cloud_start.py`, which starts the demo
target on port 8001 and serves the dashboard on Cloud Run's `$PORT`.

```powershell
# One-time authentication (opens a browser)
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy (builds the container with Cloud Build and prints the public URL)
.\deploy_google_cloud.ps1
```

The deployment script enables Run, Cloud Build, and Artifact Registry APIs,
then deploys a public, unauthenticated Cloud Run service named
`unified-test-orchestration`. Billing must be enabled on the project.

At runtime, generated projects and reports are written under `/tmp` because
Cloud Run containers have a read-only filesystem elsewhere.
