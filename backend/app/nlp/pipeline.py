import asyncio
import threading
import time

import anyio
import spacy

from ..config import Settings, get_settings
from ..schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DocumentStats,
    Issue,
    IssueSource,
    Severity,
)
from .languagetool import LanguageToolClient
from .readability import compute_stats
from .rules import run_rules
from .segment import split_chunks
from .spellcheck import SpellChecker

SOURCE_PRIORITY = {
    IssueSource.rule: 3,
    IssueSource.spellcheck: 2,
    IssueSource.language_tool: 1,
}

EMPTY_STATS = DocumentStats(
    words=0,
    sentences=0,
    characters=0,
    paragraphs=0,
    average_sentence_length=0.0,
    long_sentences=0,
    lexical_diversity=0.0,
    passive_ratio=0.0,
    flesch_reading_ease=0.0,
    flesch_kincaid_grade=0.0,
    gunning_fog=0.0,
    reading_time_seconds=0,
)


def _overlaps(first: Issue, second: Issue) -> bool:
    if first.start == first.end or second.start == second.end:
        return first.start == second.start
    return first.start < second.end and second.start < first.end


def merge_issues(groups: list[list[Issue]]) -> list[Issue]:
    candidates = [issue for group in groups for issue in group]
    candidates.sort(
        key=lambda issue: (
            issue.start,
            -issue.severity.rank,
            -(issue.end - issue.start),
            -SOURCE_PRIORITY[issue.source],
        )
    )
    kept: list[Issue] = []
    seen: set[str] = set()
    for issue in candidates:
        if issue.id in seen:
            continue
        if any(_overlaps(issue, existing) for existing in kept):
            continue
        kept.append(issue)
        seen.add(issue.id)
    kept.sort(key=lambda issue: (issue.start, -issue.severity.rank))
    return kept


class Analyzer:
    def __init__(self, settings: Settings | None = None, use_remote: bool = True):
        self.settings = settings or get_settings()
        self.nlp = spacy.load("en_core_web_sm")
        self.spell = SpellChecker()
        self.lt = LanguageToolClient(self.settings) if use_remote else None
        self._doc_lock = threading.Lock()

    async def startup(self) -> None:
        if self.lt is not None:
            await self.lt.startup()

    async def close(self) -> None:
        if self.lt is not None:
            await self.lt.close()

    def _document_pass(self, text: str) -> tuple[spacy.tokens.Doc, list[Issue], list[Issue], DocumentStats, float]:
        started = time.perf_counter()
        with self._doc_lock:
            doc = self.nlp(text)
        rules = run_rules(doc)
        spelling = self.spell.check_document(doc)
        stats = compute_stats(text, doc)
        elapsed = (time.perf_counter() - started) * 1000
        return doc, rules, spelling, stats, elapsed

    async def _remote_pass(self, chunks, language: str | None) -> tuple[list[Issue], list[str], float]:
        if self.lt is None:
            return [], [], 0.0
        started = time.perf_counter()
        issues, degraded = await self.lt.check_chunks(chunks, language)
        return issues, degraded, (time.perf_counter() - started) * 1000

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        started = time.perf_counter()
        text = request.text
        if len(text) > self.settings.max_text_chars:
            raise ValueError("text is longer than the configured maximum")

        if not text.strip():
            return AnalyzeResponse(
                issues=[],
                stats=EMPTY_STATS.model_copy() if request.include_stats else None,
                text_length=0,
                timing_ms={"total": round((time.perf_counter() - started) * 1000, 1)},
            )

        chunks = split_chunks(text, self.settings.chunk_chars)
        remote_enabled = request.use_remote and self.settings.lt_enabled and self.lt is not None
        doc_task = anyio.to_thread.run_sync(self._document_pass, text)
        if remote_enabled:
            remote_task = self._remote_pass(chunks, request.language)
        else:
            remote_task = asyncio.sleep(0, result=([], [], 0.0))

        (doc, rule_issues, spell_issues, stats, doc_ms), (lt_issues, degraded, lt_ms) = await asyncio.gather(
            doc_task, remote_task
        )

        if request.use_remote and not self.settings.lt_enabled:
            degraded = ["language_tool_disabled", *degraded]

        issues = merge_issues([rule_issues, spell_issues, lt_issues])
        if request.categories:
            allowed = set(request.categories)
            issues = [issue for issue in issues if issue.type in allowed]
        issues = [issue for issue in issues if issue.severity.rank >= request.min_severity.rank]

        return AnalyzeResponse(
            issues=issues,
            stats=stats if request.include_stats else None,
            text_length=len(text),
            timing_ms={
                "document": round(doc_ms, 1),
                "language_tool": round(lt_ms, 1),
                "total": round((time.perf_counter() - started) * 1000, 1),
            },
            degraded=degraded,
        )

    def analyze_sync(self, text: str, **options) -> AnalyzeResponse:
        return asyncio.run(self.analyze(AnalyzeRequest(text=text, **options)))
