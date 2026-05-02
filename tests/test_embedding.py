from sakina.embedding import chunk_document, parse_record, CHUNK_CHAR_LIMIT, CHUNK_OVERLAP


# ── chunk_document ────────────────────────────────────────────────────────────

def test_chunk_no_split():
    text = "short text"
    result = chunk_document("rec1", text, {"id": "rec1"})
    assert result == [("rec1", text, {"id": "rec1"})]


def test_chunk_single_split():
    text = "x" * (CHUNK_CHAR_LIMIT + 1)
    chunks = chunk_document("rec1", text, {"id": "rec1"})
    assert len(chunks) == 2
    assert chunks[0][0] == "rec1_chunk_0"
    assert chunks[1][0] == "rec1_chunk_1"


def test_chunk_overlap():
    text = "a" * CHUNK_CHAR_LIMIT + "b" * CHUNK_CHAR_LIMIT
    chunks = chunk_document("rec1", text, {})
    # Second chunk should start CHUNK_OVERLAP chars before end of first chunk
    assert chunks[1][1][:CHUNK_OVERLAP] == "a" * CHUNK_OVERLAP


def test_chunk_preserves_meta():
    text = "x" * (CHUNK_CHAR_LIMIT + 1)
    meta = {"id": "rec1", "source": "quran"}
    chunks = chunk_document("rec1", text, meta)
    for _, _, m in chunks:
        assert m["id"] == "rec1"
        assert m["source"] == "quran"
        assert "chunk_index" in m


def test_chunk_exact_limit():
    text = "x" * CHUNK_CHAR_LIMIT
    chunks = chunk_document("rec1", text, {})
    assert len(chunks) == 1


# ── parse_record ──────────────────────────────────────────────────────────────

def test_parse_quran():
    data = {"id": "q1", "source": "quran", "reference": "2:255", "surah": "2",
            "ayah": "255", "theme": "trust", "text": "Allah — there is no deity except Him"}
    text, meta = parse_record("dataset/quran.jsonl", data)
    assert "trust" in text
    assert "Allah" in text
    assert meta["source_type"] == "Quran"
    assert meta["id"] == "q1"


def test_parse_hadith():
    data = {"id": "h1", "source": "bukhari", "reference": "6369", "number": "6369",
            "chapter": "Du'a", "theme": "prayer", "text": "Make du'a to Allah"}
    text, meta = parse_record("dataset/hadith.jsonl", data)
    assert "Du'a" in text
    assert meta["source_type"] == "Hadith"


def test_parse_article():
    data = {"id": "art1", "title": "Anxiety", "theme": "mental health", "text": "Islam and anxiety"}
    text, meta = parse_record("dataset/articles.jsonl", data)
    assert "Anxiety" in text
    assert meta["source_type"] == "Article"


def test_parse_missing_fields():
    data = {"id": "q1"}
    text, meta = parse_record("dataset/quran.jsonl", data)
    assert "N/A" in text
