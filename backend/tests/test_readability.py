def test_stats_are_populated(analyzer):
    text = "This is a simple sentence. It has two sentences in total."
    stats = analyzer.analyze_sync(text, include_stats=True, use_remote=False).stats
    assert stats is not None
    assert stats.words > 0
    assert stats.sentences == 2
    assert stats.paragraphs == 1
    assert 0 <= stats.flesch_reading_ease <= 200
    assert stats.reading_time_seconds >= 1
    assert 0 <= stats.lexical_diversity <= 1


def test_empty_text(analyzer):
    response = analyzer.analyze_sync("", include_stats=True, use_remote=False)
    assert response.issues == []
    assert response.stats is not None
    assert response.stats.words == 0
