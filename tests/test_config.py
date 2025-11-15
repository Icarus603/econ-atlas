from datetime import timedelta

import pytest

from econ_atlas.config import SettingsError, parse_interval


def test_parse_interval_text() -> None:
    assert parse_interval("7d", None) == timedelta(days=7)
    assert parse_interval("12h", None) == timedelta(hours=12)
    assert parse_interval("45m", None) == timedelta(minutes=45)


def test_parse_interval_seconds_override() -> None:
    assert parse_interval("1h", 30) == timedelta(seconds=30)
    with pytest.raises(SettingsError):
        parse_interval("1h", 0)


def test_parse_invalid_interval() -> None:
    with pytest.raises(SettingsError):
        parse_interval("invalid", None)
