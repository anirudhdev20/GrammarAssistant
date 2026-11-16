from app.schemas import IssueType


def spelling_issues(analyzer, text):
    response = analyzer.analyze_sync(text, include_stats=False, use_remote=False)
    return [issue for issue in response.issues if issue.type == IssueType.spelling]


def test_common_misspellings(analyzer):
    issues = {issue.text: issue for issue in spelling_issues(analyzer, "I recieve teh mail.")}
    assert "recieve" in issues
    assert "receive" in issues["recieve"].suggestions
    assert "teh" in issues
    assert "the" in issues["teh"].suggestions


def test_known_words_are_not_flagged(analyzer):
    text = "Several important sentences contain ordinary words."
    assert spelling_issues(analyzer, text) == []


def test_technical_allowlist(analyzer):
    text = "I use fastapi and spacy to build an nlp tokenizer."
    assert spelling_issues(analyzer, text) == []


def test_proper_nouns_are_skipped(analyzer):
    text = "Yesterday Anirudh wrote some code."
    assert spelling_issues(analyzer, text) == []


def test_user_dictionary(analyzer):
    analyzer.spell.add_word("zqwv")
    try:
        assert spelling_issues(analyzer, "The zqwv is ready.") == []
    finally:
        analyzer.spell.remove_word("zqwv")
