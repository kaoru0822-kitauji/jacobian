from __future__ import annotations

import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]
DATASET = REPO_ROOT / "benchmarks" / "datasets" / "research-diagnostics-v1"
TASKS = DATASET / "tasks"


def _task_dirs() -> list[Path]:
    return sorted(path.parent for path in TASKS.rglob("task.toml"))


def test_research_diagnostics_are_one_public_answer_visible_task_each() -> None:
    tasks = _task_dirs()
    assert len(tasks) == 18
    assert {path.name for path in tasks} == {
        f"jcb-postdoc-{number:03d}" for number in range(1, 19)
    }
    manifest = tomllib.loads((DATASET / "dataset.toml").read_text())
    assert manifest["dataset"]["name"] == "jacobian/research-diagnostics-v1"
    assert len(manifest["tasks"]) == 18
    for task in tasks:
        cfg = tomllib.loads((task / "task.toml").read_text())
        metadata = cfg["metadata"]
        assert metadata["evaluation_kind"] == "research-diagnostic"
        assert metadata["answer_visibility"] == "public"
        assert metadata["assurance_ceiling"] == "COMPUTED"
        assert metadata["provenance_class"] == "public-answer-visible-diagnostic"
        assert (task / "README.md").is_file()
        assert (task / "instruction.md").is_file()
        assert (task / "environment" / "input.json").is_file()
        assert (task / "solution").is_dir()
        assert (task / "tests" / "verifier.py").is_file()
        prompt = (task / "instruction.md").read_text().lower()
        assert "http://" not in prompt and "https://" not in prompt


def test_research_tasks_keep_source_answers_out_of_agent_environment() -> None:
    for task in _task_dirs():
        visible = [task / "instruction.md", *(task / "environment").rglob("*")]
        for path in visible:
            if path.is_file() and path.suffix in {".json", ".md", ".py", ".toml"}:
                text = path.read_text(errors="replace").lower()
                assert "source_answer" not in text
                assert "oracle_summary" not in text
                if path.name == "input.json":
                    json.loads(text)


def test_research_status_overlay_is_folded_into_task_maintainer_metadata() -> None:
    required = {"historical_fit", "current_status", "evaluation_status", "next_action"}
    for task in _task_dirs():
        cfg = tomllib.loads((task / "task.toml").read_text())
        metadata = cfg["metadata"]
        assert required <= metadata.keys()
        assert metadata["historical_fit"] in {"DIRECT", "PARTIAL", "MISSING"}
        assert metadata["current_status"] in {"COVERED", "PARTIAL", "OPEN_GAP"}
        assert metadata["evaluation_status"] in {
            "REGRESSION_COVERED",
            "RUNNABLE_PUBLIC_REPRODUCTION",
            "BLOCKED_ON_INTERVENTION",
        }
        assert metadata["next_action"]
        readme = (task / "README.md").read_text()
        assert "## Portfolio status" in readme
        assert metadata["current_status"] in readme
