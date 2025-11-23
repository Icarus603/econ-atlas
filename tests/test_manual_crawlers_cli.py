import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import manual_crawlers.run as mc_run  # noqa: E402


def test_missing_cookie_fails(monkeypatch, capsys, tmp_path: Path) -> None:
    # Ensure cookie env absent
    monkeypatch.delenv("WILEY_COOKIES", raising=False)
    exit_code = mc_run.main(
        ["--sources", "economic-history-review", "--output-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "WILEY_COOKIES is required" in captured.err or "WILEY_COOKIES is required" in captured.out


def test_success_writes_archive(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WILEY_COOKIES", "dummy-cookie")
    exit_code = mc_run.main(
        ["--sources", "economic-history-review", "--output-dir", str(tmp_path)]
    )
    assert exit_code == 0
    path = tmp_path / "economic-history-review.json"
    assert path.exists()
    data = path.read_text()
    assert '"journal"' in data
    assert '"entries"' in data
