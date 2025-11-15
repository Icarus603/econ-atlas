from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from econ_atlas.config import SettingsError, build_settings
from econ_atlas.ingest.feed import FeedClient
from econ_atlas.runner import Runner, RunReport, run_scheduler
from econ_atlas.sources.list_loader import JournalListLoader
from econ_atlas.storage.json_store import JournalStore
from econ_atlas.translate.deepseek import DeepSeekTranslator

app = typer.Typer(help="econ-atlas CLI")
crawl_app = typer.Typer(help="Run RSS crawls")
LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Allow `python -m econ_atlas` execution."""
    app()


@crawl_app.callback(invoke_without_command=True)
def crawl(
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="Path to the journal list CSV."),
    output_dir: Path = typer.Option(Path("data"), help="Directory for per-journal JSON files."),
    once: bool = typer.Option(False, "--once", help="Run a single crawl and exit."),
    interval: str = typer.Option("7d", help="Interval between runs (e.g., 12h, 2d). Ignored when --once is used."),
    interval_seconds: Optional[int] = typer.Option(
        None,
        help="Explicit interval in seconds (overrides --interval).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Entry point for crawling journals."""
    _configure_logging(verbose)
    load_dotenv()
    try:
        settings = build_settings(
            list_path=list_path,
            output_dir=output_dir,
            interval_text=interval,
            interval_seconds=interval_seconds,
            run_once=once,
        )
    except SettingsError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    runner = Runner(
        list_loader=JournalListLoader(settings.list_path),
        feed_client=FeedClient(),
        translator=DeepSeekTranslator(api_key=settings.deepseek_api_key),
        store=JournalStore(settings.output_dir),
    )

    if settings.run_once:
        report = runner.run()
        _print_report(report)
        raise typer.Exit(code=0 if not report.had_errors else 1)

    interval_seconds_value = settings.interval.total_seconds()
    run_scheduler(runner, interval_seconds_value, on_report=_print_report)


app.add_typer(crawl_app, name="crawl")


def _print_report(report: RunReport) -> None:
    typer.echo(
        f"Run window {report.started_at.isoformat()} - {report.finished_at.isoformat()}"
    )
    typer.echo(
        f" Journals: {len(report.results)} | New entries: {report.total_new_entries} | Translation failures: {report.total_translation_failures}"
    )
    for result in report.results:
        status = "ok" if result.succeeded else f"failed: {result.error}"
        typer.echo(
            f"  - {result.journal.name}: fetched={result.fetched}, added={result.stored.added}, "
            f"updated={result.stored.updated}, translations={result.translation_attempts}, "
            f"translation_failures={result.translation_failures} [{status}]"
        )
    if report.errors:
        typer.secho("Errors:", fg=typer.colors.RED)
        for message in report.errors:
            typer.secho(f"  * {message}", fg=typer.colors.RED)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")
