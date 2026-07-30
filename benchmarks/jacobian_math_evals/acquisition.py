"""Resolve public source metadata without placing snapshots in the repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .catalog import LOCK_PATH, load_sources
from .models import SourceRecord


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "jacobian-math-evals/1",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object from {url}")
    return value


def _github_repo(url: str) -> str | None:
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(parts) < 2:
        return None
    return "/".join(parts[:2]).removesuffix(".git")


def _github_subresource_path(url: str) -> str | None:
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(parts) >= 5 and parts[2] in {"blob", "tree"}:
        path = "/".join(parts[4:])
        return path or None
    return None


def _hf_dataset(url: str) -> str | None:
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    if parts and parts[0] == "datasets":
        parts = parts[1:]
    if len(parts) < 2:
        return None
    return "/".join(parts[:2])


def _resolve_github(source: SourceRecord, timestamp: str) -> dict[str, Any]:
    repo = _github_repo(source.canonical_url)
    if repo is None:
        raise ValueError("URL does not identify a GitHub repository")
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
    metadata = json.loads(result.stdout)
    canonical_repo = metadata["full_name"]
    head = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{canonical_repo}/commits/{metadata['default_branch']}",
            "--jq",
            ".sha",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    ).stdout.strip()
    repository_url = metadata["html_url"]
    subresource_path = _github_subresource_path(source.url) or _github_subresource_path(
        source.canonical_url
    )
    canonical_url = (
        f"{repository_url}/blob/{head}/{subresource_path}"
        if subresource_path
        else repository_url
    )
    redirects = (
        [source.canonical_url]
        if source.canonical_url.rstrip("/") != canonical_url.rstrip("/")
        else []
    )
    state = "archived" if metadata["archived"] else "public"
    if metadata["disabled"]:
        state = "unavailable"
    return {
        "source_id": source.source_id,
        "access_state": state,
        "canonical_url": canonical_url,
        "repository_url": repository_url,
        "subresource_path": subresource_path,
        "immutable_revision": head,
        "license": (metadata.get("license") or {}).get("spdx_id") or "NOASSERTION",
        "evidence_timestamp": timestamp,
        "redirect_from": redirects,
        "provider": "github-rest-v3-via-gh",
    }


def _resolve_hf(source: SourceRecord, timestamp: str) -> dict[str, Any]:
    dataset = _hf_dataset(source.canonical_url)
    if dataset is None:
        raise ValueError("URL does not identify a Hugging Face dataset")
    quoted = urllib.parse.quote(dataset, safe="/")
    metadata = _get_json(f"https://huggingface.co/api/datasets/{quoted}")
    gated_value = metadata.get("gated", False)
    gated = bool(gated_value)
    state = "gated" if gated or metadata.get("private") else "public"
    result: dict[str, Any] = {
        "source_id": source.source_id,
        "access_state": state,
        "canonical_url": f"https://huggingface.co/datasets/{metadata['id']}",
        "immutable_revision": metadata["sha"],
        "license": (metadata.get("cardData") or {}).get("license") or "NOASSERTION",
        "evidence_timestamp": timestamp,
        "gated": gated,
        "provider": "huggingface-hub-and-dataset-viewer",
    }
    if state == "public":
        try:
            splits = _get_json(
                "https://datasets-server.huggingface.co/splits?"
                + urllib.parse.urlencode({"dataset": metadata["id"]})
            ).get("splits", [])
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError):
            splits = []
        result["configurations"] = sorted(
            {item["config"] for item in splits if item.get("config")}
        )
        result["splits"] = sorted(
            {
                f"{item['config']}/{item['split']}"
                for item in splits
                if item.get("config") and item.get("split")
            }
        )
        try:
            sizes = _get_json(
                "https://datasets-server.huggingface.co/size?"
                + urllib.parse.urlencode({"dataset": metadata["id"]})
            )
            result["row_count"] = (
                sizes.get("size", {}).get("dataset", {}).get("num_rows")
            )
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError):
            result["row_count"] = None
        try:
            parquet = _get_json(
                "https://datasets-server.huggingface.co/parquet?"
                + urllib.parse.urlencode({"dataset": metadata["id"]})
            ).get("parquet_files", [])
            result["parquet_shards"] = sorted(
                item["url"] for item in parquet if item.get("url")
            )
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError):
            result["parquet_shards"] = []
    return result


def resolve_source(source: SourceRecord, timestamp: str) -> dict[str, Any]:
    try:
        if source.host == "github.com":
            return _resolve_github(source, timestamp)
        if source.host == "huggingface.co":
            return _resolve_hf(source, timestamp)
        return {
            "source_id": source.source_id,
            "access_state": "unresolved",
            "canonical_url": source.canonical_url,
            "evidence_timestamp": timestamp,
            "provider": "manual-resolution-required",
            "error": f"no automated resolver for {source.host}",
        }
    except subprocess.CalledProcessError as error:
        state = (
            "unavailable"
            if source.host == "github.com" and "404" in error.stderr
            else "unresolved"
        )
        return {
            "source_id": source.source_id,
            "access_state": state,
            "canonical_url": source.canonical_url,
            "evidence_timestamp": timestamp,
            "provider": "github-rest-v3-via-gh",
            "error": f"upstream request failed: {error.stderr.strip()}",
        }
    except (
        KeyError,
        subprocess.TimeoutExpired,
        TimeoutError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
    ) as error:
        return {
            "source_id": source.source_id,
            "access_state": "unresolved",
            "canonical_url": source.canonical_url,
            "evidence_timestamp": timestamp,
            "provider": "resolution-failed",
            "error": f"{type(error).__name__}: {error}",
        }


def resolve_catalog(*, workers: int = 12) -> dict[str, Any]:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    sources = load_sources()
    prior_entries: dict[str, dict[str, Any]] = {}
    if LOCK_PATH.exists():
        prior_lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        prior_entries = {
            entry["source_id"]: entry for entry in prior_lock.get("sources", [])
        }
    resolved: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(resolve_source, source, timestamp): source.source_id
            for source in sources
        }
        for future in as_completed(futures):
            resolved[futures[future]] = future.result()
    for source in sources:
        entry = resolved[source.source_id]
        if (
            source.snapshot_sha256
            and entry.get("immutable_revision") == source.immutable_revision
        ):
            entry["snapshot_sha256"] = source.snapshot_sha256
        prior = prior_entries.get(source.source_id, {})
        if "gitcontribute" in prior.get("provider", "") and entry.get(
            "canonical_url"
        ) == prior.get("canonical_url"):
            entry["provider"] = prior["provider"]
            entry["metadata_evidence_timestamp"] = prior["metadata_evidence_timestamp"]
            entry["gitcontribute_job_id"] = prior["gitcontribute_job_id"]
    entries = [resolved[source.source_id] for source in sources]
    return {
        "lock_version": 1,
        "catalog_manifest_version": "1.0",
        "resolved_at": timestamp,
        "sources": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jacobian-math-evals-acquire")
    parser.add_argument("--output", type=Path, default=LOCK_PATH)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be positive")
    lock = resolve_catalog(workers=args.workers)
    args.output.write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
