import re

from spacy.tokens import Doc, Token
from wordfreq import zipf_frequency

from ..schemas import Issue, IssueSource, IssueType, Severity

TERMINAL = {".", "!", "?", "…"}
CLOSERS = {'"', "'", ")", "]", "}", "”", "’"}
VOWEL_EXCEPTIONS = {"hour", "honest", "honor", "honour", "heir", "herb"}
CONSONANT_OPENERS = {"one", "once", "euro", "european", "uni", "use", "usu", "user", "ubiq", "ukulele"}
SINGULAR_LOOKING_PLURALS = {
    "news",
    "series",
    "species",
    "physics",
    "mathematics",
    "math",
    "economics",
    "politics",
    "means",
    "ethics",
    "athletics",
    "gymnastics",
}
NEGATIONS = {
    "not",
    "never",
    "no",
    "nothing",
    "nobody",
    "none",
    "nowhere",
    "neither",
    "nor",
    "cannot",
    "hardly",
    "barely",
    "scarcely",
}
BE_FORMS = {"is", "are", "was", "were", "am"}
HAVE_FORMS = {"has", "have"}
DO_FORMS = {"does", "do"}

SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,.;:!?])")
DOUBLE_PUNCT = re.compile(r"([!?,;:])\1+")
OF_HAVE = re.compile(r"\b(could|couldn't|should|shouldn't|would|wouldn't|must|might|may)\s+of\b", re.IGNORECASE)
PRONOUN_SUBJECTS = {"i", "you", "he", "she", "it", "we", "they", "this", "that", "there"}
ING_NOUNS = {"building", "meeting", "wedding", "ceiling", "morning", "evening", "feeling", "being", "setting", "painting", "clothing", "thing", "something", "nothing", "anything", "everything"}
ED_NOUNS = {"bed", "red", "shed", "seed", "need", "feed", "speed", "breed", "creed", "greed"}

WORDINESS = {
    "in order to": "to",
    "due to the fact that": "because",
    "at this point in time": "now",
    "in the event that": "if",
    "a large number of": "many",
    "in spite of the fact that": "although",
    "for the purpose of": "to",
    "with regard to": "about",
    "the reason why is that": "because",
    "each and every": "every",
    "very unique": "unique",
    "advance planning": "planning",
    "close proximity": "nearby",
}

WORDINESS_RE = re.compile(r"\b(" + "|".join(re.escape(phrase) for phrase in WORDINESS) + r")\b", re.IGNORECASE)


def _issue(
    rule_id: str,
    start: int,
    end: int,
    text: str,
    issue_type: IssueType,
    severity: Severity,
    message: str,
    suggestions: list[str] | None = None,
) -> Issue:
    return Issue(
        id=f"rule:{rule_id}:{start}:{end}",
        start=start,
        end=end,
        text=text,
        type=issue_type,
        severity=severity,
        message=message,
        suggestions=suggestions or [],
        rule_id=rule_id,
        source=IssueSource.rule,
    )


def _match_case(original: str, replacement: str) -> str:
    if not replacement:
        return replacement
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _token_end(token: Token) -> int:
    return token.idx + len(token.text)


def _starts_with_vowel_sound(word: str) -> bool:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return False
    if cleaned in VOWEL_EXCEPTIONS or cleaned.startswith(("hour", "honest", "honor", "honour", "heir")):
        return True
    if cleaned in CONSONANT_OPENERS or cleaned.startswith(tuple(CONSONANT_OPENERS)):
        return False
    return cleaned[0] in "aeiou"


def _third_person(lemma: str) -> str:
    irregular = {"be": "is", "have": "has", "do": "does", "go": "goes"}
    if lemma in irregular:
        return irregular[lemma]
    if lemma.endswith(("s", "x", "z", "ch", "sh", "o")):
        return lemma + "es"
    if lemma.endswith("y") and len(lemma) > 1 and lemma[-2] not in "aeiou":
        return lemma[:-1] + "ies"
    return lemma + "s"


def _looks_like_verb(token: Token) -> bool:
    if token.pos_ in {"VERB", "AUX"}:
        return True
    if token.tag_ in {"VBG", "VBD", "VBN", "VB", "VBP", "VBZ", "MD"}:
        return True
    lower = token.lower_
    if lower.endswith("ing") and lower not in ING_NOUNS and zipf_frequency(lower, "en") >= 2.0:
        return True
    if lower.endswith("ed") and lower not in ED_NOUNS and zipf_frequency(lower, "en") >= 2.5:
        return True
    return False


def _subject_number(token: Token) -> str | None:
    lower = token.lower_
    if lower in {"i", "you", "we", "they"}:
        return "Plur"
    if lower in {"he", "she", "it", "this", "that"}:
        return "Sing"
    if lower in SINGULAR_LOOKING_PLURALS:
        return "Sing"
    if token.tag_ in {"NNS", "NNPS"}:
        return "Plur"
    if any(child.dep_ == "conj" for child in token.children):
        return "Plur"
    morph = token.morph.get("Number")
    if morph:
        return "Sing" if morph[0] == "Sing" else "Plur"
    if token.tag_ in {"NN", "NNP", "PRP"}:
        return "Sing"
    return None


def check_repeated_words(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    tokens = [token for token in doc if not token.is_space]
    for first, second in zip(tokens, tokens[1:]):
        if not first.is_alpha or not second.is_alpha:
            continue
        if first.lower_ != second.lower_:
            continue
        if first.lower_ in {"had", "that", "is"}:
            continue
        issues.append(
            _issue(
                "REPEATED_WORD",
                first.idx,
                _token_end(second),
                doc.text[first.idx:_token_end(second)],
                IssueType.grammar,
                Severity.error,
                f"Repeated word '{first.text}'.",
                [first.text],
            )
        )
    return issues


def check_articles(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    tokens = [token for token in doc if not token.is_space]
    for article, following in zip(tokens, tokens[1:]):
        lower = article.lower_
        if lower not in {"a", "an"}:
            continue
        if not following.is_alpha or following.like_num or following.pos_ == "PROPN":
            continue
        if len(following.text) > 1 and following.text.isupper():
            continue
        expected = "an" if _starts_with_vowel_sound(following.text) else "a"
        if expected == lower:
            continue
        replacement = _match_case(article.text, expected)
        issues.append(
            _issue(
                "ARTICLE_A_AN",
                article.idx,
                _token_end(article),
                article.text,
                IssueType.grammar,
                Severity.error,
                f"Use '{replacement}' before '{following.text}'.",
                [replacement],
            )
        )
    return issues


def check_confusables(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    tokens = [token for token in doc if not token.is_space]
    for current, following in zip(tokens, tokens[1:]):
        lower = current.lower_
        if lower == "its" and _looks_like_verb(following):
            replacement = _match_case(current.text, "it's")
            issues.append(
                _issue(
                    "ITS_IT_IS",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Use 'it's' (it is) before a verb.",
                    [replacement],
                )
            )
        elif lower == "it's" and following.tag_ in {"NN", "NNS"}:
            replacement = _match_case(current.text, "its")
            issues.append(
                _issue(
                    "IT_IS_ITS",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Use 'its' for possession before a noun.",
                    [replacement],
                )
            )
        elif lower == "your" and _looks_like_verb(following):
            replacement = _match_case(current.text, "you're")
            issues.append(
                _issue(
                    "YOUR_YOU_ARE",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Use 'you're' (you are) before a verb.",
                    [replacement],
                )
            )
        elif lower == "you're" and following.tag_ in {"NN", "NNS"}:
            replacement = _match_case(current.text, "your")
            issues.append(
                _issue(
                    "YOU_ARE_YOUR",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Use 'your' for possession before a noun.",
                    [replacement],
                )
            )
        elif lower == "their" and _looks_like_verb(following):
            replacement = _match_case(current.text, "they're")
            issues.append(
                _issue(
                    "THEIR_THEY_ARE",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Use 'they're' (they are) before a verb.",
                    [replacement],
                )
            )
        elif lower == "there" and _looks_like_verb(following):
            replacement = _match_case(current.text, "they're")
            issues.append(
                _issue(
                    "THERE_THEY_ARE",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Did you mean 'they're' (they are)?",
                    [replacement],
                )
            )
        elif lower == "they're" and following.tag_ in {"NN", "NNS"}:
            replacement = _match_case(current.text, "their")
            issues.append(
                _issue(
                    "THEY_ARE_THEIR",
                    current.idx,
                    _token_end(current),
                    current.text,
                    IssueType.grammar,
                    Severity.error,
                    "Use 'their' for possession before a noun.",
                    [replacement],
                )
            )
    return issues


def check_subject_verb_agreement(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    for token in doc:
        if token.dep_ not in {"nsubj", "nsubjpass"}:
            continue
        head = token.head
        if head.pos_ not in {"AUX", "VERB"}:
            continue
        number = _subject_number(token)
        if number is None:
            continue
        form = head.lower_
        suggestion = None
        if token.lower_ == "i":
            suggestion = {"is": "am", "are": "am", "were": "was", "has": "have", "does": "do"}.get(form)
        elif number == "Sing":
            suggestion = {"are": "is", "were": "was", "have": "has", "do": "does"}.get(form)
            if suggestion is None and token.morph.get("Person") == ["3"] and head.tag_ == "VBP":
                suggestion = _third_person(head.lemma_)
        elif number == "Plur":
            suggestion = {"is": "are", "was": "were", "has": "have", "does": "do", "am": "are"}.get(form)
        if not suggestion or suggestion == form:
            continue
        replacement = _match_case(head.text, suggestion)
        issues.append(
            _issue(
                "SUBJECT_VERB_AGREEMENT",
                head.idx,
                _token_end(head),
                head.text,
                IssueType.grammar,
                Severity.error,
                f"'{token.text}' does not agree with '{head.text}'. Consider '{replacement}'.",
                [replacement],
            )
        )
    return issues


def check_passive_voice(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[int] = set()
    for token in doc:
        if token.dep_ not in {"nsubjpass", "auxpass"}:
            continue
        head = token.head
        if head.i in seen or head.pos_ not in {"VERB", "AUX"}:
            continue
        seen.add(head.i)
        issues.append(
            _issue(
                "PASSIVE_VOICE",
                head.idx,
                _token_end(head),
                head.text,
                IssueType.style,
                Severity.suggestion,
                "Passive voice detected; active voice is often clearer.",
                [],
            )
        )
    return issues


def check_double_negatives(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    tokens = [token for token in doc if not token.is_space]
    for index, token in enumerate(tokens):
        if token.lower_ not in NEGATIONS:
            continue
        for forward in range(index + 1, min(index + 5, len(tokens))):
            other = tokens[forward]
            if other.pos_ in {"PUNCT"}:
                continue
            if other.lower_ in NEGATIONS:
                if token.lower_ in {"hardly", "barely", "scarcely"} or other.lower_ in {"hardly", "barely", "scarcely"}:
                    break
                start = other.idx
                if start > 0 and doc.text[start - 1] == " ":
                    start -= 1
                issues.append(
                    _issue(
                        "DOUBLE_NEGATIVE",
                        start,
                        _token_end(other),
                        doc.text[start:_token_end(other)],
                        IssueType.style,
                        Severity.warning,
                        "Double negative detected; consider rephrasing.",
                        [""],
                    )
                )
                break
            break
    return issues


def check_punctuation(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    text = doc.text
    for match in SPACE_BEFORE_PUNCT.finditer(text):
        issues.append(
            _issue(
                "SPACE_BEFORE_PUNCT",
                match.start(),
                match.end(),
                match.group(0),
                IssueType.punctuation,
                Severity.warning,
                "Remove the space before punctuation.",
                [match.group(1)],
            )
        )
    for match in DOUBLE_PUNCT.finditer(text):
        if len(match.group(0)) < 2:
            continue
        issues.append(
            _issue(
                "REPEATED_PUNCT",
                match.start(),
                match.end(),
                match.group(0),
                IssueType.punctuation,
                Severity.warning,
                "Repeated punctuation.",
                [match.group(1)],
            )
        )
    for match in OF_HAVE.finditer(text):
        replacement = _match_case(match.group(1), match.group(1).split("'")[0] + " have")
        issues.append(
            _issue(
                "OF_HAVE",
                match.start(),
                match.end(),
                match.group(0),
                IssueType.grammar,
                Severity.error,
                "Use 'have' instead of 'of' after a modal verb.",
                [replacement],
            )
        )
    return issues


def check_wordiness(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    for match in WORDINESS_RE.finditer(doc.text):
        phrase = match.group(0)
        replacement = _match_case(phrase, WORDINESS[phrase.lower()])
        issues.append(
            _issue(
                "WORDINESS",
                match.start(),
                match.end(),
                phrase,
                IssueType.style,
                Severity.suggestion,
                f"Consider '{replacement}' for concision.",
                [replacement],
            )
        )
    return issues


def _line_start(text: str, index: int) -> int:
    return text.rfind("\n", 0, index) + 1


def _is_heading(sentence) -> bool:
    stripped = sentence.text.strip()
    if not stripped:
        return True
    if stripped[0] in "#-*•>":
        return True
    words = [token.text for token in sentence if token.is_alpha]
    if not words:
        return True
    if len(words) <= 8 and all(word[:1].isupper() for word in words):
        return True
    return False


def check_sentences(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    text = doc.text
    for sentence in doc.sents:
        tokens = [token for token in sentence if not token.is_space]
        if not tokens:
            continue
        word_count = sum(1 for token in tokens if token.is_alpha)
        heading = _is_heading(sentence)

        first_alpha = next((token for token in tokens if token.is_alpha and not token.like_url and not token.like_email), None)
        if first_alpha is not None and first_alpha.text[:1].islower() and not heading:
            previous = first_alpha.idx - 1
            while previous >= 0 and text[previous] in " \t":
                previous -= 1
            boundary = previous < 0 or text[previous] in ".!?…\n\"'”’)]"
            if boundary:
                replacement = first_alpha.text[:1].upper() + first_alpha.text[1:]
                issues.append(
                    _issue(
                        "SENTENCE_CAPITALIZATION",
                        first_alpha.idx,
                        _token_end(first_alpha),
                        first_alpha.text,
                        IssueType.punctuation,
                        Severity.warning,
                        "Sentence should start with a capital letter.",
                        [replacement],
                    )
                )

        if word_count >= 8:
            for index, token in enumerate(tokens):
                if token.text != ",":
                    continue
                rest = tokens[index + 1:index + 3]
                if len(rest) < 2:
                    continue
                subject, verb = rest
                if subject.lower_ not in PRONOUN_SUBJECTS:
                    continue
                if not _looks_like_verb(verb):
                    continue
                issues.append(
                    _issue(
                        "COMMA_SPLICE",
                        token.idx,
                        _token_end(verb),
                        text[token.idx:_token_end(verb)],
                        IssueType.style,
                        Severity.suggestion,
                        "Possible comma splice; use a conjunction or a period.",
                        [],
                    )
                )
        if word_count < 5 or heading:
            continue
        last = tokens[-1]
        ending = last.text
        if ending in TERMINAL:
            continue
        if ending in CLOSERS:
            previous = tokens[-2].text if len(tokens) > 1 else ""
            if previous in TERMINAL or previous.endswith((".", "!", "?")):
                continue
        if ending in {":", ";"}:
            continue
        if ending in {",", "–", "-"}:
            issues.append(
                _issue(
                    "TERMINAL_PUNCTUATION",
                    last.idx,
                    _token_end(last),
                    last.text,
                    IssueType.punctuation,
                    Severity.warning,
                    "Sentence appears to be missing terminal punctuation.",
                    ["."],
                )
            )
            continue
        position = _token_end(last)
        issues.append(
            _issue(
                "TERMINAL_PUNCTUATION",
                position,
                position,
                "",
                IssueType.punctuation,
                Severity.warning,
                "Sentence appears to be missing terminal punctuation.",
                ["."],
            )
        )

    return issues


def run_rules(doc: Doc) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_repeated_words(doc))
    issues.extend(check_articles(doc))
    issues.extend(check_confusables(doc))
    issues.extend(check_subject_verb_agreement(doc))
    issues.extend(check_passive_voice(doc))
    issues.extend(check_double_negatives(doc))
    issues.extend(check_punctuation(doc))
    issues.extend(check_wordiness(doc))
    issues.extend(check_sentences(doc))
    return issues
