import { analyze, exportPdf, importPdf } from "./api.js";
import { completeText } from "./ghost.js";

const MAX_CHARS = 60000;
const DEBOUNCE_MS = 550;
const SEVERITY_RANK = { suggestion: 1, warning: 2, error: 3 };

const SAMPLE_TEXT = [
  "i recieve teh report yesterday and their going to review it.",
  "She go to the office every day , but the the manager was not their.",
  "In order to improve the process, we should of scheduled a meeting, the team was not ready.",
  "Its important that we're documentation is clear and consistent for all of our users.",
].join(" ");

const editor = document.getElementById("editor");
const highlightLayer = document.getElementById("highlight-layer");
const counts = document.getElementById("counts");
const status = document.getElementById("status");
const statsEl = document.getElementById("stats");
const scoreBadge = document.getElementById("score-badge");
const issueList = document.getElementById("issue-list");
const issueCount = document.getElementById("issue-count");
const emptyState = document.getElementById("empty-state");
const timingEl = document.getElementById("timing");
const degradedNotice = document.getElementById("degraded-notice");
const ghostLayer = document.getElementById("ghost-layer");
const ghostHint = document.getElementById("ghost-hint");
const ghostToggle = document.getElementById("ghost-toggle");
const remoteToggle = document.getElementById("remote-toggle");
const sampleButton = document.getElementById("sample-button");
const uploadPdfButton = document.getElementById("upload-pdf-button");
const pdfInput = document.getElementById("pdf-input");
const checkButton = document.getElementById("check-button");
const fixAllButton = document.getElementById("fix-all-button");
const pdfButton = document.getElementById("pdf-button");
const severityFilter = document.getElementById("severity-filter");
const typeFilters = document.getElementById("type-filters");

const state = {
  issues: [],
  stats: null,
  ignored: new Set(),
  activeType: "all",
  minSeverity: "warning",
  controller: null,
  timer: null,
  analyzedText: null,
  degraded: [],
  ghostSuggestion: "",
  ghostTimer: null,
  ghostDismissed: false,
};

function utf16Map(text) {
  const points = Array.from(text);
  const map = new Uint32Array(points.length + 1);
  let offset = 0;
  for (let i = 0; i < points.length; i += 1) {
    map[i] = offset;
    offset += points[i].length;
  }
  map[points.length] = offset;
  return map;
}

function formatNumber(value, digits = 0) {
  return Number(value ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function autoGrow() {
  editor.style.height = "auto";
  editor.style.height = `${editor.scrollHeight}px`;
  highlightLayer.style.height = `${editor.scrollHeight}px`;
}

let ghostMirror = null;

function caretCoordinates(text, position) {
  if (!ghostMirror) {
    ghostMirror = document.createElement("div");
    ghostMirror.className = "ghost-mirror";
    ghostMirror.setAttribute("aria-hidden", "true");
    editor.parentElement.append(ghostMirror);
  }
  const marker = document.createElement("span");
  marker.textContent = "\u200b";
  ghostMirror.style.width = `${editor.clientWidth}px`;
  ghostMirror.replaceChildren(document.createTextNode(text.slice(0, position)), marker);
  const editorRect = editor.getBoundingClientRect();
  const markerRect = marker.getBoundingClientRect();
  return {
    left: markerRect.left - editorRect.left - editor.scrollLeft,
    top: markerRect.top - editorRect.top - editor.scrollTop,
  };
}

function hideGhost() {
  state.ghostSuggestion = "";
  ghostLayer.replaceChildren();
  ghostHint.classList.add("hidden");
}

function positionGhost() {
  if (!state.ghostSuggestion) return;
  const span = ghostLayer.querySelector(".ghost-text");
  if (!span) return;
  const { left, top } = caretCoordinates(editor.value, editor.selectionStart);
  span.style.left = `${left}px`;
  span.style.top = `${top}px`;
}

function renderGhost() {
  ghostLayer.replaceChildren();
  const span = document.createElement("span");
  span.className = "ghost-text";
  span.textContent = state.ghostSuggestion;
  ghostLayer.append(span);
  positionGhost();
  ghostHint.classList.remove("hidden");
}

function updateGhost() {
  if (!ghostToggle.checked || state.ghostDismissed) return;
  if (document.activeElement !== editor) return;
  if (editor.selectionStart !== editor.selectionEnd) return;
  if (editor.selectionStart !== editor.value.length) return;
  const suggestion = completeText(editor.value);
  if (!suggestion) return;
  state.ghostSuggestion = suggestion;
  renderGhost();
}

function scheduleGhost() {
  clearTimeout(state.ghostTimer);
  state.ghostTimer = null;
  hideGhost();
  if (!ghostToggle.checked || document.activeElement !== editor) return;
  state.ghostTimer = setTimeout(() => {
    state.ghostTimer = null;
    updateGhost();
  }, 140);
}

function acceptGhost() {
  const suggestion = state.ghostSuggestion;
  if (!suggestion) return;
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  if (start !== end || start !== editor.value.length) {
    hideGhost();
    return;
  }
  editor.setRangeText(suggestion, start, end, "end");
  state.ghostDismissed = false;
  handleInput(false);
  scheduleGhost();
}

function updateCounts() {
  const text = editor.value;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  counts.textContent = `${formatNumber(words)} ${words === 1 ? "word" : "words"} · ${formatNumber(text.length)} characters`;
}

function setStatus(message, variant = "") {
  status.textContent = message;
  status.className = `status${variant ? ` ${variant}` : ""}`;
}

function severityRank(issue) {
  return SEVERITY_RANK[issue.severity] ?? 1;
}

function renderHighlights(text) {
  highlightLayer.replaceChildren();
  const map = utf16Map(text);
  const issues = visibleIssues()
    .filter((issue) => issue.end > issue.start && issue.start < map.length - 1)
    .map((issue) => ({
      ...issue,
      start: map[Math.min(issue.start, map.length - 1)],
      end: map[Math.min(issue.end, map.length - 1)],
    }))
    .sort((a, b) => a.start - b.start || b.end - a.end);

  const fragment = document.createDocumentFragment();
  let cursor = 0;
  for (const issue of issues) {
    if (issue.start < cursor) continue;
    if (issue.start > cursor) fragment.append(document.createTextNode(text.slice(cursor, issue.start)));
    const span = document.createElement("span");
    span.className = `h hl-${issue.type}`;
    span.textContent = text.slice(issue.start, issue.end);
    fragment.append(span);
    cursor = issue.end;
  }
  if (cursor < text.length) fragment.append(document.createTextNode(text.slice(cursor)));
  highlightLayer.append(fragment);
}

function renderStats(stats) {
  if (!stats) {
    scoreBadge.textContent = "No score";
    scoreBadge.className = "badge";
    return;
  }
  const ease = stats.flesch_reading_ease;
  const values = [
    ["Words", formatNumber(stats.words)],
    ["Sentences", formatNumber(stats.sentences)],
    ["Reading time", `${formatNumber(stats.reading_time_seconds)}s`],
    ["Reading ease", formatNumber(ease, 1)],
    ["Vocabulary", `${formatNumber(stats.lexical_diversity * 100, 0)}%`],
    ["Passive voice", `${formatNumber(stats.passive_ratio * 100, 0)}%`],
  ];
  statsEl.replaceChildren(
    ...values.map(([label, value]) => {
      const item = document.createElement("div");
      item.className = "stat";
      const name = document.createElement("span");
      name.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(name, strong);
      return item;
    })
  );

  let label = "Hard";
  let variant = "poor";
  if (ease >= 60) {
    label = "Clear";
    variant = "good";
  } else if (ease >= 40) {
    label = "Fair";
    variant = "fair";
  }
  scoreBadge.textContent = label;
  scoreBadge.className = `badge ${variant}`;
}

function issueMatches(issue) {
  if (state.ignored.has(issue.id)) return false;
  if (severityRank(issue) < SEVERITY_RANK[state.minSeverity]) return false;
  if (state.activeType !== "all" && issue.type !== state.activeType) return false;
  return true;
}

function visibleIssues() {
  return state.issues.filter(issueMatches);
}

function typeCounts() {
  const countsByType = { all: 0 };
  for (const issue of state.issues) {
    if (state.ignored.has(issue.id)) continue;
    if (severityRank(issue) < SEVERITY_RANK[state.minSeverity]) continue;
    countsByType[issue.type] = (countsByType[issue.type] || 0) + 1;
    countsByType.all += 1;
  }
  return countsByType;
}

function renderTypeCounts() {
  const countsByType = typeCounts();
  for (const chip of typeFilters.querySelectorAll(".chip")) {
    const type = chip.dataset.type;
    const count = countsByType[type] || 0;
    const base = type === "all" ? "All" : chip.textContent.replace(/\s*\(\d+\)$/, "");
    chip.textContent = `${base} (${count})`;
    const active = state.activeType === type;
    chip.classList.toggle("active", active);
    chip.setAttribute("aria-pressed", String(active));
  }
}

function snippet(issue, text) {
  const map = utf16Map(text);
  const issueStart = map[Math.min(issue.start, map.length - 1)] ?? 0;
  const issueEnd = map[Math.min(issue.end, map.length - 1)] ?? issueStart;
  const start = Math.max(0, issueStart - 24);
  const end = Math.min(text.length, issueEnd + 24);
  const prefix = start > 0 ? "…" : "";
  const suffix = end < text.length ? "…" : "";
  const before = text.slice(start, issueStart);
  const marked = text.slice(issueStart, issueEnd);
  const after = text.slice(issueEnd, end);
  return { before: prefix + before, marked: marked || "insertion point", after: after + suffix };
}

function replacementText(issue) {
  return issue.suggestions.length ? issue.suggestions[0] : null;
}

function selectSpan(issue) {
  const map = utf16Map(editor.value);
  const start = map[Math.min(issue.start, map.length - 1)] ?? 0;
  const end = map[Math.min(issue.end, map.length - 1)] ?? start;
  editor.focus();
  editor.setSelectionRange(start, end);
}

function applySuggestion(issue, replacement) {
  if (replacement === null) return;
  const map = utf16Map(editor.value);
  const start = map[Math.min(issue.start, map.length - 1)] ?? 0;
  const end = map[Math.min(issue.end, map.length - 1)] ?? start;
  const text = editor.value;
  editor.value = text.slice(0, start) + replacement + text.slice(end);
  const caret = start + replacement.length;
  editor.setSelectionRange(caret, caret);
  handleInput(true);
}

async function fixAll() {
  const text = editor.value;
  if (!text.trim()) {
    setStatus("Add some text first", "error");
    return;
  }
  if (text.length > MAX_CHARS) {
    setStatus(`Text exceeds the ${formatNumber(MAX_CHARS)} character limit`, "error");
    return;
  }

  fixAllButton.disabled = true;
  checkButton.disabled = true;
  setStatus("Applying fixes…", "busy");
  try {
    const result = await analyze(text, {
      use_remote: remoteToggle.checked,
      min_severity: "suggestion",
      include_stats: true,
    });
    if (editor.value !== text) {
      setStatus("Text changed while fixing; run it again");
      return;
    }

    const map = utf16Map(text);
    const allowed = new Set(["spelling", "grammar", "punctuation"]);
    const seen = new Set();
    const edits = [];
    for (const issue of result.issues) {
      if (!allowed.has(issue.type) || !issue.suggestions.length) continue;
      if (state.ignored.has(issue.id)) continue;
      const start = map[Math.min(issue.start, map.length - 1)] ?? 0;
      const end = map[Math.min(issue.end, map.length - 1)] ?? start;
      const replacement = issue.suggestions[0];
      if (text.slice(start, end) === replacement) continue;
      const key = `${start}:${end}:${replacement}`;
      if (seen.has(key)) continue;
      seen.add(key);
      edits.push({ start, end, replacement });
    }
    edits.sort((a, b) => a.start - b.start || b.end - a.end);

    const chosen = [];
    let lastEnd = 0;
    for (const edit of edits) {
      if (edit.start < lastEnd) continue;
      chosen.push(edit);
      lastEnd = Math.max(lastEnd, edit.end);
    }

    if (!chosen.length) {
      setStatus("No automatic fixes found");
      return;
    }

    let corrected = text;
    for (let index = chosen.length - 1; index >= 0; index -= 1) {
      const edit = chosen[index];
      corrected = corrected.slice(0, edit.start) + edit.replacement + corrected.slice(edit.end);
    }
    editor.value = corrected;
    const caret = corrected.length;
    editor.setSelectionRange(caret, caret);
    handleInput(true);
  } catch (error) {
    setStatus(`Fix failed: ${error.message}`, "error");
  } finally {
    fixAllButton.disabled = false;
    checkButton.disabled = false;
  }
}

sampleButton.addEventListener("click", () => {
  editor.value = SAMPLE_TEXT;
  state.ignored.clear();
  editor.focus();
  handleInput(true);
});

fixAllButton.addEventListener("click", fixAll);

async function uploadPdf(file) {
  uploadPdfButton.disabled = true;
  setStatus(`Reading ${file.name}…`, "busy");
  try {
    const result = await importPdf(file);
    editor.value = result.text.slice(0, MAX_CHARS);
    state.ignored.clear();
    editor.focus();
    handleInput(true);
    const pages =
      result.pages_read < result.pages
        ? `first ${result.pages_read} of ${result.pages} pages`
        : `${result.pages} ${result.pages === 1 ? "page" : "pages"}`;
    const suffix = result.truncated ? " · truncated to fit" : "";
    setStatus(`Loaded ${pages} from ${result.filename}${suffix}`);
  } catch (error) {
    setStatus(`PDF import failed: ${error.message}`, "error");
  } finally {
    uploadPdfButton.disabled = false;
    pdfInput.value = "";
  }
}

uploadPdfButton.addEventListener("click", () => pdfInput.click());
pdfInput.addEventListener("change", () => {
  const file = pdfInput.files?.[0];
  if (file) uploadPdf(file);
});

async function downloadPdf() {
  const text = editor.value;
  if (!text.trim()) {
    setStatus("Add some text first", "error");
    return;
  }
  pdfButton.disabled = true;
  setStatus("Preparing PDF…", "busy");
  try {
    const blob = await exportPdf(text);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `grammar-assistant-${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    setStatus("PDF downloaded");
  } catch (error) {
    setStatus(`PDF export failed: ${error.message}`, "error");
  } finally {
    pdfButton.disabled = false;
  }
}

pdfButton.addEventListener("click", downloadPdf);

function renderIssueList(text) {
  const issues = visibleIssues();
  issueCount.textContent = String(issues.length);
  issueList.replaceChildren();
  emptyState.classList.toggle("hidden", issues.length > 0);

  for (const issue of issues) {
    const item = document.createElement("li");
    item.className = "issue";
    item.dataset.type = issue.type;

    const top = document.createElement("div");
    top.className = "issue-top";
    const type = document.createElement("span");
    type.className = "issue-type";
    type.textContent = issue.type;
    const severity = document.createElement("span");
    severity.className = "issue-severity";
    severity.textContent = issue.severity;
    top.append(type, severity);

    const message = document.createElement("p");
    message.className = "issue-message";
    message.textContent = issue.message;

    const snippetEl = document.createElement("p");
    snippetEl.className = "issue-snippet";
    const parts = snippet(issue, text);
    snippetEl.append(document.createTextNode(parts.before));
    const mark = document.createElement("mark");
    mark.textContent = parts.marked;
    snippetEl.append(mark, document.createTextNode(parts.after));

    const actions = document.createElement("div");
    actions.className = "issue-actions";

    for (const suggestion of issue.suggestions.slice(0, 3)) {
      const apply = document.createElement("button");
      apply.type = "button";
      apply.className = "suggestion";
      apply.textContent = suggestion === "" ? "Delete" : suggestion;
      apply.title = `Replace with "${suggestion}"`;
      apply.addEventListener("click", () => applySuggestion(issue, suggestion));
      actions.append(apply);
    }

    const locate = document.createElement("button");
    locate.type = "button";
    locate.textContent = "Show";
    locate.addEventListener("click", () => selectSpan(issue));
    actions.append(locate);

    const ignore = document.createElement("button");
    ignore.type = "button";
    ignore.className = "ignore";
    ignore.textContent = "Ignore";
    ignore.addEventListener("click", () => {
      state.ignored.add(issue.id);
      renderAll();
    });
    actions.append(ignore);

    item.append(top, message, snippetEl, actions);
    issueList.append(item);
  }
}

function renderAll() {
  const text = editor.value;
  renderHighlights(text);
  renderTypeCounts();
  renderIssueList(text);
  autoGrow();
}

function renderDegraded(list) {
  const messages = [];
  if (list.includes("language_tool_disabled")) messages.push("LanguageTool is disabled on the server; using local rules only.");
  else if (list.length) messages.push(`Deep check unavailable: ${list.join(", ")}.`);
  degradedNotice.textContent = messages.join(" ");
  degradedNotice.classList.toggle("hidden", messages.length === 0);
}

async function runAnalysis(immediate = false) {
  const text = editor.value;
  updateCounts();
  autoGrow();

  if (state.controller) state.controller.abort();
  clearTimeout(state.timer);

  if (!text.trim()) {
    state.issues = [];
    state.stats = null;
    state.analyzedText = "";
    renderStats(null);
    timingEl.textContent = "";
    setStatus(text.length > MAX_CHARS ? "Text is too long" : "Ready", text.length > MAX_CHARS ? "error" : "");
    renderAll();
    return;
  }

  if (text.length > MAX_CHARS) {
    setStatus(`Text exceeds the ${formatNumber(MAX_CHARS)} character limit`, "error");
    return;
  }

  if (!immediate) {
    setStatus("Typing…");
    state.timer = setTimeout(() => runAnalysis(true), DEBOUNCE_MS);
    return;
  }

  const controller = new AbortController();
  state.controller = controller;
  const started = performance.now();
  setStatus("Checking…", "busy");
  checkButton.disabled = true;

  try {
    const result = await analyze(
      text,
      { use_remote: remoteToggle.checked, min_severity: "suggestion", include_stats: true },
      controller.signal
    );
    if (controller.signal.aborted) return;
    state.issues = result.issues;
    state.stats = result.stats;
    state.analyzedText = text;
    state.degraded = result.degraded || [];
    renderStats(result.stats);
    renderDegraded(state.degraded);
    renderAll();
    const elapsed = performance.now() - started;
    timingEl.textContent = `Checked in ${Math.round(elapsed)} ms · server ${Math.round(result.timing_ms.total)} ms`;
    const count = visibleIssues().length;
    setStatus(count === 0 ? "No issues found" : `${count} ${count === 1 ? "issue" : "issues"}`);
  } catch (error) {
    if (error.name === "AbortError") return;
    setStatus(`Check failed: ${error.message}`, "error");
    renderDegraded(["request_failed"]);
  } finally {
    if (state.controller === controller) {
      state.controller = null;
      checkButton.disabled = false;
    }
  }
}

function handleInput(immediate = false) {
  hideGhost();
  updateCounts();
  autoGrow();
  renderHighlights(editor.value);
  if (immediate) {
    runAnalysis(true);
  } else {
    runAnalysis(false);
  }
}

editor.addEventListener("input", () => {
  state.ghostDismissed = false;
  handleInput(false);
  scheduleGhost();
});
editor.addEventListener("scroll", () => {
  autoGrow();
  positionGhost();
});
editor.addEventListener("focus", scheduleGhost);
editor.addEventListener("blur", hideGhost);
editor.addEventListener("click", scheduleGhost);
editor.addEventListener("keydown", (event) => {
  if (
    event.key === "Tab" &&
    state.ghostSuggestion &&
    !event.shiftKey &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey
  ) {
    event.preventDefault();
    acceptGhost();
    return;
  }
  if (event.key === "Escape" && state.ghostSuggestion) {
    event.preventDefault();
    state.ghostDismissed = true;
    hideGhost();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    runAnalysis(true);
  }
});
editor.addEventListener("keyup", (event) => {
  if (["Tab", "Escape"].includes(event.key)) return;
  if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) {
    scheduleGhost();
  }
});

ghostToggle.addEventListener("change", () => {
  if (!ghostToggle.checked) {
    clearTimeout(state.ghostTimer);
    state.ghostTimer = null;
    hideGhost();
    return;
  }
  scheduleGhost();
});

checkButton.addEventListener("click", () => runAnalysis(true));

remoteToggle.addEventListener("change", () => runAnalysis(true));

severityFilter.addEventListener("change", () => {
  state.minSeverity = severityFilter.value;
  renderAll();
});

typeFilters.addEventListener("click", (event) => {
  const chip = event.target.closest(".chip");
  if (!chip) return;
  state.activeType = chip.dataset.type;
  renderAll();
});

window.addEventListener("resize", () => {
  autoGrow();
  positionGhost();
});

const params = new URLSearchParams(window.location.search);
const incoming = params.get("text");
if (incoming) {
  editor.value = incoming.slice(0, MAX_CHARS);
  editor.focus();
  handleInput(true);
} else {
  updateCounts();
  autoGrow();
  setStatus("Ready");
}
