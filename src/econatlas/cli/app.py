"""
Typer CLI 入口：提供全量抓取、按出版商抓取，以及样本采集/清单。
"""

from __future__ import annotations

import csv
import html
import json
import logging
import shutil
import os
import time
import http.server
import functools
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, cast
from urllib.parse import quote_plus, urlparse

import typer
from dotenv import load_dotenv
from slugify import slugify


from econatlas.config import SettingsError, build_settings
from econatlas.models import ArticleRecord, TranslationRecord, JournalSource
from econatlas.feeds import FeedClient, JournalListLoader, ALLOWED_SOURCE_TYPES
from econatlas.crawlers import (
    ScienceDirect爬虫,
    Oxford爬虫,
    Cambridge爬虫,
    CNKI爬虫,
    NBER爬虫,
    Wiley爬虫,
    Chicago爬虫,
    Informs爬虫,
)

from econatlas.storage import JournalStore
from econatlas.translation import (
    Translator,
    TranslationResult,
    skipped_translation,
    detect_language,
    NoOpTranslator,
    DeepSeekTranslator,
)
from econatlas.samples import (
    SampleCollector,
    SampleCollectorReport,
    build_inventory,
)


@dataclass
class JournalRunResult:
    journal: JournalSource
    fetched: int
    added: int
    updated: int
    translation_attempts: int
    translation_failures: int
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass
class RunReport:
    started_at: datetime
    finished_at: datetime
    results: list[JournalRunResult]
    errors: list[str]

    @property
    def total_new_entries(self) -> int:
        return sum(result.added for result in self.results if result.error is None)

    @property
    def total_translation_failures(self) -> int:
        return sum(result.translation_failures for result in self.results if result.error is None)

    @property
    def had_errors(self) -> bool:
        return bool(self.errors or any(not r.succeeded for r in self.results))

app = typer.Typer(help="econ-atlas CLI")
crawl_app = typer.Typer(help="运行 RSS 抓取")
samples_app = typer.Typer(help="采集/导入/清点 HTML 样本")
viewer_app = typer.Typer(help="本地静态查看器（浏览 data/*.json）")
LOGGER = logging.getLogger(__name__)


def main() -> None:
    """允许 `python -m econatlas` 执行。"""
    app()


@crawl_app.callback(invoke_without_command=True)
def crawl(
    ctx: typer.Context,
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    output_dir: Path = typer.Option(Path("data"), help="期刊 JSON 输出目录。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="开启详细日志。"),
    include_source: Optional[list[str]] = typer.Option(
        None,
        "--include-source",
        "-s",
        help="仅抓取指定来源类型。",
    ),
    include_slug: Optional[list[str]] = typer.Option(
        None,
        "--include-slug",
        "-j",
        help="仅抓取指定 slug（对应 data/<slug>.json）。",
    ),
    skip_translation: bool = typer.Option(
        False,
        "--skip-translation",
        help="跳过翻译以提升速度。",
    ),
    progress_path: Path = typer.Option(
        Path(".cache/crawl_progress.json"),
        help="进度文件路径，默认开启断点续跑。",
    ),
) -> None:
    """全量抓取入口。"""
    if ctx.invoked_subcommand:
        # 被子命令调用时直接返回，避免重复执行父命令逻辑。
        return
    _configure_logging(verbose)
    load_dotenv()
    source_filter = _normalize_crawl_sources(include_source)
    slug_filter = _normalize_slug_filter(include_slug)
    try:
        settings = build_settings(
            list_path=list_path,
            output_dir=output_dir,
            include_slugs=slug_filter,
            include_sources=source_filter,
            skip_translation=skip_translation,
        )
    except SettingsError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if not settings.elsevier_api_key:
        typer.secho(
            "[ScienceDirect] 缺少 ELSEVIER_API_KEY，将跳过 API 增强。",
            fg=typer.colors.YELLOW,
        )

    translator: NoOpTranslator | DeepSeekTranslator
    if settings.skip_translation:
        translator = NoOpTranslator()
    else:
        assert settings.deepseek_api_key is not None
        translator = DeepSeekTranslator(api_key=settings.deepseek_api_key)

    journals = JournalListLoader(settings.list_path).load()
    if settings.include_sources:
        journals = [j for j in journals if j.source_type in settings.include_sources]
    if settings.include_slugs:
        journals = [j for j in journals if j.slug in settings.include_slugs]
    if not journals:
        typer.secho("无匹配的期刊可抓取。", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    feed_client = FeedClient()
    store = JournalStore(settings.output_dir)
    report = _run_once(
        journals=journals,
        feed_client=feed_client,
        translator=translator,
        store=store,
        scd_api_key=settings.elsevier_api_key,
        scd_inst_token=settings.elsevier_inst_token,
        skip_translation=settings.skip_translation,
        progress_path=progress_path,
    )
    _print_report(report)
    # 默认自动更新本地查看器索引，避免用户手动执行 viewer build。
    try:
        _build_viewer_index(list_path=settings.list_path, data_dir=settings.output_dir, viewer_dir=Path("viewer"))
    except Exception:
        LOGGER.debug("生成 viewer/index.json 失败", exc_info=True)
    raise typer.Exit(code=0 if not report.had_errors else 1)


@crawl_app.command("publisher")
def crawl_publisher(
    source: str = typer.Argument(..., help="出版商来源，如 sciencedirect/oxford/cambridge 等。"),
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    output_dir: Path = typer.Option(Path("data"), help="期刊 JSON 输出目录。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="开启详细日志。"),
    include_slug: Optional[list[str]] = typer.Option(
        None,
        "--include-slug",
        "-j",
        help="仅抓取指定 slug。",
    ),
    skip_translation: bool = typer.Option(
        False,
        "--skip-translation",
        help="跳过翻译以提升速度。",
    ),
    progress_path: Path = typer.Option(
        Path(".cache/crawl_progress.json"),
        help="进度文件路径，默认开启断点续跑。",
    ),
) -> None:
    """按单一出版商运行抓取。"""
    normalized_source = source.strip().lower()
    if normalized_source not in ALLOWED_SOURCE_TYPES:
        typer.secho(f"未知来源类型: {normalized_source}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    _configure_logging(verbose)
    load_dotenv()
    slug_filter = _normalize_slug_filter(include_slug)
    try:
        settings = build_settings(
            list_path=list_path,
            output_dir=output_dir,
            include_slugs=slug_filter,
            include_sources={normalized_source},
            skip_translation=skip_translation,
        )
    except SettingsError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if not settings.elsevier_api_key and normalized_source == "sciencedirect":
        typer.secho(
            "[ScienceDirect] 缺少 ELSEVIER_API_KEY，将跳过 API 增强。",
            fg=typer.colors.YELLOW,
        )

    translator: NoOpTranslator | DeepSeekTranslator
    if settings.skip_translation:
        translator = NoOpTranslator()
    else:
        assert settings.deepseek_api_key is not None
        translator = DeepSeekTranslator(api_key=settings.deepseek_api_key)

    journals = JournalListLoader(settings.list_path).load()
    journals = [j for j in journals if j.source_type == normalized_source]
    if settings.include_slugs:
        journals = [j for j in journals if j.slug in settings.include_slugs]
    if not journals:
        typer.secho("无匹配的期刊可抓取。", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    feed_client = FeedClient()
    store = JournalStore(settings.output_dir)
    report = _run_once(
        journals=journals,
        feed_client=feed_client,
        translator=translator,
        store=store,
        scd_api_key=settings.elsevier_api_key,
        scd_inst_token=settings.elsevier_inst_token,
        skip_translation=settings.skip_translation,
        progress_path=progress_path,
    )
    _print_report(report)
    # 默认自动更新本地查看器索引，避免用户手动执行 viewer build。
    try:
        _build_viewer_index(list_path=settings.list_path, data_dir=settings.output_dir, viewer_dir=Path("viewer"))
    except Exception:
        LOGGER.debug("生成 viewer/index.json 失败", exc_info=True)
    raise typer.Exit(code=0 if not report.had_errors else 1)


app.add_typer(crawl_app, name="crawl")
app.add_typer(samples_app, name="samples")
app.add_typer(viewer_app, name="viewer")


@samples_app.command("collect")
def collect_samples(
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    output_dir: Path = typer.Option(Path("samples"), help="样本输出目录。"),
    limit: int = typer.Option(3, min=1, help="每个期刊采集的条目上限。"),
    include_source: Optional[list[str]] = typer.Option(
        None,
        "--include-source",
        "-s",
        help="限制采集的来源类型（默认排除 cnki）。",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="开启详细日志。"),
    sciencedirect_debug: bool = typer.Option(
        False,
        "--sdir-debug",
        help="采集 ScienceDirect 时保存调试截图/trace。",
    ),
) -> None:
    """下载 HTML 样本。"""
    _configure_logging(verbose)
    load_dotenv(dotenv_path=".env", override=True)
    journals = JournalListLoader(list_path).load()
    include = _resolve_include_sources(include_source)
    filtered = [journal for journal in journals if journal.source_type in include]
    if not filtered:
        typer.secho("未匹配到指定来源的期刊。", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    collector = SampleCollector(feed_client=FeedClient(), sciencedirect_debug=sciencedirect_debug)
    report = collector.collect(filtered, limit_per_journal=limit, output_dir=output_dir)
    _print_sample_summary(report)
    if report.failures:
        raise typer.Exit(code=1)


@samples_app.command("import")
def import_sample(
    source_type: str = typer.Argument(..., help="来源目录名，例如 sciencedirect。"),
    journal_slug: str = typer.Argument(..., help="期刊 slug（与 list.csv 对应）。"),
    input_file: Path = typer.Argument(..., exists=True, readable=True, help="要导入的 HTML/JSON 样本。"),
    output_dir: Path = typer.Option(Path("samples"), help="样本存放目录。"),
    entry_id: Optional[str] = typer.Option(
        None,
        "--entry-id",
        help="可选标识符，用于重命名文件（会 slugify，保留扩展名）。",
    ),
) -> None:
    """导入手工采集的 HTML/JSON 样本。"""
    filename = input_file.name
    if entry_id:
        safe = slugify(entry_id, lowercase=True, separator="-") or "entry"
        filename = f"{safe}{input_file.suffix}"
    destination = output_dir / source_type / journal_slug
    destination.mkdir(parents=True, exist_ok=True)
    target_path = destination / filename
    shutil.copyfile(input_file, target_path)
    typer.echo(f"已导入 {input_file} -> {target_path}")


@samples_app.command("inventory")
def inventory_samples(
    samples_dir: Path = typer.Option(Path("samples"), help="样本目录。"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="可选输出文件（默认 stdout）。"
    ),
    output_format: Literal["json", "csv"] = typer.Option(
        "json", "--format", help="清单输出格式。", case_sensitive=False
    ),
    pretty: bool = typer.Option(False, "--pretty", help="JSON 是否缩进。"),
) -> None:
    """汇总样本目录。"""
    inventories = build_inventory(samples_dir)
    if not inventories:
        typer.secho("未找到样本。请先运行 `samples collect`。", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    content = _render_inventory(inventories, fmt=output_format.lower(), pretty=pretty)
    if output:
        output.write_text(content, encoding="utf-8")
    else:
        typer.echo(content)


def _render_inventory(inventories: list[Any], fmt: str, pretty: bool) -> str:
    if fmt == "csv":
        buffer = StringIO()
        fieldnames = [
            "source_type",
            "source_total_samples",
            "source_latest_fetched_at",
            "notes",
            "journal_slug",
            "journal_sample_count",
            "journal_latest_fetched_at",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for source in inventories:
            for journal in source.journals:
                writer.writerow(
                    {
                        "source_type": source.source_type,
                        "source_total_samples": source.total_samples,
                        "source_latest_fetched_at": source.latest_fetched_at.isoformat() if source.latest_fetched_at else "",
                        "notes": source.notes or "",
                        "journal_slug": journal.slug,
                        "journal_sample_count": journal.sample_count,
                        "journal_latest_fetched_at": journal.latest_fetched_at.isoformat() if journal.latest_fetched_at else "",
                    }
                )
        return buffer.getvalue().strip()

    payload = [source.to_dict() for source in inventories]
    return json.dumps(payload, indent=2 if pretty else None)


def _normalize_crawl_sources(include_source: Optional[list[str]]) -> set[str] | None:
    if not include_source:
        return set(ALLOWED_SOURCE_TYPES)
    normalized = {value.strip().lower() for value in include_source if value and value.strip()}
    invalid = normalized - ALLOWED_SOURCE_TYPES
    if invalid:
        invalid_str = ", ".join(sorted(invalid))
        raise typer.BadParameter(f"Invalid source types: {invalid_str}")
    return normalized or None


def _resolve_include_sources(include_source: Optional[list[str]]) -> set[str]:
    include = {value.lower() for value in include_source} if include_source else None
    if include:
        invalid = include - ALLOWED_SOURCE_TYPES
        if invalid:
            invalid_str = ", ".join(sorted(invalid))
            raise typer.BadParameter(f"Invalid source types: {invalid_str}")
        return include
    return {value for value in ALLOWED_SOURCE_TYPES if value != "cnki"}


def _normalize_slug_filter(include_slug: Optional[list[str]]) -> set[str] | None:
    if not include_slug:
        return None
    normalized = {value.strip().lower() for value in include_slug if value and value.strip()}
    return normalized or None


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
        force=True,  # 确保覆盖已有 handler，避免日志静默
    )


def _load_progress(path: Path) -> tuple[dict[str, set[str]], set[str]]:
    """
    返回 (per_entry, legacy_completed_slugs)。
    per_entry: slug -> 已处理 entry.id 集合。
    legacy_completed_slugs: 兼容旧版仅记录 slug 的进度文件。
    """
    per_entry: dict[str, set[str]] = {}
    legacy_completed_slugs: set[str] = set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            legacy_completed_slugs = {str(item) for item in data}
        elif isinstance(data, dict):
            raw_entries = data.get("completed_entries", {}) if isinstance(data.get("completed_entries", {}), dict) else {}
            per_entry = {slug: {str(item) for item in items or []} for slug, items in raw_entries.items()}
            legacy_raw = data.get("completed_slugs", [])
            if isinstance(legacy_raw, list):
                legacy_completed_slugs = {str(item) for item in legacy_raw}
    except FileNotFoundError:
        return per_entry, legacy_completed_slugs
    except Exception:
        LOGGER.debug("读取进度文件失败 %s", path, exc_info=True)
    return per_entry, legacy_completed_slugs


def _save_progress(path: Path, per_entry: dict[str, set[str]]) -> None:
    payload = {"completed_entries": {slug: sorted(entries) for slug, entries in per_entry.items()}}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        LOGGER.debug("写入进度文件失败 %s", path, exc_info=True)


def _run_once(
    *,
    journals: list[JournalSource],
    feed_client: FeedClient,
    translator: Translator,
    store: JournalStore,
    scd_api_key: str | None,
    scd_inst_token: str | None,
    skip_translation: bool,
    progress_path: Path,
) -> RunReport:
    started = datetime.now(timezone.utc)
    results: list[JournalRunResult] = []
    errors: list[str] = []
    per_entry_progress, legacy_completed_slugs = _load_progress(progress_path)

    scd_crawler = ScienceDirect爬虫(feed_client, scd_api_key, scd_inst_token)
    oxford_crawler = Oxford爬虫(feed_client)
    cambridge_crawler = Cambridge爬虫(feed_client)
    cnki_crawler = CNKI爬虫(feed_client)
    nber_crawler = NBER爬虫(feed_client)
    wiley_crawler = Wiley爬虫(feed_client)
    chicago_crawler = Chicago爬虫(feed_client)
    informs_crawler = Informs爬虫(feed_client)

    for journal in journals:
        if journal.slug in legacy_completed_slugs:
            LOGGER.info("跳过已完成 %s（来自旧版进度文件）", journal.slug)
            continue
        completed_entries = set(per_entry_progress.get(journal.slug, set()))
        store.ensure_archive(journal)
        # 防止进度文件与存档不一致：若存档里缺少标记为完成的条目，则重新抓取这些缺失条目。
        try:
            archive = store._load_archive(journal)  # pragma: no cover
            archived_ids = {entry.id for entry in archive.entries}
            missing = completed_entries - archived_ids
            if missing:
                LOGGER.info("检测到进度与存档不一致，重新抓取 %s 缺失的 %d 条", journal.slug, len(missing))
                completed_entries -= missing
                if completed_entries:
                    per_entry_progress[journal.slug] = completed_entries
                else:
                    per_entry_progress.pop(journal.slug, None)
        except Exception:
            LOGGER.debug("校验存档与进度失败 %s", journal.slug, exc_info=True)
        try:
            LOGGER.info("开始 %s", journal.name)
            fetched_total = 0
            added_total = 0
            updated_total = 0
            translation_attempts = 0
            translation_failures = 0

            for record in _stream_records(
                journal,
                scd_crawler=scd_crawler,
                oxford_crawler=oxford_crawler,
                cambridge_crawler=cambridge_crawler,
                cnki_crawler=cnki_crawler,
                nber_crawler=nber_crawler,
                wiley_crawler=wiley_crawler,
                chicago_crawler=chicago_crawler,
                informs_crawler=informs_crawler,
                feed_client=feed_client,
            ):
                fetched_total += 1
                if record.id in completed_entries:
                    LOGGER.info("%s | %s（已完成，跳过）", journal.name, record.title)
                    continue

                LOGGER.info("%s | %s", journal.name, record.title)
                base_store = store.persist(journal, [record])
                added_total += base_store.added
                updated_total += base_store.updated

                if skip_translation:
                    completed_entries.add(record.id)
                    per_entry_progress[journal.slug] = completed_entries
                    _save_progress(progress_path, per_entry_progress)
                    continue

                translated_records, attempts, failures = _translate_records(
                    [record], translator, skip_translation=False
                )
                translation_attempts += attempts
                translation_failures += failures
                trans_store = store.persist(journal, translated_records)
                updated_total += trans_store.updated

                completed_entries.add(record.id)
                per_entry_progress[journal.slug] = completed_entries
                _save_progress(progress_path, per_entry_progress)

            results.append(
                JournalRunResult(
                    journal=journal,
                    fetched=fetched_total,
                    added=added_total,
                    updated=updated_total,
                    translation_attempts=translation_attempts,
                    translation_failures=translation_failures,
                )
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"{journal.name}: {exc}"
            LOGGER.exception("处理失败 %s", journal.name)
            errors.append(msg)
            results.append(
                JournalRunResult(
                    journal=journal,
                    fetched=0,
                    added=0,
                    updated=0,
                    translation_attempts=0,
                    translation_failures=0,
                    error=str(exc),
                )
            )
    finished = datetime.now(timezone.utc)
    try:
        oxford_crawler.close()
    except Exception:
        LOGGER.debug("关闭 Oxford 爬虫失败", exc_info=True)
    return RunReport(started_at=started, finished_at=finished, results=results, errors=errors)


def _stream_records(
    journal: JournalSource,
    *,
    scd_crawler: Any,
    oxford_crawler: Any,
    cambridge_crawler: Any,
    cnki_crawler: Any,
    nber_crawler: Any,
    wiley_crawler: Any,
    chicago_crawler: Any,
    informs_crawler: Any,
    feed_client: FeedClient,
) -> Iterable[ArticleRecord]:
    def _iter_from(crawler: Any) -> Iterable[ArticleRecord]:
        iter_crawl = getattr(crawler, "iter_crawl", None)
        if callable(iter_crawl):
            return cast(Iterable[ArticleRecord], iter_crawl(journal))
        records = crawler.crawl(journal)
        if isinstance(records, list):
            return records
        return cast(Iterable[ArticleRecord], records)

    if journal.source_type == "cnki":
        return _iter_from(cnki_crawler)
    if journal.source_type == "sciencedirect":
        return _iter_from(scd_crawler)
    if journal.source_type == "oxford":
        return _iter_from(oxford_crawler)
    if journal.source_type == "cambridge":
        return _iter_from(cambridge_crawler)
    if journal.source_type == "nber":
        return _iter_from(nber_crawler)
    if journal.source_type == "wiley":
        return _iter_from(wiley_crawler)
    if journal.source_type == "chicago":
        return _iter_from(chicago_crawler)
    if journal.source_type == "informs":
        return _iter_from(informs_crawler)
    # 其他来源：仅用 FeedClient 构建基础记录
    entries = feed_client.fetch(journal.rss_url)
    records: list[ArticleRecord] = []
    for entry in entries:
        summary = entry.summary or ""
        language = detect_language(summary)
        translation_result = skipped_translation(summary)
        records.append(
            ArticleRecord(
                id=entry.entry_id,
                title=entry.title,
                link=entry.link,
                authors=list(entry.authors),
                published_at=entry.published_at,
                abstract_original=summary or None,
                abstract_language=language,
                abstract_zh=None,
                translation=TranslationRecord(
                    status=translation_result.status,
                    translator=translation_result.translator,
                    translated_at=translation_result.translated_at,
                    error=translation_result.error,
                ),
                fetched_at=datetime.now(timezone.utc),
            )
        )
    return records


def _translate_records(
    records: list[ArticleRecord],
    translator: Translator,
    skip_translation: bool,
) -> tuple[list[ArticleRecord], int, int]:
    if skip_translation:
        return records, 0, 0
    throttle_raw = os.getenv("TRANSLATION_THROTTLE_SECONDS")
    try:
        throttle_seconds = float(throttle_raw) if throttle_raw else 0.5
        if throttle_seconds < 0:
            throttle_seconds = 0.0
    except ValueError:
        throttle_seconds = 0.5
    attempts = 0
    translated: list[ArticleRecord] = []
    results: list[TranslationResult | None] = []
    failure_indices: list[int] = []
    for idx, record in enumerate(records):
        summary = record.abstract_original or ""
        language = record.abstract_language
        if not summary:
            translated.append(record)
            results.append(None)
            continue
        if language and language.startswith("zh"):
            # 中文摘要无需翻译：对用户展示为已具备中文摘要（success），且填充 abstract_zh。
            now = datetime.now(timezone.utc)
            translated.append(
                record.model_copy(
                    update={
                        "abstract_zh": record.abstract_zh or summary,
                        "translation": TranslationRecord(
                            status="success",
                            translator=None,
                            translated_at=now,
                            error=None,
                        ),
                    }
                )
            )
            results.append(None)
            continue
        if throttle_seconds:
            time.sleep(throttle_seconds)
        attempts += 1
        result: TranslationResult = translator.translate(summary, source_language=language or "unknown")
        results.append(result)
        if result.status == "failed":
            failure_indices.append(idx)
        translated.append(
            record.model_copy(
                update={
                    "abstract_zh": result.translated_text or record.abstract_zh,
                    "translation": TranslationRecord(
                        status=result.status,
                        translator=result.translator,
                        translated_at=result.translated_at,
                        error=result.error,
                    ),
                }
            )
        )
    if failure_indices:
        LOGGER.info("翻译失败 %d 条，开始补偿重试", len(failure_indices))
        for idx in failure_indices:
            record = records[idx]
            summary = record.abstract_original or ""
            language = record.abstract_language
            if throttle_seconds:
                time.sleep(throttle_seconds)
            attempts += 1
            retry_result: TranslationResult = translator.translate(summary, source_language=language or "unknown")
            results[idx] = retry_result
            translated[idx] = record.model_copy(
                update={
                    "abstract_zh": retry_result.translated_text or record.abstract_zh,
                    "translation": TranslationRecord(
                        status=retry_result.status,
                        translator=retry_result.translator,
                        translated_at=retry_result.translated_at,
                        error=retry_result.error,
                    ),
                }
            )
    failures = sum(1 for result in results if result and result.status == "failed")
    return translated, attempts, failures


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
            f"  - {result.journal.name}: fetched={result.fetched}, added={result.added}, "
            f"updated={result.updated}, translations={result.translation_attempts}, "
            f"translation_failures={result.translation_failures} [{status}]"
        )
    if report.errors:
        typer.secho("Errors:", fg=typer.colors.RED)
        for message in report.errors:
            typer.secho(f"  * {message}", fg=typer.colors.RED)


def _print_sample_summary(report: SampleCollectorReport) -> None:
    summary = (
        f"Journals: {len(report.results)} | HTML files saved: {report.total_saved} | Failures: {len(report.failures)}"
    )
    if report.total_browser_attempts:
        summary += (
            f" | Browser successes: {report.total_browser_successes}/{report.total_browser_attempts}"
            f" | Browser failures: {report.total_browser_failures}"
        )
    typer.echo(summary)
    for result in report.results:
        status = "ok"
        if result.errors:
            status = "failed: " + "; ".join(result.errors)
        browser_note = ""
        if result.browser_attempts:
            browser_note = (
                f" (browser ok={result.browser_successes}, failed={result.browser_failures}, attempts={result.browser_attempts})"
            )
        typer.echo(
            f"  - {result.journal.name} [{result.journal.source_type}] saved={len(result.saved_files)} [{status}]{browser_note}"
        )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@viewer_app.command("build")
def build_viewer_index(
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    data_dir: Path = typer.Option(Path("data"), help="抓取输出目录（包含 *.json）。"),
    viewer_dir: Path = typer.Option(Path("viewer"), help="查看器目录（写入 index.json）。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="开启详细日志。"),
) -> None:
    """生成 viewer/index.json，供浏览器快速加载期刊清单与统计。"""
    _configure_logging(verbose)
    path = _build_viewer_index(
        list_path=list_path,
        data_dir=data_dir,
        viewer_dir=viewer_dir,
    )
    typer.echo(f"已生成 {path}")


@viewer_app.command("fix-cnki-links")
def fix_cnki_links(
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    data_dir: Path = typer.Option(Path("data"), help="抓取输出目录（包含 *.json）。"),
    apply: bool = typer.Option(False, "--apply", help="写回 data/*.json（默认仅统计/预览）。"),
) -> None:
    """将 CNKI 条目中可能过期的 `kcms2/article/abstract?v=...` 链接替换为 CNKI 搜索链接。"""
    journals = JournalListLoader(list_path).load()
    store = JournalStore(data_dir)
    total_archives = 0
    total_changed = 0

    for journal in journals:
        if journal.source_type != "cnki":
            continue
        archive_path = store.archive_path(journal)
        if not archive_path.exists():
            continue
        total_archives += 1
        try:
            archive = json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            typer.secho(f"读取失败 {archive_path}: {exc}", fg=typer.colors.YELLOW)
            continue
        if not isinstance(archive, dict):
            continue
        entries = archive.get("entries")
        if not isinstance(entries, list):
            continue

        changed = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            link = entry.get("link")
            title = entry.get("title")
            if not isinstance(link, str) or not isinstance(title, str):
                continue
            if not _looks_like_cnki_ephemeral_link(link):
                continue
            replacement = _cnki_search_url(title)
            if not replacement or replacement == link:
                continue
            entry["link"] = replacement
            changed += 1

        if not changed:
            continue
        total_changed += changed
        typer.echo(f"{archive_path}: {changed} links {'updated' if apply else 'would update'}")
        if apply:
            archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")

    typer.echo(
        f"CNKI archives scanned: {total_archives}; links {'updated' if apply else 'matched'}: {total_changed}"
    )


def _looks_like_cnki_ephemeral_link(link: str) -> bool:
    raw = (link or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    if not parsed.hostname or not parsed.hostname.endswith(".cnki.net"):
        return False
    if not parsed.path.startswith("/kcms2/article/abstract"):
        return False
    return "v=" in (parsed.query or "")


def _cnki_search_url(title: str) -> str:
    query = (title or "").strip()
    if not query:
        return ""
    normalized = html.unescape(query).strip()
    return f"https://kns.cnki.net/kns8/defaultresult/index?kw={quote_plus(normalized)}"


@viewer_app.command("serve")
def serve_viewer(
    port: int = typer.Option(8765, "--port", "-p", min=1, max=65535, help="监听端口。"),
    bind: str = typer.Option("127.0.0.1", "--bind", help="监听地址（建议仅本机）。"),
    root: Path = typer.Option(Path("."), "--root", help="HTTP 根目录（包含 viewer/ 和 data/）。"),
) -> None:
    """启动本地静态服务器，用于打开 viewer/（需要通过 http:// 访问）。"""
    root = root.expanduser().resolve()
    if not (root / "viewer").exists():
        typer.secho(f"未找到 viewer 目录：{root / 'viewer'}", fg=typer.colors.YELLOW)

    # 默认自动生成/更新索引，避免 index.json 缺失或路径不一致导致 404。
    try:
        _build_viewer_index(
            list_path=root / "list.csv",
            data_dir=root / "data",
            viewer_dir=root / "viewer",
        )
    except Exception as exc:  # noqa: BLE001
        typer.secho(
            f"自动生成 viewer/index.json 失败：{exc}",
            fg=typer.colors.YELLOW,
        )

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer((bind, port), handler)
    url = f"http://{bind}:{port}/viewer/"
    typer.echo(f"Serving {root} at {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _build_viewer_index(*, list_path: Path, data_dir: Path, viewer_dir: Path) -> Path:
    root_dir = viewer_dir.expanduser().resolve().parent
    journals = JournalListLoader(list_path).load()
    store = JournalStore(data_dir)

    items: list[dict[str, Any]] = []
    for journal in journals:
        archive_path = store.archive_path(journal)
        if not archive_path.exists():
            continue
        try:
            archive = json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("读取失败 %s: %s", archive_path, exc)
            continue

        journal_node = archive.get("journal", {}) if isinstance(archive, dict) else {}
        entries = archive.get("entries", []) if isinstance(archive, dict) else []
        if not isinstance(entries, list):
            entries = []

        translation_counts = {"success": 0, "failed": 0, "skipped": 0}
        latest_published: datetime | None = None
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            trans = entry.get("translation", {})
            status = trans.get("status") if isinstance(trans, dict) else None
            lang = entry.get("abstract_language")
            if isinstance(lang, str) and lang.startswith("zh"):
                translation_counts["success"] += 1
            elif status in translation_counts:
                translation_counts[cast(str, status)] += 1
            published_at = _parse_iso_datetime(cast(Optional[str], entry.get("published_at")))
            if published_at and (latest_published is None or published_at > latest_published):
                latest_published = published_at

        last_run_at = _parse_iso_datetime(cast(Optional[str], journal_node.get("last_run_at")))
        resolved_archive = archive_path.expanduser().resolve()
        archive_rel: Path
        try:
            archive_rel = resolved_archive.relative_to(root_dir)
        except ValueError:
            try:
                data_rel = resolved_archive.relative_to(data_dir.expanduser().resolve())
                archive_rel = Path(data_dir.name) / data_rel
            except ValueError:
                archive_rel = Path(data_dir.name) / resolved_archive.name

        items.append(
            {
                "name": journal_node.get("name") or journal.name,
                "slug": journal.slug,
                "source_type": journal.source_type,
                "entry_count": len(entries),
                "last_run_at": last_run_at.isoformat() if last_run_at else None,
                "latest_published_at": latest_published.isoformat() if latest_published else None,
                "translation": translation_counts,
                "archive_path": archive_rel.as_posix(),
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "journals": sorted(items, key=lambda x: (str(x.get("source_type", "")), str(x.get("name", "")))),
    }
    viewer_dir.mkdir(parents=True, exist_ok=True)
    path = viewer_dir / "index.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
