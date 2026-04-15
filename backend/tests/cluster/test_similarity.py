import random

import numpy as np

from app.cluster.similarity import compute_similarity, len_ratio


def test_len_ratio_identical_strings_returns_1():
    """Identical strings should have a length ratio of 1.0."""
    assert len_ratio("hello", "hello") == 1.0
    assert len_ratio("test", "test") == 1.0
    assert len_ratio("a", "a") == 1.0


def test_len_ratio_half_length_returns_half():
    """When one string is half the length of the other, ratio should be 0.5."""
    assert len_ratio("hi", "hello") == 2 / 5  # "hi" is 2 chars, "hello" is 5
    assert len_ratio("ab", "abcd") == 0.5
    assert len_ratio("hello", "hi") == 2 / 5  # symmetric


def test_len_ratio_empty_string_returns_0():
    """Empty strings should return 0.0."""
    assert len_ratio("", "hello") == 0.0
    assert len_ratio("hello", "") == 0.0
    assert len_ratio("", "") == 0.0


def test_len_ratio_symmetric():
    """len_ratio(a, b) should equal len_ratio(b, a) for random pairs."""
    random.seed(42)
    for _ in range(20):
        a = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=random.randint(1, 20)))
        b = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=random.randint(1, 20)))
        assert len_ratio(a, b) == len_ratio(b, a)


def test_compute_similarity_shape_is_NxN():
    """Similarity matrix should be NxN for N input strings."""
    strings = ["jefe compras", "jefe de compras", "director ventas"]
    matrix = compute_similarity(strings)
    assert matrix.shape == (3, 3)


def test_compute_similarity_diagonal_is_100():
    """Diagonal elements should be 100 (string compared to itself)."""
    strings = ["jefe compras", "jefe de compras", "director ventas"]
    matrix = compute_similarity(strings)
    for i in range(len(strings)):
        assert matrix[i][i] == 100


def test_compute_similarity_symmetric():
    """Similarity matrix should be symmetric."""
    strings = ["jefe compras", "jefe de compras", "director ventas"]
    matrix = compute_similarity(strings)
    for i in range(len(strings)):
        for j in range(len(strings)):
            assert matrix[i][j] == matrix[j][i]


def test_compute_similarity_jefe_compras_scores_above_90():
    """Similar variants of "jefe compras" should score above 90."""
    strings = ["jefe compras", "jefe de compras"]
    matrix = compute_similarity(strings)
    assert matrix[0][1] >= 90


def test_compute_similarity_product_vs_project_manager_scores_below_85():
    """Distinct titles should not trip threshold 90."""
    strings = ["jefe compras", "ingeniero software"]
    matrix = compute_similarity(strings)
    assert matrix[0][1] < 85
