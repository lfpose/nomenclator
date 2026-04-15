"""Union-Find (Disjoint Set) data structure with path compression and union-by-rank."""


class UnionFind:
    """Union-Find data structure for maintaining disjoint sets.

    Uses path compression in find() and union-by-rank in union()
    for near-constant amortized time complexity.
    """

    def __init__(self, n: int) -> None:
        """Initialize Union-Find with n disjoint sets."""
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """Find the root of the set containing x, with path compression."""
        while self.parent[x] != x:
            # Path compression: make x point to its grandparent
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        """Merge the sets containing x and y, using union-by-rank."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return  # Already in the same set
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def components(self) -> dict[int, list[int]]:
        """Return all components as a mapping from root to member list."""
        out: dict[int, list[int]] = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            out.setdefault(root, []).append(i)
        return out
