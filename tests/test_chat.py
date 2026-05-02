from sakina.chat import build_context


def _passage(doc_id: str, text: str = "passage text", **extra) -> dict:
    return {"id": doc_id, "document": text, "reference": f"ref:{doc_id}", **extra}


def test_build_context_basic():
    passages = [_passage("q1"), _passage("h1")]
    xml, ids = build_context(passages)
    assert "q1" in xml
    assert "h1" in xml
    assert ids == ["q1", "h1"]


def test_build_context_deduplicates_chunk_ids():
    # Two chunks of the same source record share metadata id "q1"
    p1 = _passage("q1")
    p2 = {"id": "q1", "document": "chunk 2 text", "reference": "ref:q1"}
    _, ids = build_context([p1, p2])
    assert ids.count("q1") == 1


def test_build_context_xml_escapes_special_chars():
    passages = [_passage("q1", text="text with <tags> & 'quotes'")]
    xml, _ = build_context(passages)
    assert "<tags>" not in xml
    assert "&amp;" in xml or "&lt;" in xml


def test_build_context_empty():
    xml, ids = build_context([])
    assert ids == []
    assert "<documents>" in xml


def test_build_context_preserves_order():
    passages = [_passage("c"), _passage("a"), _passage("b")]
    _, ids = build_context(passages)
    assert ids == ["c", "a", "b"]
