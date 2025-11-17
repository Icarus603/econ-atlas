from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from econ_atlas.source_profiling.sample_inventory import build_inventory


def test_build_inventory_counts_and_notes(tmp_path: Path) -> None:
    samples = tmp_path / "samples"
    wiley = samples / "wiley" / "journal-a"
    wiley.mkdir(parents=True)
    ts = datetime(2025, 1, 2, tzinfo=timezone.utc)
    file_path = wiley / "foo.html"
    file_path.write_text("<html></html>", encoding="utf-8")
    epoch = ts.timestamp()
    os.utime(file_path, (epoch, epoch))

    informs = samples / "informs" / "management-science"
    informs.mkdir(parents=True)

    inventories = build_inventory(samples)
    assert len(inventories) == 2
    wiley_inventory = next(item for item in inventories if item.source_type == "wiley")
    assert wiley_inventory.total_samples == 1
    assert wiley_inventory.latest_fetched_at is not None
    assert isinstance(wiley_inventory.latest_fetched_at, datetime)
    assert wiley_inventory.journals[0].slug == "journal-a"
    assert wiley_inventory.journals[0].sample_count == 1

    informs_inventory = next(item for item in inventories if item.source_type == "informs")
    assert informs_inventory.total_samples == 0
    assert informs_inventory.notes is not None
    assert informs_inventory.journals[0].sample_count == 0
