"""
Complete self-contained test program for the Unified Test Orchestration website.

Paste this ENTIRE file into the Source Code box and leave the other three tabs empty.
It drives all three stages by itself:
  - UNIT  : test_* functions below (plus the Python syntax check)
  - API   : API_TESTS list
  - UI    : UI_TESTS list (checks all 5 dashboard pages)
The API_BASE_URL / UI_BASE_URL constants set the target, so no other field is needed.
"""

API_BASE_URL = "https://harder-compute-tattoo-immigration.trycloudflare.com"
UI_BASE_URL = "https://harder-compute-tattoo-immigration.trycloudflare.com"


# ---------------------------------------------------------------------------
# Application helper under test (mirrors the dashboard Test Summary logic)
# ---------------------------------------------------------------------------

class SummaryMetrics:
    """Computes the six Test Summary rows from stage results."""

    def __init__(self, passed=0, failed=0, errors=0, skipped=0):
        self.passed = passed
        self.failed = failed
        self.errors = errors
        self.skipped = skipped

    @property
    def total(self):
        return self.passed + self.failed + self.errors + self.skipped

    @property
    def overall_status(self):
        if self.errors or self.failed:
            return "FAILED"
        if self.total == 0:
            return "SKIPPED"
        return "PASSED"

    @property
    def pass_rate(self):
        if self.total == 0:
            return 0
        return round(self.passed * 100 / self.total)

    def as_summary_rows(self):
        return {
            "Overall": self.overall_status,
            "Total Test": self.total,
            "Pass": self.passed,
            "Failed": self.failed,
            "Error": self.errors,
            "Skipped": self.skipped,
        }


# ---------------------------------------------------------------------------
# UNIT TESTS
# ---------------------------------------------------------------------------

def test_summary_empty_is_skipped():
    metrics = SummaryMetrics()
    assert metrics.total == 0
    assert metrics.overall_status == "SKIPPED"
    assert metrics.pass_rate == 0


def test_summary_all_passed():
    metrics = SummaryMetrics(passed=9)
    rows = metrics.as_summary_rows()
    assert rows["Overall"] == "PASSED"
    assert rows["Total Test"] == 9
    assert rows["Pass"] == 9
    assert rows["Failed"] == 0
    assert rows["Error"] == 0
    assert rows["Skipped"] == 0


def test_summary_failed_assertion_marks_failed():
    metrics = SummaryMetrics(passed=4, failed=1)
    assert metrics.overall_status == "FAILED"
    assert metrics.as_summary_rows()["Failed"] == 1


def test_summary_error_marks_failed():
    metrics = SummaryMetrics(passed=3, errors=1, skipped=1)
    assert metrics.overall_status == "FAILED"
    assert metrics.as_summary_rows()["Error"] == 1


def test_summary_total_counts_every_category():
    metrics = SummaryMetrics(passed=2, failed=1, errors=1, skipped=2)
    assert metrics.total == 6
    assert metrics.as_summary_rows() == {
        "Overall": "FAILED",
        "Total Test": 6,
        "Pass": 2,
        "Failed": 1,
        "Error": 1,
        "Skipped": 2,
    }


def test_summary_pass_rate_rounding():
    assert SummaryMetrics(passed=2, failed=1).pass_rate == 67
    assert SummaryMetrics(passed=3, failed=0).pass_rate == 100


# ---------------------------------------------------------------------------
# API TESTS (dashboard endpoints)
# ---------------------------------------------------------------------------

API_TESTS = [
    {
        "name": "api: dashboard home returns 200",
        "method": "GET",
        "path": "/",
        "expected_status": 200,
    },
    {
        "name": "api: stylesheet loads",
        "method": "GET",
        "path": "/static/style.css",
        "expected_status": 200,
    },
    {
        "name": "api: unit icon loads",
        "method": "GET",
        "path": "/static/images/unit-icon.svg",
        "expected_status": 200,
    },
    {
        "name": "api: reports endpoint returns 200",
        "method": "GET",
        "path": "/api/reports",
        "expected_status": 200,
    },
    {
        "name": "api: missing page returns 404",
        "method": "GET",
        "path": "/this-page-does-not-exist",
        "expected_status": 404,
    },
]


# ---------------------------------------------------------------------------
# UI TESTS (all 5 dashboard pages, reached through their hash routes)
# ---------------------------------------------------------------------------

UI_TESTS = [
    {
        "name": "ui page 1: Start heading visible",
        "path": "/?page=1#intro",
        "selector": ".hero h2",
        "expected_text": "Start Your Test Run",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 1: stepper navigation visible",
        "path": "/?page=1#intro",
        "selector": ".stepper",
        "expected_text": "Start",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 2: Test Input form visible",
        "path": "/?page=2#input",
        "selector": "#customForm",
        "expected_text": "Run Custom Test",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 2: Test Input heading visible",
        "path": "/?page=2#input",
        "selector": ".section-head h2",
        "expected_text": "Test Your Own Source",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 3: Test Summary table visible",
        "path": "/?page=3#summary",
        "selector": ".summary-table",
        "expected_text": "Total Test",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 3: AI Failure Analysis heading visible",
        "path": "/?page=3#summary",
        "selector": ".ai-panel h2",
        "expected_text": "AI Failure Analysis",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 4: Stage Details navigation visible",
        "path": "/?page=4#stages",
        "selector": "#stages .page-nav",
        "expected_text": "Next: Saved Reports",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 5: Exit panel visible",
        "path": "/?page=5#reports",
        "selector": ".exit-panel h3",
        "expected_text": "Test run complete",
        "timeout_ms": 15000,
    },
    {
        "name": "ui page 5: Finish and Exit action visible",
        "path": "/?page=5#reports",
        "selector": "#exitBtn",
        "expected_text": "Finish & Exit",
        "timeout_ms": 15000,
    },
]
