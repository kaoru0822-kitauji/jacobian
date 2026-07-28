# Deep Test Suite Audit — Findings & Recommendations

**Repo:** `/root/jacobian` · **Branch:** `fix/audit-critical-bugs-and-improvements` · **Scope:** All 1,007 tests across 6 test directories

## Test Suite at a Glance

| Directory | Files | Tests | % of total |
|-----------|-------|-------|------------|
| tests/integration | 90 | 609 | 60% |
| tests/contract | 30 | 150 | 15% |
| tests/checkers | 22 | 125 | 12% |
| tests/unit | 21 | 68 | 7% |
| tests/reference | 4 | 47 | 5% |
| tests/end_to_end | 2 | 8 | 1% |

**Total:** 169 files, 1,007 tests, 41,697 lines, ~4,639s estimated runtime

**Time distribution:** The top 10% slowest tests (66 tests) account for 32% of total runtime. The integration suite dominates at 4,485s (97% of total time).

---

## PART 1: Bad Tests & Antipatterns

### 1.1 `try/except` swallowing masks wrong exception types (HIGH)

**File:** `tests/integration/test_agent_ab_benchmark.py` (7 sites: lines 1156-1167, 1197-1208, 1283-1307, 1331-1342, 1434-1451, 1455-1472, 1496-1510)

```python
try:
    score_report(case, report, condition="control", ...)
except BENCHMARK["BenchmarkError"] as exc:
    assert "falsely certified" in str(exc)
else:
    raise AssertionError("false certification was accepted")
```

If `score_report` raises a *different* exception type (e.g., `TypeError`, `KeyError`), the test errors confusingly instead of failing cleanly. This pattern appears **7 times** — a systematic antipattern.

**Fix:** Replace with `pytest.raises(BENCHMARK["BenchmarkError"], match="falsely certified")`, which is already used correctly elsewhere in the same file (lines 1819, 2060).

### 1.2 Direct access to private APIs couples tests to implementation (HIGH)

**Files:** `tests/integration/test_search_orchestration.py` (lines 199, 243, 256, 278, 291, 461, 521), `tests/integration/test_workspaces.py` (lines 116, 139, 141, 872, 874, 881, 883, 918), `tests/integration/test_artifact_store.py` (21 private method calls)

Tests call `kernel.search._put_internal_artifact()`, `kernel.workspaces._connect()`, `kernel.workspaces._prepare_write()`, `store._write_blob()`, `store._blob_bytes_committed()`, `store._adjust_blob_bytes_committed()`, `store._blob_path()`, etc. If any private method is renamed, the test breaks even when the public API behavior is unchanged.

**Fix:** Expose test-only public helpers (e.g., `kernel.testing.corrupt_experiment()`) or use the public API. For `test_artifact_store.py`, the 21 private method calls are acceptable since the store's internal accounting IS the unit under test — but these should be documented as intentional test seams.

### 1.3 `runpy.run_path` + `cast(Any, ...)` loses all type safety (MEDIUM)

**File:** `tests/integration/test_agent_ab_benchmark.py` line 45

```python
BENCHMARK = runpy.run_path(str(PROJECT_ROOT / "benchmarks" / "agent_ab.py"))
```

This executes the benchmark module at collection time (side effects during collection) and requires `cast(Any, BENCHMARK["..."])` for every function access (~30 sites). A simple `from benchmarks.agent_ab import ...` would give static type checking and faster collection.

### 1.4 Raw SQL mutations to simulate corruption (MEDIUM)

**File:** `tests/integration/test_search_orchestration.py` (5 sites: lines 214-226, 358-375, 461-484, 521-544, 582-616)

Tests directly `sqlite3.connect()` and execute raw `UPDATE`/`INSERT` to corrupt state. This couples tests to the exact table schema. If a column is renamed or a migration runs, the tests break.

**Fix:** Add a `kernel.testing.corrupt_experiment(uri)` helper.

### 1.5 Unit tests misplaced in integration directory (MEDIUM)

**File:** `tests/integration/test_workspaces.py` lines 420-519 (5 test functions)

These 5 tests only test Pydantic model validation — no kernel, no store, no SQLite. They are pure contract unit tests that belong in `tests/contract/`.

### 1.6 Hardcoded timeouts with no adaptive logic (MEDIUM)

**Files:** `tests/integration/test_search_orchestration.py` (25+ occurrences), `tests/integration/test_enumeration_experiments.py` (15+)

Every `wait()` call uses a hardcoded `timeout_seconds=30` (or `15` or `90`). On a slow CI machine, 30s may be insufficient; on a fast machine, a hanging test wastes 30s.

**Fix:** Define `WAIT_TIMEOUT = int(os.environ.get("JACOBIAN_TEST_TIMEOUT", "30"))` and use it consistently.

### 1.7 Concurrency test race conditions (MEDIUM)

**File:** `tests/integration/test_workspaces.py` lines 863-930, `tests/integration/test_artifact_store.py` lines 272-327

`Event.wait(timeout=10)` with hardcoded 10s timeouts in concurrency tests. On a heavily loaded CI machine, the thread pool may not start within 10s, causing confusing `AssertionError` failures.

### 1.8 Embedded Python source as string literals (MEDIUM)

**File:** `tests/integration/test_enumeration_experiments.py` lines 708-755

A Python script is embedded as a string and run in a subprocess to simulate process death. No syntax checking, no IDE support, fragile to API changes.

**Fix:** Move to `tests/fixtures/_interrupt_enumeration.py`.

### 1.9 Schema description wording tests (MEDIUM)

**File:** `tests/integration/test_agent_ab_benchmark.py` lines 367-410

Tests assert on the *wording* of JSON Schema `description` fields and prompt text — not runtime behavior. Brittle to rewording.

### 1.10 Magic numbers without explanation (LOW)

**File:** `tests/integration/test_workspaces.py` lines 1025-1078

`assert context.context.total_dependency_count == 1023` — the magic number `1023` is never explained (it's `1024 - 1` from the dependency chain). Tests also create 1024 workspace items.

---

## PART 2: Structural Improvement Recommendations

### 2.1 Should the test suite be broken up?

**Yes — the integration suite should be split into domain and infrastructure subdirectories.**

Currently `tests/integration/` has 90 files / 609 tests in a flat directory. Natural sub-categories:

| Sub-category | Files | Tests | Est. time |
|--------------|-------|-------|-----------|
| graph/ | 17 | ~110 | ~700s |
| polynomial/ | 12 | ~80 | ~500s |
| sat_smt/ | 7 | ~50 | ~400s |
| lean/ | 5 | ~30 | ~200s |
| matrix/ | 4 | ~30 | ~200s |
| workflow/ | 7 | ~50 | ~600s |
| infrastructure/ | 12 | ~80 | ~500s |
| agent/ | 2 | ~32 | ~400s |
| other/ | ~24 | ~177 | ~1385s |

**Benefits:** Faster test selection (`pytest tests/integration/graph/`), clearer ownership in CI-ownership.json, easier parallel sharding.

**Cost:** A git mv of files into subdirectories — no test changes needed since the conftest marker hook resolves markers from the first path component under `tests/`.

### 2.2 Tests that should be unit tests

5 workspace contract tests in `tests/integration/test_workspaces.py` (lines 420-519) test pure Pydantic validation with no I/O. They should move to `tests/contract/`.

### 2.3 Missing markers on 50+ test files

50 test files across `tests/integration/`, `tests/checkers/`, `tests/unit/`, and `tests/reference/` have **no markers at all** (no `pytestmark`, no `@pytest.mark.*`). This means:
- The conftest layer-marker hook (which adds `integration`/`end_to_end` based on directory) is the only thing classifying them.
- `tests/checkers/` and `tests/reference/` have no layer marker in `_LAYER_MARKERS`, so their tests run under every marker-filtered invocation.

**Fix:** Add `pytestmark = pytest.mark.integration` (or `pytest.mark.contract` / `pytest.mark.conformance`) to all files missing markers.

### 2.4 Source files without direct tests

117 of 233 source files (50%) have no direct test file. Key gaps:
- `src/jacobian/claims.py` (138 lines) — no test
- `src/jacobian/conjectures.py` (887 lines) — no direct test (only via integration)
- `src/jacobian/checker_worker.py` (123 lines) — no direct test
- `src/jacobian/cvc5_worker.py` (174 lines) — no direct test

These are exercised indirectly via integration tests, but have no focused unit/contract tests for edge cases.

### 2.5 Test naming conventions

Test names follow a consistent pattern: `test_<subject>_<condition>` (e.g., `test_graph_atlas_search_is_bounded_complete_and_replayable`). No naming antipatterns found. The 8 duplicate test names across files are intentional — they test the same contract across different domain backends (e.g., SAT vs SMT).

### 2.6 Private API usage summary

- `store._*` private methods calls in tests: 21 (all in `test_artifact_store.py` — acceptable, testing internals)
- `kernel._*` private calls: 0 (clean)
- `search._*` private calls: 7 (in `test_search_orchestration.py` — coupling risk)
- `workspaces._*` private calls: 8 (in `test_workspaces.py` — coupling risk)
- `monkeypatch` usages: 362 (high but mostly for environment/fixture setup)
- `mock`/`MagicMock` references: 364

### 2.7 Duplicate test names

8 test function names appear in multiple files. All are intentional — they test the same contract across different domain backends (SAT vs SMT, matrix vs graph). This is a feature, not a bug: it demonstrates contract conformance across backends.

---

## PART 3: Recommendations Ranked by Impact

| # | Impact | Recommendation |
|----|--------|----------------|
| 1 | HIGH | Replace `try/except` antipattern with `pytest.raises` in `test_agent_ab_benchmark.py` (7 sites) |
| 2 | HIGH | Add test-only public helpers for private API access in `test_search_orchestration.py` and `test_workspaces.py` |
| 3 | MEDIUM | Replace `runpy.run_path` with proper `import` in `test_agent_ab_benchmark.py` |
| 4 | MEDIUM | Move 5 pure-validation tests from `tests/integration/test_workspaces.py` to `tests/contract/` |
| 5 | MEDIUM | Split `tests/integration/` into domain subdirectories (graph/, polynomial/, sat_smt/, lean/, etc.) |
| 6 | MEDIUM | Add `pytestmark` markers to 50+ files missing them |
| 7 | MEDIUM | Add `kernel.testing` helpers for corruption/recovery test scenarios |
| 8 | MEDIUM | Define configurable wait timeouts instead of hardcoded 30s |
| 9 | MEDIUM | Move embedded subprocess scripts to fixture files |
| 10 | LOW | Document magic numbers (e.g., `1023` in workspace dependency chain tests) |
