"""Seed initial Odyssey sources into the RAG database.

Reads source documents from known relative paths and runs the ingestion
pipeline for each one.  The paths are relative to the workspace root
(one level above the RAG/ directory).

Usage:
    # From the RAG/ directory:
    PYTHONPATH=src python scripts/seed_initial_sources.py

    # Dry-run (show what would be ingested without actually ingesting):
    PYTHONPATH=src python scripts/seed_initial_sources.py --dry-run

    # Force re-ingest even if file hash hasn't changed:
    PYTHONPATH=src python scripts/seed_initial_sources.py --replace
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# ── Source manifest ────────────────────────────────────────────────────────────
# Paths are relative to the workspace root (parent of RAG/).
# Set WORKSPACE_ROOT env var or pass --workspace-root to override.

INITIAL_SOURCES: list[dict] = [
    # ── Annex B specification ──────────────────────────────────────────────
    {
        "path": "md/IPS_Annex_B_Message_Specifications.md",
        "source_type": "annex_b_spec",
    },
    # ── Technical documentation ────────────────────────────────────────────
    {
        "path": "notion/BIMPAY_TECHNICAL_DOC.md",
        "source_type": "tech_doc",
    },
    {
        "path": "notion/BIMPAY_INFRASTRUCTURE_DOC.md",
        "source_type": "tech_doc",
    },
    # ── Claude context files ───────────────────────────────────────────────
    {
        "path": "odyssey/CLAUDE.md",
        "source_type": "claude_context",
    },
    {
        "path": "IA SKIILLS/CLAUDE.md",
        "source_type": "claude_context",
    },
    # ── PHP Bimpay code (56 files — directory glob) ────────────────────────
    {
        "path": "Bimpay Context Claude/Bimpay/",
        "source_type": "php_code",
        "recursive": True,
        "extensions": [".php"],
    },
    # ── XML examples ──────────────────────────────────────────────────────
    {
        "path": "IPS Messages Examples/",
        "source_type": "xml_example",
        "recursive": True,
        "extensions": [".xml"],
    },
    # ── Postman collections ────────────────────────────────────────────────
    {
        "path": "IPS Messages Examples/BIMPAY POC.postman_collection.json",
        "source_type": "postman_collection",
    },
    {
        "path": "md/BIMPAY POC.postman_collection.json",
        "source_type": "postman_collection",
    },
]


def _resolve_files(entry: dict, workspace_root: Path) -> list[tuple[Path, str]]:
    """Resolve a source entry to a list of (file_path, source_type) tuples."""
    raw_path = workspace_root / entry["path"]
    source_type = entry["source_type"]

    if raw_path.is_file():
        return [(raw_path, source_type)]

    if raw_path.is_dir():
        extensions = entry.get("extensions", None)
        recursive = entry.get("recursive", False)
        glob_pattern = "**/*" if recursive else "*"
        files = []
        for p in raw_path.glob(glob_pattern):
            if p.is_file():
                if extensions is None or p.suffix.lower() in extensions:
                    files.append((p, source_type))
        return sorted(files)

    logger.warning("seed.path_not_found", path=str(raw_path))
    return []


async def _run_seed(
    workspace_root: Path,
    replace: bool,
    dry_run: bool,
) -> None:
    """Main async seed logic."""
    from odyssey_rag.ingestion.pipeline import ingest

    all_files: list[tuple[Path, str]] = []
    for entry in INITIAL_SOURCES:
        all_files.extend(_resolve_files(entry, workspace_root))

    logger.info("seed.files_found", total=len(all_files), dry_run=dry_run)

    completed = skipped = failed = 0
    t0 = time.monotonic()

    for file_path, source_type in all_files:
        rel = file_path.relative_to(workspace_root)
        log = logger.bind(path=str(rel), source_type=source_type)

        if dry_run:
            log.info("seed.would_ingest")
            continue

        result = await ingest(
            source_path=str(file_path),
            overrides={"source_type": source_type},
            replace_existing=replace,
        )

        if result.status == "completed":
            log.info("seed.completed", chunks=result.chunks_created)
            completed += 1
        elif result.status == "skipped":
            log.info("seed.skipped", reason=result.reason)
            skipped += 1
        else:
            log.error("seed.failed", error=result.error)
            failed += 1

    elapsed = time.monotonic() - t0
    logger.info(
        "seed.summary",
        total=len(all_files),
        completed=completed,
        skipped=skipped,
        failed=failed,
        elapsed_s=round(elapsed, 1),
    )

    if failed:
        sys.exit(1)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed initial Odyssey sources into the RAG database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).parent.parent.parent),
        help="Absolute path to the workspace root (parent of RAG/).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        default=False,
        help="Re-ingest files even if their hash hasn't changed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be ingested without actually ingesting.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    workspace_root = Path(args.workspace_root).resolve()
    logger.info(
        "seed.starting",
        workspace_root=str(workspace_root),
        replace=args.replace,
        dry_run=args.dry_run,
    )
    asyncio.run(_run_seed(workspace_root, replace=args.replace, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
