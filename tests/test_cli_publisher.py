from __future__ import annotations

from datetime import datetime, timezone

from importlib import import_module

from typer.testing import CliRunner

from econatlas.cli.app import RunReport, app
from econatlas.models import JournalSource


runner = CliRunner()
cli_app = import_module("econatlas.cli.app")


def test_crawl_publisher_does_not_trigger_parent_callback(monkeypatch: object) -> None:
    """Ensure `crawl publisher ...`不会先跑父 callback 导致抓取全部来源。"""
    calls: list[list[str]] = []

    def fake_run_once(*, journals: list[JournalSource], **_: object) -> RunReport:
        calls.append([journal.slug for journal in journals])
        now = datetime.now(timezone.utc)
        return RunReport(started_at=now, finished_at=now, results=[], errors=[])

    def fake_load(self: object) -> list[JournalSource]:  # noqa: ANN001
        return [
            JournalSource(name="CNKI", rss_url="https://cnki.invalid/rss", slug="cnki", source_type="cnki"),
            JournalSource(
                name="ScienceDirect Journal",
                rss_url="https://rss.sciencedirect.com/publication/science/00000000",
                slug="jfe",
                source_type="sciencedirect",
            ),
        ]

    monkeypatch.setattr(cli_app, "_run_once", fake_run_once)
    monkeypatch.setattr(cli_app.JournalListLoader, "load", fake_load)

    result = runner.invoke(
        app,
        ["crawl", "publisher", "sciencedirect", "--once", "--skip-translation"],
        env={"DEEPSEEK_API_KEY": "dummy"},
    )

    assert result.exit_code == 0, result.output
    # 仅应调用一次，且只包含 ScienceDirect 期刊。
    assert calls == [["jfe"]]
