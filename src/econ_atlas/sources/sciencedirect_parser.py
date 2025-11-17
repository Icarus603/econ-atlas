from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from itertools import zip_longest
from typing import Any, Generic, Literal, Sequence, TypeVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser

SCID_BASE_URL = "https://www.sciencedirect.com"
RE_PII = re.compile(r"/pii/([^/?#]+)", re.IGNORECASE)
RE_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)

T = TypeVar("T")


@dataclass(frozen=True)
class FieldValue(Generic[T]):
    value: T | None
    source: Literal["dom", "meta", "url", "inferred"] | None = None
    missing_reason: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class ScienceDirectAuthor:
    name: str
    affiliations: list[str]


@dataclass(frozen=True)
class ScienceDirectParsedArticle:
    title: FieldValue[str]
    doi: FieldValue[str]
    pii: FieldValue[str]
    authors: FieldValue[list[ScienceDirectAuthor]]
    publication_date: FieldValue[str]
    abstract: FieldValue[str]
    keywords: FieldValue[list[str]]
    highlights: FieldValue[list[str]]
    pdf_url: FieldValue[str]

    def missing_fields(self) -> dict[str, str]:
        report: dict[str, str] = {}
        for attr in (
            "title",
            "doi",
            "pii",
            "authors",
            "publication_date",
            "abstract",
            "keywords",
            "highlights",
            "pdf_url",
        ):
            field_value: FieldValue[Any] = getattr(self, attr)
            if field_value.is_missing and field_value.missing_reason:
                report[attr] = field_value.missing_reason
        return report

    def to_dict(self) -> dict[str, Any]:
        authors = self.authors.value if self.authors.value is not None else []
        keywords = self.keywords.value if self.keywords.value is not None else []
        highlights = self.highlights.value if self.highlights.value is not None else []
        return {
            "title": self.title.value,
            "doi": self.doi.value,
            "pii": self.pii.value,
            "authors": [asdict(author) for author in authors],
            "publication_date": self.publication_date.value,
            "abstract": self.abstract.value,
            "keywords": keywords,
            "highlights": highlights,
            "pdf_url": self.pdf_url.value,
            "missing": self.missing_fields(),
        }


def parse_sciencedirect_fallback(html: str, *, url: str | None = None) -> ScienceDirectParsedArticle:
    soup = BeautifulSoup(html, "html.parser")
    pii_value, pii_source = _extract_pii(soup, url)
    doi_value, doi_source = _extract_doi(soup, html)
    title_value, title_source = _extract_title(soup)
    authors_value, authors_source = _extract_authors(soup)
    pub_date_value, pub_date_source = _extract_publication_date(soup)
    abstract_value, abstract_source = _extract_abstract(soup)
    keywords_value, keywords_source = _extract_keywords(soup)
    highlights_value, highlights_source = _extract_highlights(soup)
    pdf_value, pdf_source = _extract_pdf_url(soup, url, pii_value)

    return ScienceDirectParsedArticle(
        title=_field(title_value, title_source, "title not found in DOM or meta"),
        doi=_field(doi_value, doi_source, "DOI missing from DOM/meta"),
        pii=_field(pii_value, pii_source, "PII missing from DOM/meta"),
        authors=_field(authors_value, authors_source, "author list missing"),
        publication_date=_field(pub_date_value, pub_date_source, "publication date missing"),
        abstract=_field(abstract_value, abstract_source, "abstract missing"),
        keywords=_field(keywords_value, keywords_source, "keywords missing"),
        highlights=_field(highlights_value, highlights_source, "highlights missing"),
        pdf_url=_field(pdf_value, pdf_source, "PDF link missing"),
    )


def _field(value: T | None, source: Literal["dom", "meta", "url", "inferred"] | None, missing: str) -> FieldValue[T]:
    if value:
        return FieldValue(value=value, source=source)
    return FieldValue(value=None, source=None, missing_reason=missing)


def _extract_title(soup: BeautifulSoup) -> tuple[str | None, Literal["dom", "meta"] | None]:
    title_tag = soup.select_one('[data-qa="article-title"], h1[data-qa]')
    if title_tag:
        text = _text(title_tag)
        if text:
            return text, "dom"
    return _meta_content(soup, ["citation_title"])


def _extract_doi(soup: BeautifulSoup, raw_html: str) -> tuple[str | None, Literal["dom", "meta", "url"] | None]:
    value, source = _meta_content(soup, ["citation_doi", "dc.identifier"])
    if value:
        return value, source
    anchor = soup.find("a", href=re.compile(r"doi.org", re.IGNORECASE))
    href = _attr_str(anchor, "href") if anchor else None
    if href:
        match = RE_DOI.search(href)
        if match:
            return match.group(0), "dom"
    html_match = RE_DOI.search(raw_html)
    if html_match:
        return html_match.group(0), "url"
    return None, None


def _extract_pii(soup: BeautifulSoup, url: str | None) -> tuple[str | None, Literal["dom", "meta", "url"] | None]:
    value, source = _meta_content(soup, ["citation_pii"])
    if value:
        return value, source
    attr_tag = soup.find(attrs={"data-pii": True})
    attr_value = _attr_str(attr_tag, "data-pii") if attr_tag else None
    if attr_value:
        return attr_value.strip(), "dom"
    for anchor in soup.find_all("a", href=True):
        href = _attr_str(anchor, "href")
        if not href:
            continue
        match = RE_PII.search(href)
        if match:
            return match.group(1), "dom"
    if url:
        match = RE_PII.search(url)
        if match:
            return match.group(1), "url"
    return None, None


def _extract_authors(soup: BeautifulSoup) -> tuple[list[ScienceDirectAuthor] | None, Literal["dom", "meta"] | None]:
    authors: list[ScienceDirectAuthor] = []
    for container in soup.select('[data-qa="author"], [data-qa="author-item"]'):
        name_tag = container.select_one('[data-qa="author-name"]')
        name = _text(name_tag)
        if not name:
            continue
        affiliations = [
            _text(aff)
            for aff in container.select('[data-qa="author-affiliation"], [data-qa="author-affiliations"]')
            if _text(aff)
        ]
        authors.append(ScienceDirectAuthor(name=name, affiliations=affiliations))
    if authors:
        return authors, "dom"
    meta_authors = _parse_meta_authors(soup)
    if meta_authors:
        return meta_authors, "meta"
    return None, None


def _parse_meta_authors(soup: BeautifulSoup) -> list[ScienceDirectAuthor]:
    names = [
        content
        for tag in soup.find_all("meta", attrs={"name": "citation_author"})
        if (content := _attr_str(tag, "content"))
    ]
    institutions = [
        content
        for tag in soup.find_all("meta", attrs={"name": "citation_author_institution"})
        if (content := _attr_str(tag, "content"))
    ]
    authors: list[ScienceDirectAuthor] = []
    for name, insta in zip_longest(names, institutions, fillvalue=""):
        if not name:
            continue
        affiliations = _split_multi(insta)
        authors.append(ScienceDirectAuthor(name=name, affiliations=affiliations))
    return authors


def _extract_publication_date(soup: BeautifulSoup) -> tuple[str | None, Literal["dom", "meta"] | None]:
    dom_candidate = soup.select_one('[data-qa="publication-date"], time[data-qa], div[data-qa="publication"]')
    if dom_candidate:
        parsed = _parse_date(_text(dom_candidate))
        if parsed:
            return parsed, "dom"
    value, source = _meta_content(soup, ["citation_publication_date", "prism.publicationDate"])
    if value:
        parsed = _parse_date(value)
        if parsed:
            return parsed, source
    return None, None


def _parse_date(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        parsed = date_parser.parse(cleaned, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    return parsed.date().isoformat()


def _extract_abstract(soup: BeautifulSoup) -> tuple[str | None, Literal["dom", "meta"] | None]:
    container = soup.select_one('[data-qa="abstract-text"], section#abstracts div')
    if container:
        paragraphs = [_text(block) for block in container.find_all(["p", "li"]) if _text(block)]
        if not paragraphs:
            paragraphs = [_text(container)]
        joined = "\n\n".join(paragraphs).strip()
        if joined:
            return joined, "dom"
    return _meta_content(soup, ["citation_abstract"])


def _extract_keywords(soup: BeautifulSoup) -> tuple[list[str] | None, Literal["dom", "meta"] | None]:
    keywords = [_text(node) for node in soup.select('[data-qa="keyword"], .keyword-chip') if _text(node)]
    if keywords:
        return keywords, "dom"
    meta_keywords = []
    for tag in soup.find_all("meta", attrs={"name": "citation_keywords"}):
        meta_keywords.extend(_split_multi(_attr_str(tag, "content")))
    if meta_keywords:
        return meta_keywords, "meta"
    return None, None


def _extract_highlights(soup: BeautifulSoup) -> tuple[list[str] | None, Literal["dom"] | None]:
    items = [_text(node) for node in soup.select('[data-qa="highlight-item"], section[data-qa="highlights"] li') if _text(node)]
    if items:
        return items, "dom"
    return None, None


def _extract_pdf_url(soup: BeautifulSoup, url: str | None, pii: str | None) -> tuple[str | None, Literal["dom", "meta", "inferred"] | None]:
    link = soup.select_one('a[data-qa="download-pdf"], a[href*="/pdfft"], a[href*="/pdf"]')
    href = _attr_str(link, "href") if link else None
    if href:
        return urljoin(url or SCID_BASE_URL, href), "dom"
    pdf_meta, source = _meta_content(soup, ["citation_pdf_url"])
    if pdf_meta:
        return pdf_meta, source
    if pii:
        inferred = f"{SCID_BASE_URL}/science/article/pii/{pii}/pdf?isDTMRedir=true"
        return inferred, "inferred"
    return None, None


def _meta_content(
    soup: BeautifulSoup,
    names: Sequence[str],
) -> tuple[str | None, Literal["meta"] | None]:
    for name in names:
        tag = soup.find("meta", attrs={"name": name})
        if tag:
            content = _attr_str(tag, "content")
            if content:
                return content, "meta"
    return None, None


def _split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [piece.strip() for piece in re.split(r"[;,]", value) if piece.strip()]
    return parts


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    text = " ".join(list(node.stripped_strings))
    return text.strip()


def _attr_str(tag: Tag | None, attr: str) -> str | None:
    if tag is None:
        return None
    raw = tag.get(attr)
    if isinstance(raw, str):
        return raw.strip()
    return None
