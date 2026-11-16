import re

import textstat
from spacy.tokens import Doc

from ..schemas import DocumentStats

PARAGRAPH_SPLIT = re.compile(r"\n[ \t]*\n")


def _safe_metric(function, text: str) -> float:
    try:
        value = float(function(text))
    except (ValueError, ZeroDivisionError, TypeError):
        return 0.0
    if value != value:
        return 0.0
    return round(max(0.0, min(value, 200.0)), 1)


def compute_stats(text: str, doc: Doc) -> DocumentStats:
    words = sum(1 for token in doc if token.is_alpha)
    sentences = len(list(doc.sents)) or 1
    paragraphs = len([block for block in PARAGRAPH_SPLIT.split(text) if block.strip()]) or 1
    long_sentences = sum(1 for sentence in doc.sents if sum(1 for token in sentence if token.is_alpha) > 25)
    lemmas = {token.lemma_.lower() for token in doc if token.is_alpha}
    diversity = round(len(lemmas) / words, 3) if words else 0.0
    passive_heads = {
        token.head.i
        for token in doc
        if token.dep_ in {"nsubjpass", "auxpass"} and token.head.pos_ in {"VERB", "AUX"}
    }
    passive_ratio = round(min(len(passive_heads) / sentences, 1.0), 3)
    reading_time = max(1, round((words / 200.0) * 60)) if words else 0

    return DocumentStats(
        words=words,
        sentences=sentences,
        characters=len(text),
        paragraphs=paragraphs,
        average_sentence_length=round(words / sentences, 1),
        long_sentences=long_sentences,
        lexical_diversity=diversity,
        passive_ratio=passive_ratio,
        flesch_reading_ease=_safe_metric(textstat.flesch_reading_ease, text),
        flesch_kincaid_grade=_safe_metric(textstat.flesch_kincaid_grade, text),
        gunning_fog=_safe_metric(textstat.gunning_fog, text),
        reading_time_seconds=reading_time,
    )
