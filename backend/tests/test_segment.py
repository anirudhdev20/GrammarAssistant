from app.nlp.segment import convert_span, split_chunks, utf16_to_index


def test_chunks_are_exact_slices():
    text = "First paragraph.\n\nSecond paragraph with more words.\n\n\nThird."
    chunks = split_chunks(text, max_chars=15000)
    assert chunks
    for chunk in chunks:
        assert chunk.text == text[chunk.start:chunk.end]
        assert chunk.end > chunk.start


def test_chunks_split_long_paragraphs():
    text = " ".join(f"Sentence number {index} is here." for index in range(400))
    chunks = split_chunks(text, max_chars=500)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 500 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks) == text


def test_utf16_conversion_with_emoji():
    text = "😀 hello"
    assert utf16_to_index(text, 0) == 0
    assert utf16_to_index(text, 2) == 1
    assert utf16_to_index(text, 3) == 2
    assert convert_span(text, 3, 8) == (2, 7)


def test_utf16_identity_for_bmp_text():
    text = "plain ascii text"
    assert convert_span(text, 3, 8) == (3, 8)
