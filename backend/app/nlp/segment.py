import re
from dataclasses import dataclass

PARAGRAPH_RE = re.compile(r"\n[ \t]*\n")
SENTENCE_RE = re.compile(r"(?<=[.!?])[ \t]+")


@dataclass(frozen=True)
class Chunk:
    text: str
    start: int
    end: int


def utf16_to_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    units = 0
    for index, char in enumerate(text):
        width = 2 if ord(char) > 0xFFFF else 1
        if offset < units + width:
            return index
        units += width
    return len(text)


def convert_span(text: str, start: int, end: int) -> tuple[int, int]:
    if all(ord(char) <= 0xFFFF for char in text):
        return start, end
    return utf16_to_index(text, start), utf16_to_index(text, end)


def _sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    for match in SENTENCE_RE.finditer(text, start, end):
        if match.end() > cursor:
            spans.append((cursor, match.end()))
        cursor = match.end()
    if cursor < end:
        spans.append((cursor, end))
    return spans or [(start, end)]


def _split_span(text: str, start: int, end: int, max_chars: int) -> list[Chunk]:
    if end - start <= max_chars:
        return [Chunk(text[start:end], start, end)]
    pieces: list[Chunk] = []
    chunk_start = start
    for sentence_start, sentence_end in _sentence_spans(text, start, end):
        if sentence_end - chunk_start <= max_chars:
            continue
        if sentence_start > chunk_start:
            pieces.append(Chunk(text[chunk_start:sentence_start], chunk_start, sentence_start))
            chunk_start = sentence_start
        while sentence_end - chunk_start > max_chars:
            cut = chunk_start + max_chars
            pieces.append(Chunk(text[chunk_start:cut], chunk_start, cut))
            chunk_start = cut
    if chunk_start < end:
        pieces.append(Chunk(text[chunk_start:end], chunk_start, end))
    return pieces


def split_chunks(text: str, max_chars: int = 15000) -> list[Chunk]:
    if not text:
        return []
    blocks: list[tuple[int, int]] = []
    cursor = 0
    for match in PARAGRAPH_RE.finditer(text):
        if match.start() > cursor:
            blocks.append((cursor, match.start()))
        cursor = match.end()
    if cursor < len(text):
        blocks.append((cursor, len(text)))
    if not blocks:
        blocks = [(0, len(text))]

    chunks: list[Chunk] = []
    for start, end in blocks:
        if not text[start:end].strip():
            continue
        chunks.extend(_split_span(text, start, end, max_chars))
    return chunks
