const INDEX_URL = "./index.json";

const elements = {
  search: document.getElementById("search"),
  sourceFilter: document.getElementById("sourceFilter"),
  statusFilter: document.getElementById("statusFilter"),
  refresh: document.getElementById("refresh"),
  stats: document.getElementById("stats"),
  hint: document.getElementById("hint"),
  journalList: document.getElementById("journalList"),
  mainTitle: document.getElementById("mainTitle"),
  mainMeta: document.getElementById("mainMeta"),
  entries: document.getElementById("entries"),
  detail: document.getElementById("detail"),
};

/** @typedef {{ archive_path: string, name: string, slug: string, source_type: string, entry_count: number, last_run_at: string|null, latest_published_at: string|null, translation: {success:number, failed:number, skipped:number}}} JournalIndexItem */
/** @typedef {{ journals: JournalIndexItem[], generated_at: string }} ViewerIndex */

/** @type {ViewerIndex|null} */
let viewerIndex = null;
/** @type {JournalIndexItem|null} */
let activeJournal = null;
/** @type {any|null} */
let activeArchive = null;
/** @type {string|null} */
let activeEntryId = null;

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, { year: "numeric", month: "2-digit", day: "2-digit" });
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function decodeHtmlEntities(text) {
  const value = String(text || "");
  if (!value) return "";
  const textarea = document.createElement("textarea");
  textarea.innerHTML = value;
  return textarea.value;
}

function stripHtmlPreserveBreaks(text) {
  const value = String(text || "");
  if (!value) return "";
  const withBreaks = value
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*p\s*>/gi, "\n\n")
    .replace(/<\s*p(\s+[^>]*)?>/gi, "");
  const container = document.createElement("div");
  container.innerHTML = withBreaks;
  return (container.textContent || "").replaceAll(/\n{3,}/g, "\n\n").trim();
}

function normalizeText(text) {
  const decoded = decodeHtmlEntities(text);
  return stripHtmlPreserveBreaks(decoded);
}

function formatAbstract(text, language) {
  const lang = String(language || "");
  let value = normalizeText(text || "");
  if (!value) return "";
  value = value.replace(/\r\n/g, "\n").trim();

  // Strip common heading prefixes.
  // Handles plain text ("Abstract ..."), glued text after stripping HTML ("AbstractWe ..."),
  // and common Chinese prefixes ("摘要：", "【摘要】").
  for (let i = 0; i < 3; i += 1) {
    const before = value;
    value = value
      .replace(/^\s*(abstract|summary)\s*[:：\-–]?\s*/i, "")
      .replace(/^\s*(摘要|【摘要】|\[摘要\])\s*[:：\-–]?\s*/u, "");
    if (value === before) break;
  }

  // Remove trailing keyword/classification blocks (keep the abstract itself).
  const cutoffMatchers = [
    /\n\s*(keywords?|key\s*words?)\s*[:：]/i,
    /\n\s*(jel\s*(codes?)?|jel\s*classification)\s*[:：]/i,
    /\n\s*(关键词|关键字|jel分类号|中图分类号)\s*[:：]/u,
  ];
  for (const matcher of cutoffMatchers) {
    const match = value.match(matcher);
    if (match && typeof match.index === "number" && match.index > 0) {
      value = value.slice(0, match.index).trim();
    }
  }

  // If the abstract is Chinese, keep it compact (avoid accidental leading markers).
  if (lang.startsWith("zh")) {
    value = value.replace(/^[：:\-\s]+/g, "").trim();
  }

  value = value.replace(/\n{3,}/g, "\n\n").trim();
  return value;
}

function normalizeInlineText(text) {
  return normalizeText(text).replaceAll(/\s+/g, " ").trim();
}

function splitAuthorsText(text) {
  const raw = normalizeInlineText(text);
  if (!raw) return [];

  const trimmed = raw.replace(/^[\s,，;；、]+|[\s,，;；、]+$/g, "").trim();
  if (!trimmed) return [];

  // 1) Prefer semicolons (CNKI often uses `;` / `；`), even if it results in a single name:
  // it strips trailing delimiters like `李珍;`.
  if (/[;；]/.test(trimmed)) {
    return trimmed
      .split(/[;；]+/)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  // 2) Chinese list separators.
  if (/[、，]/.test(trimmed)) {
    const parts = trimmed
      .split(/[、，]+/)
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length > 1) return parts;
  }

  // 3) Common English separators.
  if (/\s+and\s+|\s*&\s*/i.test(trimmed)) {
    const parts = trimmed
      .split(/\s*(?:and|&)\s*/i)
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length > 1) return parts;
  }

  // 4) Commas: either a list of authors, or "Last, First" format.
  if (/,/.test(trimmed)) {
    const parts = trimmed
      .split(/\s*,\s*/)
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length === 2) {
      const [firstPart, secondPart] = parts;
      const firstHasSpace = /\s/.test(firstPart);
      const secondHasSpace = /\s/.test(secondPart);

      // Heuristic: "Last, First" usually has a compact last name (no spaces),
      // while a 2-author list usually has spaces in both names.
      const looksLikeLastFirst = !firstHasSpace && secondHasSpace;
      if (looksLikeLastFirst) return [`${secondPart} ${firstPart}`.trim()];
      return parts;
    }
    if (parts.length > 2) return parts;
  }

  return [trimmed];
}

function formatAuthors(authors) {
  const values = Array.isArray(authors) ? authors : [];
  const names = [];
  for (const value of values) {
    const text = normalizeInlineText(value);
    if (!text) continue;
    for (const token of splitAuthorsText(text)) {
      const cleaned = normalizeInlineText(token)
        .replace(/^unknown$/i, "")
        .replace(/[\s,，;；、]+$/g, "")
        .replace(/^[\s,，;；、]+/g, "")
        .replaceAll(/\s*\(\s*\)\s*/g, "")
        .trim();
      if (!cleaned) continue;
      names.push(cleaned);
    }
  }
  const unique = Array.from(new Set(names));
  return unique.length ? unique.join(", ") : "unknown";
}

function effectiveTranslationStatus(entry) {
  const lang = String(entry?.abstract_language || "");
  if (lang.startsWith("zh")) return "success";
  return String(entry?.translation?.status || "");
}

function isProbablyNonArticle(entry) {
  const title = String(entry?.title || "").trim();
  const titleLower = title.toLowerCase();
  const authors = Array.isArray(entry?.authors) ? entry.authors.filter(Boolean) : [];
  const abstract = normalizeText(entry?.abstract_original || "");
  const abstractLower = abstract.toLowerCase();

  // Book reviews often embed bibliographic/purchase metadata in the *title* itself.
  const looksLikeBookReviewTitle =
    /(\.|\u3002)\s*By\s+/i.test(title) &&
    (/\bPp\.\b/i.test(title) ||
      /[$£€]/.test(title) ||
      /\b(hardcover|paperback|ebook)\b/i.test(title) ||
      /\b(University Press|Press)\b/i.test(title));

  const titleMatchers = [
    /征稿(启事)?/u,
    /欢迎订阅/u,
    /投稿指南/u,
    /作者指南/u,
    /征订/u,
    /通知|公告|声明|启事/u,
    /更正|勘误/u,
    /目录/u,
    /致谢/u,
    /编者按/u,
    /订阅/u,
    /call for papers/i,
    /announcement/i,
    /editorial/i,
    /editors?[’']?\s+notes/i,
    /erratum|corrigendum/i,
    /addendum/i,
    /retraction|expression of concern/i,
    /front matter|back matter|masthead/i,
    /recent referees?/i,
    /turnaround times?/i,
    /in memoriam/i,
  ];
  if (looksLikeBookReviewTitle) return true;
  if (titleMatchers.some((re) => re.test(title))) return true;

  // Many "front matter" type entries have no authors and the abstract is just issue metadata.
  if (authors.length === 0) {
    const looksLikeIssueMeta =
      abstractLower.includes("volume") &&
      (abstractLower.includes("issue") || abstractLower.includes("page") || abstractLower.includes("pages"));
    if (looksLikeIssueMeta) return true;
  }

  // CNKI non-paper notices tend to have no authors and are short titles with promotional wording.
  if (authors.length === 0 && (title.includes("订阅") || title.includes("征稿"))) return true;

  return false;
}

function pickStatusPill(status) {
  if (status === "success") return ["success", "good"];
  if (status === "failed") return ["failed", "bad"];
  return [status || "unknown", "warn"];
}

function computeJournalBadge(item) {
  const total = item.translation.success + item.translation.failed + item.translation.skipped;
  if (!total) return "no translations";
  if (item.translation.failed) return `${item.translation.failed} failed`;
  if (item.translation.success) return `${item.translation.success} ok`;
  return "skipped";
}

function renderHint(message, type = "info") {
  if (!message) {
    elements.hint.textContent = "";
    return;
  }
  elements.hint.textContent = message;
  elements.hint.style.color = type === "error" ? "var(--bad)" : "var(--muted)";
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  return await response.json();
}

function buildSourceOptions(journals) {
  const sources = Array.from(new Set(journals.map((j) => j.source_type))).sort();
  elements.sourceFilter.innerHTML = `<option value="">全部来源</option>${sources
    .map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`)
    .join("")}`;
}

function applyFilters() {
  if (!viewerIndex) return [];
  const query = elements.search.value.trim().toLowerCase();
  const source = elements.sourceFilter.value.trim().toLowerCase();
  const status = elements.statusFilter.value.trim().toLowerCase();

  const journals = viewerIndex.journals.filter((journal) => {
    if (source && journal.source_type !== source) return false;
    if (!status) return true;
    if (status === "success") return journal.translation.success > 0;
    if (status === "failed") return journal.translation.failed > 0;
    if (status === "skipped") return journal.translation.skipped > 0;
    return true;
  });

  if (!query) return journals;
  return journals.filter((journal) => {
    const haystack = `${journal.name} ${journal.slug} ${journal.source_type}`.toLowerCase();
    return haystack.includes(query);
  });
}

function renderJournals() {
  if (!viewerIndex) return;
  const filtered = applyFilters();
  elements.stats.textContent = `${filtered.length}/${viewerIndex.journals.length}`;

  elements.journalList.innerHTML = filtered
    .map((journal) => {
      const active = activeJournal && activeJournal.slug === journal.slug ? "active" : "";
      const badge = computeJournalBadge(journal);
      const meta = [
        journal.source_type,
        `${journal.entry_count} entries`,
        journal.latest_published_at ? `latest ${formatDate(journal.latest_published_at)}` : "",
      ]
        .filter(Boolean)
        .join(" · ");
      return `<div class="item ${active}" data-slug="${escapeHtml(journal.slug)}">
        <div>
          <div class="item-title">${escapeHtml(journal.name)}</div>
          <div class="item-sub">${escapeHtml(meta)}</div>
        </div>
        <div class="badge">${escapeHtml(badge)}</div>
      </div>`;
    })
    .join("");
}

function renderEntries() {
  if (!activeArchive || !activeArchive.entries) {
    elements.entries.innerHTML = `<div class="empty">没有条目。</div>`;
    return;
  }
  const query = elements.search.value.trim().toLowerCase();
  const statusFilter = elements.statusFilter.value.trim().toLowerCase();

  const filtered = activeArchive.entries
    .slice()
    .reverse()
    .filter((entry) => {
      if (!entry) return false;
      if (isProbablyNonArticle(entry)) return false;
      if (statusFilter && effectiveTranslationStatus(entry) !== statusFilter) return false;
      if (!query) return true;
      const authorText = formatAuthors(entry.authors);
      const haystack = `${entry.title || ""} ${authorText}`.toLowerCase();
      return haystack.includes(query);
    });

  elements.entries.innerHTML = filtered
    .map((entry) => {
      const active = activeEntryId === entry.id ? "active" : "";
      const [label, cls] = pickStatusPill(effectiveTranslationStatus(entry));
      const published = entry.published_at ? formatDate(entry.published_at) : "";
      const authorText = formatAuthors(entry.authors);
      return `<div class="entry ${active}" data-entry-id="${escapeHtml(entry.id)}">
        <div class="entry-title">${escapeHtml(entry.title || "Untitled")}</div>
        <div class="entry-meta">
          ${published ? `<span>${escapeHtml(published)}</span>` : ""}
          <span>${escapeHtml(authorText)}</span>
          <span class="pill ${cls}">${escapeHtml(label)}</span>
        </div>
      </div>`;
    })
    .join("");
}

function renderDetail(entry) {
  if (!entry) {
    elements.detail.innerHTML = `<div class="empty">点击左侧文章查看摘要与翻译。</div>`;
    return;
  }
  const status = effectiveTranslationStatus(entry);
  const [label, cls] = pickStatusPill(status);
  const published = entry.published_at ? formatDate(entry.published_at) : "";
  const fetched = entry.fetched_at ? formatDate(entry.fetched_at) : "";
  const authors = formatAuthors(entry.authors);
  const lang = String(entry.abstract_language || "");
  const original = formatAbstract(entry.abstract_original || "", lang);
  const zh = formatAbstract(entry.abstract_zh || "", "zh") || (lang.startsWith("zh") ? original : "");
  const link = entry.link || "";

  elements.detail.innerHTML = `
    <div class="detail-title">${escapeHtml(entry.title || "Untitled")}</div>
    <div class="detail-links">
      ${link ? `<a class="link" href="${escapeHtml(link)}" target="_blank" rel="noreferrer">打开原文</a>` : ""}
      <span class="pill ${cls}">${escapeHtml(label)}</span>
      ${lang ? `<span class="pill">${escapeHtml(lang)}</span>` : ""}
      ${published ? `<span class="pill">published ${escapeHtml(published)}</span>` : ""}
      ${fetched ? `<span class="pill">fetched ${escapeHtml(fetched)}</span>` : ""}
    </div>

    <div class="detail-section">
      <div class="detail-section-title">Authors</div>
      <div class="detail-text">${escapeHtml(authors)}</div>
    </div>

    <div class="detail-section">
      <div class="detail-section-title">Abstract (Original)</div>
      <div class="detail-text">${escapeHtml(original || "(empty)")}</div>
    </div>

    <div class="detail-section">
      <div class="detail-section-title">Abstract (ZH)</div>
      <div class="detail-text">${escapeHtml(zh || "(empty)")}</div>
    </div>
  `;
}

async function loadIndex() {
  renderHint("");
  try {
    const index = /** @type {ViewerIndex} */ (await fetchJson(`${INDEX_URL}?t=${Date.now()}`));
    viewerIndex = index;
    buildSourceOptions(index.journals);
    renderJournals();
    renderHint("");
  } catch (err) {
    viewerIndex = null;
    elements.journalList.innerHTML = "";
    renderHint(
      `无法加载 viewer/index.json。请确认你是通过本地 HTTP 服务打开（例如 http://127.0.0.1:8765/viewer/）。错误：${err}`,
      "error"
    );
  }
}

async function loadJournal(slug) {
  if (!viewerIndex) return;
  const journal = viewerIndex.journals.find((j) => j.slug === slug);
  if (!journal) return;
  activeJournal = journal;
  activeEntryId = null;
  activeArchive = null;
  renderJournals();
  elements.mainTitle.textContent = journal.name;
  elements.mainMeta.textContent = `${journal.source_type} · ${journal.entry_count} entries · last_run_at ${
    journal.last_run_at ? formatDate(journal.last_run_at) : "unknown"
  }`;
  elements.entries.innerHTML = `<div class="empty">加载中…</div>`;
  renderDetail(null);
  try {
    const archive = await fetchJson(`../${journal.archive_path}?t=${Date.now()}`);
    activeArchive = archive;
    renderEntries();
  } catch (err) {
    elements.entries.innerHTML = `<div class="empty">加载期刊 JSON 失败：${escapeHtml(String(err))}</div>`;
  }
}

function bindEvents() {
  elements.search.addEventListener("input", () => {
    renderJournals();
    renderEntries();
  });
  elements.sourceFilter.addEventListener("change", () => {
    renderJournals();
  });
  elements.statusFilter.addEventListener("change", () => {
    renderJournals();
    renderEntries();
  });
  elements.refresh.addEventListener("click", () => {
    loadIndex();
  });

  elements.journalList.addEventListener("click", (event) => {
    const target = /** @type {HTMLElement|null} */ (event.target instanceof HTMLElement ? event.target : null);
    const item = target ? target.closest(".item") : null;
    if (!item) return;
    const slug = item.getAttribute("data-slug");
    if (!slug) return;
    loadJournal(slug);
  });

  elements.entries.addEventListener("click", (event) => {
    const target = /** @type {HTMLElement|null} */ (event.target instanceof HTMLElement ? event.target : null);
    const item = target ? target.closest(".entry") : null;
    if (!item) return;
    const entryId = item.getAttribute("data-entry-id");
    if (!entryId || !activeArchive) return;
    activeEntryId = entryId;
    renderEntries();
    const entry = (activeArchive.entries || []).find((e) => e.id === entryId);
    renderDetail(entry);
  });
}

bindEvents();
await loadIndex();
