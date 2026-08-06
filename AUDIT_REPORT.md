# Jacobian Codebase Audit Report

## Date: 2026-08-07
## Scope: Verification kernel, MCP adapters, benchmark verifiers, domain operations, process management

---

## Summary

| # | Bug | Location | Severity | Status |
|---|-----|----------|----------|--------|
| 1 | `_close_evicted` overwrites concurrently-created runtime | `remote.py` | **High** | Fixed |
| 2 | `close()` leaves `_closing=True` on failure | `remote.py` | **Medium** | Fixed |
| 3 | `_run_blocking` orphans worker on second `CancelledError` | `tooling.py` | **Medium** | Fixed |
| 4 | `_trial_status` fail-open on missing status | `observation_results.py` | **Medium** | Fixed |
| 5 | `compare_evidence` only checks core metrics for missing pairs | `observation_comparison.py` | **Medium** | Fixed |
| 6 | `mkstemp` fd leak on `os.fdopen` failure | `statement.py` | **Low** | Fixed |

Previously fixed bugs (merged to main in prior PRs):
| # | Bug | Location | Severity | Status |
|---|-----|----------|----------|--------|
| 7 | `_observation_pair_failures` returns `[]` on malformed JSON | `benchmark_contracts.py` | **High** | Merged |
| 8 | `_usage` skips incompleteness check on non-dict stats | `heldout_runner.py` | **High** | Merged |
| 9 | `load_registry` cache has no invalidation path | `harbor_suite.py` | **Medium** | Merged |
| 10 | `install_source_only_importer` doesn't purge stale modules | `implementation.py` | **Medium** | Merged |

---

## Bug Details

### Bug 1: `_close_evicted` overwrites concurrently-created runtime (High)

**File:** `src/jacobian/adapters/mcp/remote.py`

When `_close_evicted` fails (the runtime's `close()` raises), the exception handler
blindly restores `self._runtimes[tenant_key] = entry`. Between the lock release in
`_plan_acquisition` and `_close_evicted`, another thread can create a new runtime
for the same tenant. The blind overwrite destroys the new runtime, leaking it.

**Fix:** Guard the restore with `if tenant_key not in self._runtimes`.

### Bug 2: `close()` permanently rejects leases after partial failure (Medium)

**File:** `src/jacobian/adapters/mcp/remote.py`

When `close()` fails to close some runtimes, the failure path resets
`_shutdown_in_flight = False` but never resets `_closing`. The router rejects all
future `lease_for()` calls with `TenantRuntimeRouterClosedError` indefinitely.

**Fix:** Reset `_closing = False` in the failure path.

### Bug 3: `_run_blocking` orphans worker thread on second `CancelledError` (Medium)

**File:** `src/jacobian/adapters/mcp/tooling.py`

When draining a cancelled worker, the inner `except Exception:` guard does not catch
`asyncio.CancelledError` (which inherits from `BaseException` in Python 3.12+). A
second cancellation during the drain skips `exc.drained_result = drained` and
the `raise`, orphaning the worker task.

**Fix:** Broaden the inner exception guard to `except BaseException:`.

### Bug 4: `_trial_status` fail-open on missing status (Medium)

**File:** `benchmarks/tooling/observation_results.py`

A trial with a missing, `None`, or non-string `status` field was silently treated as
`"COMPLETED"`. This meant an incomplete trial could pass the observation evidence
validation gate.

**Fix:** Return `"ERROR"` for any non-string or non-`"COMPLETED"` status.

### Bug 5: `compare_evidence` silently drops pairs with None metrics (Medium)

**File:** `benchmarks/tooling/observation_comparison.py`

Only `correctness` and `false_certification` were checked for missing metric pairs.
Non-core metrics (`evidence_validity`, `scope_accuracy`, `reward`, etc.) silently
dropped pairs with `None` values, potentially inflating means via survivorship bias.

**Fix:** Check all `metric_names` for missing pairs.

### Bug 6: `mkstemp` fd leak on `os.fdopen` failure (Low)

**File:** `src/jacobian/lean_frontend/statement.py`

If `os.fdopen(fd, "w")` raised before the `with` block took ownership, the raw file
descriptor from `mkstemp` was leaked.

**Fix:** Wrap `os.fdopen` in a try/except that closes the fd on failure.

---

## Verification

All fixes include regression tests in `tests/unit/tooling/test_audit_fixes_round2.py`
(8 tests, all passing). The broader tooling and contract test suites (304 tests) pass
with no regressions. Lint and typecheck are clean.

## Areas Audited (No Bugs Found)

- **Verification kernel** (`verification/service.py`): All verification paths correctly
  guard `VERIFIED` with `conclusion == Conclusion.TRUE`. TIMEOUT/CANCELLED/ERROR all
  return `_operational_failure`, never `VERIFIED`.

- **Checker authorization** (`registry.py`): Checkers cannot self-authorize. Content-addressed
  IDs and policy locks prevent self-authorization.

- **Domain operations** (finite_sets, number_theory, combinatorics, polynomial,
  matrix_lattice, graph_optimization): All bounded search operations correctly return
  `UNKNOWN` completeness for incomplete results. No case where `COMPLETED` is set for
  an incomplete computation.

- **Process management** (`bounded_process.py`): Robust process-group cleanup,
  bounded output, and timeout handling.
