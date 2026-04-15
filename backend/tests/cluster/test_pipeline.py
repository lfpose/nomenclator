import numpy as np
from app.cluster.pipeline import build_components


def test_build_components_singleton_input():
    """Single string should form a single component of size 1."""
    strings = ["jefe compras"]
    matrix = np.array([[100]], dtype=np.uint8)
    result = build_components(strings, matrix, threshold=90)
    assert len(result) == 1
    assert list(result.values())[0] == [0]


def test_build_components_two_similar_merged():
    """Two similar strings should merge into one component."""
    strings = ["jefe compras", "jefe de compras"]
    # High similarity, length ratio > 0.6
    matrix = np.array([
        [100, 95],
        [95, 100],
    ], dtype=np.uint8)
    result = build_components(strings, matrix, threshold=90)
    assert len(result) == 1
    assert list(result.values())[0] == [0, 1]


def test_build_components_two_unrelated_separate():
    """Two unrelated strings should remain separate components."""
    strings = ["jefe compras", "director ventas"]
    # Low similarity
    matrix = np.array([
        [100, 45],
        [45, 100],
    ], dtype=np.uint8)
    result = build_components(strings, matrix, threshold=90)
    assert len(result) == 2
    # Both components should be singletons
    for indices in result.values():
        assert len(indices) == 1


def test_build_components_length_ratio_blocks_merge():
    """Length ratio gate should block merge even with high similarity."""
    strings = ["jefe", "jefe de operaciones internacionales"]
    # High similarity (token_set_ratio on "jefe"), but length ratio < 0.6
    # "jefe" is 4 chars, "jefe de operaciones internacionales" is 33 chars
    # ratio = 4/33 ≈ 0.12
    matrix = np.array([
        [100, 92],
        [92, 100],
    ], dtype=np.uint8)
    result = build_components(strings, matrix, threshold=90)
    assert len(result) == 2
    # Both components should be singletons
    for indices in result.values():
        assert len(indices) == 1


def test_build_components_transitive_merging():
    """Transitive merging: if a~b and b~c, then {a,b,c} form one component."""
    strings = ["jefe compras", "jefe de compras", "jefe ventas"]
    # All similar with good length ratios:
    # "jefe compras" (12 chars), "jefe de compras" (16 chars), "jefe ventas" (11 chars)
    # ratios: 12/16=0.75, 12/11=0.92, 16/11=0.69 - all > 0.6
    matrix = np.array([
        [100, 95, 88],
        [95, 100, 96],
        [88, 96, 100],
    ], dtype=np.uint8)
    result = build_components(strings, matrix, threshold=90)
    assert len(result) == 1
    component = list(result.values())[0]
    assert set(component) == {0, 1, 2}
