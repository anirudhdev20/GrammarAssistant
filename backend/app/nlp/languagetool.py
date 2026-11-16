import asyncio
import hashlib
import time
from collections import deque

import httpx

from ..config import Settings
from ..schemas import Issue, IssueSource, IssueType, Severity
from .segment import Chunk, convert_span

CATEGORY_TYPES = {
    "TYPOS": IssueType.spelling,
    "PUNCTUATION": IssueType.punctuation,
    "TYPOGRAPHY": IssueType.punctuation,
    "CASING": IssueType.punctuation,
    "GRAMMAR": IssueType.grammar,
    "CONFUSED_WORDS": IssueType.grammar,
    "COLLOCATIONS": IssueType.grammar,
    "STYLE": IssueType.style,
    "REDUNDANCY": IssueType.style,
    "PLAIN_ENGLISH": IssueType.style,
    "CLARITY": IssueType.style,
    "MISC": IssueType.grammar,
}

ISSUE_TYPES = {
    "misspelling": IssueType.spelling,
    "typographical": IssueType.punctuation,
    "typography": IssueType.punctuation,
    "duplication": IssueType.grammar,
    "inconsistency": IssueType.grammar,
    "grammar": IssueType.grammar,
    "locale-violation": IssueType.grammar,
    "style": IssueType.style,
    "register": IssueType.style,
    "repetition": IssueType.style,
}

SEVERITY_BY_TYPE = {
    IssueType.spelling: Severity.error,
    IssueType.grammar: Severity.error,
    IssueType.punctuation: Severity.warning,
    IssueType.style: Severity.suggestion,
    IssueType.readability: Severity.suggestion,
}


def _classify(match: dict) -> IssueType:
    rule = match.get("rule") or {}
    category = str((rule.get("category") or {}).get("id", "")).upper()
    if category in CATEGORY_TYPES:
        return CATEGORY_TYPES[category]
    issue_type = str(rule.get("issueType", "")).lower()
    return ISSUE_TYPES.get(issue_type, IssueType.grammar)


class LanguageToolClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[float, list[Issue]]] = {}
        self._lock = asyncio.Lock()
        self._requests: deque[float] = deque()

    async def startup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.lt_timeout_seconds,
                headers={"User-Agent": "GrammarAssistant/0.1"},
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _throttle(self) -> None:
        limit = max(self.settings.lt_requests_per_minute, 1)
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._requests and now - self._requests[0] >= 60.0:
                    self._requests.popleft()
                if len(self._requests) < limit:
                    self._requests.append(now)
                    return
                wait = 60.0 - (now - self._requests[0]) + 0.05
            await asyncio.sleep(wait)

    def _cache_get(self, key: str) -> list[Issue] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires_at, issues = entry
        if expires_at <= time.monotonic():
            self._cache.pop(key, None)
            return None
        return [issue.model_copy(deep=True) for issue in issues]

    def _cache_put(self, key: str, issues: list[Issue]) -> None:
        if len(self._cache) > 512:
            oldest = min(self._cache, key=lambda item: self._cache[item][0])
            self._cache.pop(oldest, None)
        self._cache[key] = (time.monotonic() + self.settings.lt_cache_seconds, issues)

    def _map_matches(self, payload: dict, chunk: Chunk) -> list[Issue]:
        issues: list[Issue] = []
        for match in payload.get("matches", []):
            issue_type = _classify(match)
            severity = SEVERITY_BY_TYPE[issue_type]
            start = int(match.get("offset", 0))
            length = int(match.get("length", 0))
            end = start + max(length, 0)
            if self.settings.lt_offsets_utf16:
                start, end = convert_span(chunk.text, start, end)
            start = max(0, min(start, len(chunk.text)))
            end = max(start, min(end, len(chunk.text)))
            absolute_start = chunk.start + start
            absolute_end = chunk.start + end
            rule = match.get("rule") or {}
            rule_id = str(rule.get("id") or "LANGUAGETOOL")
            suggestions: list[str] = []
            for replacement in (match.get("replacements") or [])[: self.settings.max_suggestions]:
                value = replacement.get("value", "")
                if value not in suggestions:
                    suggestions.append(value)
            issues.append(
                Issue(
                    id=f"lt:{rule_id}:{absolute_start}:{absolute_end}",
                    start=absolute_start,
                    end=absolute_end,
                    text=chunk.text[start:end],
                    type=issue_type,
                    severity=severity,
                    message=str(match.get("message") or "Possible issue"),
                    suggestions=suggestions,
                    rule_id=rule_id,
                    source=IssueSource.language_tool,
                )
            )
        return issues

    async def check_chunk(self, chunk: Chunk, language: str) -> list[Issue]:
        if len(chunk.text.strip()) < 4:
            return []
        key = hashlib.sha256(f"{language}\x00{chunk.text}".encode("utf-8")).hexdigest()
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        if self._client is None:
            await self.startup()
        await self._throttle()
        response = await self._client.post(
            self.settings.lt_url,
            data={"text": chunk.text, "language": language},
        )
        response.raise_for_status()
        issues = self._map_matches(response.json(), chunk)
        self._cache_put(key, issues)
        return [issue.model_copy(deep=True) for issue in issues]

    async def check_chunks(self, chunks: list[Chunk], language: str | None = None) -> tuple[list[Issue], list[str]]:
        language = language or self.settings.lt_language
        issues: list[Issue] = []
        degraded: list[str] = []
        for chunk in chunks:
            try:
                issues.extend(await self.check_chunk(chunk, language))
            except (httpx.HTTPError, ValueError, KeyError):
                if "language_tool_unavailable" not in degraded:
                    degraded.append("language_tool_unavailable")
                break
        return issues, degraded
