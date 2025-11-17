import json
from pathlib import Path
from typing import Callable

import pytest
from typer.testing import CliRunner

from econ_atlas.cli import app


def test_sciencedirect_warmup_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    def fake_warmup(
        *,
        profile_dir: Path,
        target_url: str,
        wait_callback: Callable[[], None],
        export_local_storage: Path | None,
        user_agent: str | None,
    ) -> None:
        captured["profile_dir"] = profile_dir
        captured["target_url"] = target_url
        captured["export_path"] = export_local_storage
        captured["user_agent"] = user_agent
        wait_callback()
        if export_local_storage:
            export_local_storage.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("econ_atlas.cli.warmup_sciencedirect_profile", fake_warmup)

    profile_dir = tmp_path / "profile"
    local_storage = tmp_path / "storage.json"
    result = runner.invoke(
        app,
        [
            "samples",
            "scd-session",
            "warmup",
            "--profile-dir",
            str(profile_dir),
            "--pii",
            "S0047272725001975",
            "--export-local-storage",
            str(local_storage),
        ],
        input="\n",
    )

    assert result.exit_code == 0
    assert "warmup complete" in result.stdout.lower()
    assert captured["target_url"] == "https://www.sciencedirect.com/science/article/pii/S0047272725001975"
    assert captured["profile_dir"] == profile_dir.resolve()
    assert captured["export_path"] == local_storage.resolve()


def _write_sample(tmp_path: Path, fixture_name: str, target_name: str) -> Path:
    fixture = Path(__file__).parent / "fixtures" / "sciencedirect" / fixture_name
    destination = tmp_path / "samples" / "sciencedirect" / "demo-journal"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / target_name
    target.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path / "samples" / "sciencedirect"


def test_samples_parse_sciencedirect_success(tmp_path: Path) -> None:
    input_dir = _write_sample(tmp_path, "fallback_full.html", "full.html")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["samples", "parse", "sciencedirect", "--input", str(input_dir)],
    )

    assert result.exit_code == 0
    assert "parsed: 1" in result.stdout


def test_samples_parse_sciencedirect_reports_missing(tmp_path: Path) -> None:
    input_dir = _write_sample(tmp_path, "fallback_full.html", "full.html")
    _write_sample(tmp_path, "fallback_missing.html", "missing.html")
    output = tmp_path / "parsed.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "samples",
            "parse",
            "sciencedirect",
            "--input",
            str(input_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "missing-fields: 1" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["parsed"]) == 2
    assert any(record["missing"] for record in payload["parsed"])
