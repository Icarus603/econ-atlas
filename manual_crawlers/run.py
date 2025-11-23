from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

from manual_crawlers.sources import SOURCES, ManualSource, list_source_keys


@dataclass
class CrawlResult:
    source: ManualSource
    success: bool
    message: str
    output_path: Path | None = None


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual crawlers for cookie-bound journals")
    parser.add_argument(
        "--sources",
        type=str,
        default=",".join(list_source_keys()),
        help="Comma-separated list of sources to run (default: all manual-only sources)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../data"),
        help="Directory to write JSON archives (default: ../data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and report what would run without writing files",
    )
    return parser.parse_args(argv)


def ensure_env_loaded() -> None:
    if load_dotenv is not None:
        env_path = Path(__file__).resolve().parent / ".env"
        load_dotenv(env_path, override=False)


def resolve_sources(source_arg: str) -> List[ManualSource]:
    keys = [s.strip() for s in source_arg.split(",") if s.strip()]
    invalid = [k for k in keys if k not in SOURCES]
    if invalid:
        raise ValueError(f"Unknown sources: {', '.join(invalid)}")
    return [SOURCES[k] for k in keys]


def validate_cookie(source: ManualSource) -> Tuple[bool, str]:
    value = os.getenv(source.env_cookie_var)
    if value is None or value.strip() == "":
        return False, f"{source.env_cookie_var} is required for {source.name}"
    return True, "cookie present"


def build_archive(source: ManualSource) -> Dict:
    now = datetime.now(timezone.utc).isoformat()
    # Minimal schema match: journal metadata + entries list
    return {
        "journal": {
            "name": source.name,
            "rss_url": "",
            "notes": f"manual crawler ({source.notes})",
            "last_run_at": now,
        },
        "entries": [],
    }


def run_source(source: ManualSource, output_dir: Path, dry_run: bool) -> CrawlResult:
    ok, msg = validate_cookie(source)
    if not ok:
        return CrawlResult(source=source, success=False, message=msg)

    if dry_run:
        return CrawlResult(source=source, success=True, message="dry-run, skipped write")

    archive = build_archive(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{source.slug}.json"
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=2))
    return CrawlResult(
        source=source,
        success=True,
        message=f"wrote {path}",
        output_path=path,
    )


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    ensure_env_loaded()
    try:
        selected_sources = resolve_sources(args.sources)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    results: List[CrawlResult] = []
    for source in selected_sources:
        result = run_source(source, args.output_dir, args.dry_run)
        results.append(result)
        status = "OK" if result.success else "FAIL"
        print(f"[{status}] {source.key}: {result.message}")

    failures = [r for r in results if not r.success]
    if failures:
        print(f"[SUMMARY] {len(failures)} failure(s), {len(results) - len(failures)} success", file=sys.stderr)
        return 1

    print(f"[SUMMARY] {len(results)} success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
