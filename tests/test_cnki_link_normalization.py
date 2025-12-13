from __future__ import annotations

from econatlas.cli.app import _cnki_search_url


def test_cnki_search_url_decodes_html_entities() -> None:
    assert _cnki_search_url("A &amp; B").endswith("A+%26+B")

