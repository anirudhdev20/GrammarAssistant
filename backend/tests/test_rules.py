import pytest

from app.nlp.rules import _starts_with_vowel_sound, _third_person


def rule_ids(analyzer, text):
    response = analyzer.analyze_sync(text, include_stats=False, use_remote=False)
    return response.issues


def find(issues, rule_id):
    return [issue for issue in issues if issue.rule_id == rule_id]


@pytest.mark.parametrize(
    "text,rule_id,suggestion",
    [
        ("We saw the the dog.", "REPEATED_WORD", "the"),
        ("I waited a hour.", "ARTICLE_A_AN", "an"),
        ("Its raining today.", "ITS_IT_IS", "It's"),
        ("Your going home now.", "YOUR_YOU_ARE", "You're"),
        ("Their going home now.", "THEIR_THEY_ARE", "They're"),
        ("She go to school every day.", "SUBJECT_VERB_AGREEMENT", "goes"),
        ("This are a test of the parser.", "SUBJECT_VERB_AGREEMENT", "is"),
        ("We should of gone.", "OF_HAVE", "should have"),
        ("In order to succeed we must try.", "WORDINESS", "to"),
        ("I do not never want that.", "DOUBLE_NEGATIVE", ""),
    ],
)
def test_rules_fire(analyzer, text, rule_id, suggestion):
    issues = find(rule_ids(analyzer, text), rule_id)
    assert issues, f"{rule_id} did not fire for {text!r}"
    if suggestion:
        assert suggestion.lower() in [value.lower() for value in issues[0].suggestions]


def test_passive_voice_detected(analyzer):
    issues = find(rule_ids(analyzer, "The report was written by the team."), "PASSIVE_VOICE")
    assert issues


def test_punctuation_spacing(analyzer):
    issues = find(rule_ids(analyzer, "Hello , world."), "SPACE_BEFORE_PUNCT")
    assert issues
    assert issues[0].suggestions == [","]


def test_sentence_capitalization_and_terminal(analyzer):
    text = "this is a test of the whole system"
    ids = {issue.rule_id for issue in rule_ids(analyzer, text)}
    assert "SENTENCE_CAPITALIZATION" in ids
    assert "TERMINAL_PUNCTUATION" in ids


def test_comma_splice(analyzer):
    text = "I finished the report, I sent it to the manager."
    assert find(rule_ids(analyzer, text), "COMMA_SPLICE")


def test_offsets_match_text(analyzer):
    text = "😀 i recieve teh mail. She go to school. Their going home , now"
    for issue in rule_ids(analyzer, text):
        assert text[issue.start:issue.end] == issue.text


@pytest.mark.parametrize(
    "word,expected",
    [
        ("hour", True),
        ("honest", True),
        ("university", False),
        ("user", False),
        ("apple", True),
        ("banana", False),
    ],
)
def test_vowel_sound(word, expected):
    assert _starts_with_vowel_sound(word) is expected


@pytest.mark.parametrize(
    "lemma,expected",
    [("go", "goes"), ("have", "has"), ("be", "is"), ("watch", "watches"), ("try", "tries"), ("walk", "walks")],
)
def test_third_person(lemma, expected):
    assert _third_person(lemma) == expected
