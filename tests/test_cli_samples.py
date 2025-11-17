from pathlib import Path
from typing import Any, Callable

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
