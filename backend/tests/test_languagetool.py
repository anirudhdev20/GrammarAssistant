from app.config import Settings
from app.nlp.languagetool import LanguageToolClient
from app.nlp.segment import Chunk
from app.schemas import IssueSource, IssueType, Severity


def make_client():
    return LanguageToolClient(Settings(lt_enabled=True))


def test_maps_utf16_offsets_and_chunk_origin():
    client = make_client()
    chunk = Chunk("😀 hello there", 10, 24)
    payload = {
        "matches": [
            {
                "offset": 3,
                "length": 5,
                "message": "Possible spelling mistake",
                "replacements": [{"value": "hello"}],
                "rule": {"id": "MORFOLOGIK_RULE_EN_US", "category": {"id": "TYPOS"}, "issueType": "misspelling"},
            }
        ]
    }
    issues = client._map_matches(payload, chunk)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.text == "hello"
    assert (issue.start, issue.end) == (12, 17)
    assert issue.type is IssueType.spelling
    assert issue.severity is Severity.error
    assert issue.source is IssueSource.language_tool
    assert issue.suggestions == ["hello"]
    assert issue.rule_id == "MORFOLOGIK_RULE_EN_US"


def test_maps_bmp_offsets_without_conversion():
    client = make_client()
    chunk = Chunk("teh cat", 0, 7)
    payload = {
        "matches": [
            {
                "offset": 0,
                "length": 3,
                "message": "Possible spelling mistake",
                "replacements": [{"value": "the"}],
                "rule": {"id": "MORFOLOGIK_RULE_EN_US", "category": {"id": "TYPOS"}},
            }
        ]
    }
    issue = client._map_matches(payload, chunk)[0]
    assert issue.text == "teh"
    assert (issue.start, issue.end) == (0, 3)
    assert issue.type is IssueType.spelling


def test_limits_suggestions_and_handles_missing_fields():
    client = make_client()
    chunk = Chunk("some text", 5, 14)
    payload = {
        "matches": [
            {
                "offset": 0,
                "length": 4,
                "message": "Style issue",
                "replacements": [{"value": f"word{i}"} for i in range(10)],
                "rule": {"id": "STYLE_RULE", "category": {"id": "STYLE"}},
            }
        ]
    }
    issue = client._map_matches(payload, chunk)[0]
    assert issue.type is IssueType.style
    assert issue.severity is Severity.suggestion
    assert len(issue.suggestions) == client.settings.max_suggestions


def test_classifies_grammar_and_unknown_categories():
    client = make_client()
    chunk = Chunk("some text", 0, 9)
    payload = {
        "matches": [
            {"offset": 0, "length": 4, "message": "Grammar", "rule": {"category": {"id": "GRAMMAR"}}},
            {"offset": 5, "length": 4, "message": "Other", "rule": {"category": {"id": "UNKNOWN"}}},
        ]
    }
    issues = client._map_matches(payload, chunk)
    assert issues[0].type is IssueType.grammar
    assert issues[1].type is IssueType.grammar
