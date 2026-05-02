from sakina.eval import recall_at_k


def test_recall_perfect():
    assert recall_at_k(["a", "b"], ["a", "b", "c"], k=3) == 1.0


def test_recall_partial():
    assert recall_at_k(["a", "b"], ["a", "x", "y"], k=3) == 0.5


def test_recall_miss():
    assert recall_at_k(["a", "b"], ["x", "y", "z"], k=3) == 0.0


def test_recall_k_cutoff():
    # "b" is at index 3, outside k=3 window
    assert recall_at_k(["a", "b"], ["a", "x", "y", "b"], k=3) == 0.5


def test_recall_empty_expected():
    assert recall_at_k([], ["a", "b"], k=3) == 0.0


def test_recall_at_1():
    assert recall_at_k(["a"], ["a", "b"], k=1) == 1.0
    assert recall_at_k(["a"], ["b", "a"], k=1) == 0.0
