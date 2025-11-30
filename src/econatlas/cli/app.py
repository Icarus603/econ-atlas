"""
Typer CLI 入口：提供全量抓取、按出版商抓取，以及样本采集/清单。
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Literal, Optional, cast

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
LOGGER = logging.getLogger(__name__)


def main() -> None:
    """允许 `python -m econatlas` 执行。"""
    app()


@crawl_app.callback(invoke_without_command=True)
def crawl(
    ctx: typer.Context,
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    output_dir: Path = typer.Option(Path("data"), help="期刊 JSON 输出目录。"),
    once: bool = typer.Option(False, "--once", help="仅运行一次后退出。"),
    interval: str = typer.Option("7d", help="运行间隔，例如 12h、2d，--once 时忽略。"),
    interval_seconds: Optional[int] = typer.Option(
        None,
        help="直接传入秒数，覆盖 --interval。",
    ),
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
    resume: bool = typer.Option(
        False,
        "--resume",
        help="使用进度文件断点续跑（按 slug 跳过已完成并在成功后写回进度）。",
    ),
    resume_path: Path = typer.Option(
        Path(".cache/crawl_progress.json"),
        help="进度文件路径（配合 --resume 生效）。",
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
            interval_text=interval,
            interval_seconds=interval_seconds,
            run_once=once,
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
        resume=resume,
        resume_path=resume_path if resume else None,
    )
    _print_report(report)
    raise typer.Exit(code=0 if not report.had_errors else 1)


@crawl_app.command("publisher")
def crawl_publisher(
    source: str = typer.Argument(..., help="出版商来源，如 sciencedirect/oxford/cambridge 等。"),
    list_path: Path = typer.Option(Path("list.csv"), exists=True, help="期刊列表 CSV 路径。"),
    output_dir: Path = typer.Option(Path("data"), help="期刊 JSON 输出目录。"),
    once: bool = typer.Option(True, "--once", help="默认只跑一轮；如需循环可指定 --once false。"),
    interval: str = typer.Option("7d", help="循环间隔，仅当 --once false 时有效。"),
    interval_seconds: Optional[int] = typer.Option(None, help="覆盖 --interval 的秒数。"),
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
    resume: bool = typer.Option(
        False,
        "--resume",
        help="使用进度文件断点续跑（按 slug 跳过已完成并在成功后写回进度）。",
    ),
    resume_path: Path = typer.Option(
        Path(".cache/crawl_progress.json"),
        help="进度文件路径（配合 --resume 生效）。",
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
            interval_text=interval,
            interval_seconds=interval_seconds,
            run_once=once,
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
        resume=resume,
        resume_path=resume_path if resume else None,
    )
    _print_report(report)
    raise typer.Exit(code=0 if not report.had_errors else 1)


app.add_typer(crawl_app, name="crawl")
app.add_typer(samples_app, name="samples")


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
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def _load_completed_slugs(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(item) for item in data}
    except FileNotFoundError:
        return set()
    except Exception:
        LOGGER.debug("读取进度文件失败 %s", path, exc_info=True)
    return set()


def _save_completed_slugs(path: Path, slugs: set[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(slugs), ensure_ascii=False, indent=2), encoding="utf-8")
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
    resume: bool = False,
    resume_path: Path | None = None,
) -> RunReport:
    started = datetime.now(timezone.utc)
    results: list[JournalRunResult] = []
    errors: list[str] = []
    completed_slugs: set[str] = set()
    if resume and resume_path:
        completed_slugs = _load_completed_slugs(resume_path)

    scd_crawler = ScienceDirect爬虫(feed_client, scd_api_key, scd_inst_token)
    oxford_crawler = Oxford爬虫(feed_client)
    cambridge_crawler = Cambridge爬虫(feed_client)
    cnki_crawler = CNKI爬虫(feed_client)
    nber_crawler = NBER爬虫(feed_client)
    wiley_crawler = Wiley爬虫(feed_client)
    chicago_crawler = Chicago爬虫(feed_client)
    informs_crawler = Informs爬虫(feed_client)

    for journal in journals:
        if resume and resume_path and journal.slug in completed_slugs:
            LOGGER.info("跳过已完成 %s（resume）", journal.slug)
            continue
        try:
            records = _crawl_with_dispatch(
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
            )
            base_store = store.persist(journal, records)
            if skip_translation:
                results.append(
                    JournalRunResult(
                        journal=journal,
                        fetched=len(records),
                        added=base_store.added,
                        updated=base_store.updated,
                        translation_attempts=0,
                        translation_failures=0,
                    )
                )
                continue

            translated_records, attempts, failures = _translate_records(records, translator, skip_translation)
            trans_store = store.persist(journal, translated_records)
            results.append(
                JournalRunResult(
                    journal=journal,
                    fetched=len(records),
                    added=base_store.added,
                    updated=base_store.updated + trans_store.updated,
                    translation_attempts=attempts,
                    translation_failures=failures,
                )
            )
            if resume and resume_path:
                completed_slugs.add(journal.slug)
                _save_completed_slugs(resume_path, completed_slugs)
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


def _crawl_with_dispatch(
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
) -> list[ArticleRecord]:
    if journal.source_type == "cnki":
        return cast(list[ArticleRecord], cnki_crawler.crawl(journal))
    if journal.source_type == "sciencedirect":
        return cast(list[ArticleRecord], scd_crawler.crawl(journal))
    if journal.source_type == "oxford":
        return cast(list[ArticleRecord], oxford_crawler.crawl(journal))
    if journal.source_type == "cambridge":
        return cast(list[ArticleRecord], cambridge_crawler.crawl(journal))
    if journal.source_type == "nber":
        return cast(list[ArticleRecord], nber_crawler.crawl(journal))
    if journal.source_type == "wiley":
        return cast(list[ArticleRecord], wiley_crawler.crawl(journal))
    if journal.source_type == "chicago":
        return cast(list[ArticleRecord], chicago_crawler.crawl(journal))
    if journal.source_type == "informs":
        return cast(list[ArticleRecord], informs_crawler.crawl(journal))
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
        if not summary or (language and language.startswith("zh")):
            translated.append(record)
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
