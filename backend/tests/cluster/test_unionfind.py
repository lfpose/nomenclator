"""Tests for UnionFind data structure."""

import time

from app.cluster.unionfind import UnionFind


def test_find_on_singleton_returns_self() -> None:
    """Finding the root of a singleton set should return the element itself."""
    uf = UnionFind(5)
    for i in range(5):
        assert uf.find(i) == i


def test_union_merges_roots() -> None:
    """Union should merge two sets by linking one root to the other."""
    uf = UnionFind(5)
    uf.union(0, 1)
    assert uf.find(0) == uf.find(1)
    assert uf.find(0) != uf.find(2)


def test_components_on_disjoint_graph() -> None:
    """Five singletons should produce five components."""
    uf = UnionFind(5)
    components = uf.components()
    assert len(components) == 5
    # Each component should have exactly one member
    for members in components.values():
        assert len(members) == 1


def test_components_on_chain() -> None:
    """Chain union(0,1), union(1,2), union(2,3) should produce one component of size 4."""
    uf = UnionFind(4)
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(2, 3)
    components = uf.components()
    assert len(components) == 1
    members = next(iter(components.values()))
    assert len(members) == 4
    assert set(members) == {0, 1, 2, 3}


def test_union_idempotent() -> None:
    """Union should be idempotent: calling it twice should have the same effect as once."""
    uf = UnionFind(5)
    uf.union(0, 1)
    uf.union(0, 1)  # Same union again
    components = uf.components()
    assert len(components) == 4  # One merged, plus three singletons
    # Find the merged component
    merged = next(iter(components.values()))
    assert len(merged) == 2


def test_components_deterministic_output() -> None:
    """Components should produce the same output for the same input."""
    uf1 = UnionFind(5)
    uf1.union(0, 1)
    uf1.union(2, 3)

    uf2 = UnionFind(5)
    uf2.union(0, 1)
    uf2.union(2, 3)

    assert uf1.components() == uf2.components()


def test_large_union_find_1000_elements_under_10ms() -> None:
    """Union-Find operations on 1000 elements should complete within 10ms."""
    n = 1000
    uf = UnionFind(n)

    start = time.perf_counter()
    # Perform many union operations
    for i in range(n - 1):
        uf.union(i, i + 1)

    # Find all roots
    for i in range(n):
        uf.find(i)

    # Get components
    components = uf.components()

    elapsed = time.perf_counter() - start
    assert elapsed < 0.01, f"Union-Find took {elapsed:.3f}s, expected < 0.01s"
    # All elements should be in one component
    assert len(components) == 1
    assert len(next(iter(components.values()))) == n
