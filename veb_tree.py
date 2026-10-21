"""Reusable Van Emde Boas (vEB) tree for integer keys.

The tree stores unique integer keys in the bounded universe
    0 <= key < universe_size
where universe_size is a power of two and at least 2.

This module is application-independent: it does not know about wafers,
equipment, resources, or reservations.
"""

from __future__ import annotations

from typing import Optional


class VEBTree:
    """Van Emde Boas tree supporting O(log log U) ordered-set operations.

    Args:
        universe_size: Power of two, at least 2. Valid keys are from
            0 to universe_size - 1.

    Public operations:
        insert(key)       -> bool: True if inserted, False if already present
        delete(key)       -> bool: True if deleted, False if not present
        search(key)       -> bool
        contains(key)     -> bool (alias for search)
        minimum()         -> smallest key, or None when empty
        maximum()         -> largest key, or None when empty
        predecessor(key)  -> greatest stored key strictly less than key, or None
        successor(key)    -> smallest stored key strictly greater than key, or None
    """

    def __init__(self, universe_size: int) -> None:
        if isinstance(universe_size, bool) or not isinstance(universe_size, int):
            raise TypeError("universe_size must be an integer")
        if universe_size < 2 or (universe_size & (universe_size - 1)) != 0:
            raise ValueError("universe_size must be a power of two >= 2")

        self.u: int = universe_size
        self.min: Optional[int] = None
        self.max: Optional[int] = None

        # A universe of size 2 is the base case and needs no children.
        if self.u > 2:
            # Split the key into high and low parts. Either half may have
            # different sizes when log2(U) is odd, but both remain powers of 2.
            self.lower_bits = self.u.bit_length() // 2
            self.lower_size = 1 << self.lower_bits
            self.upper_size = self.u // self.lower_size

            self.summary = VEBTree(self.upper_size)
            self.clusters = [
                VEBTree(self.lower_size) for _ in range(self.upper_size)
            ]

    def _validate_key(self, key: int) -> None:
        """Raise a helpful exception if key is outside this tree's universe."""
        if isinstance(key, bool) or not isinstance(key, int):
            raise TypeError("key must be an integer")
        if key < 0 or key >= self.u:
            raise ValueError(f"key must be in the range 0..{self.u - 1}")

    def _require_children(self) -> None:
        """Guard decomposition helpers, which do not apply to U == 2."""
        if self.u == 2:
            raise ValueError("high/low/index are not used for universe size 2")

    # Key decomposition helpers. These are useful for learning/debugging too.
    def high(self, key: int) -> int:
        self._validate_key(key)
        self._require_children()
        return key // self.lower_size

    def low(self, key: int) -> int:
        self._validate_key(key)
        self._require_children()
        return key % self.lower_size

    def index(self, high: int, low: int) -> int:
        self._require_children()
        if not isinstance(high, int) or isinstance(high, bool):
            raise TypeError("high must be an integer")
        if not isinstance(low, int) or isinstance(low, bool):
            raise TypeError("low must be an integer")
        if not (0 <= high < self.upper_size):
            raise ValueError(f"high must be in the range 0..{self.upper_size - 1}")
        if not (0 <= low < self.lower_size):
            raise ValueError(f"low must be in the range 0..{self.lower_size - 1}")
        return high * self.lower_size + low

    def is_empty(self) -> bool:
        """Return True when the tree contains no keys."""
        return self.min is None

    def search(self, key: int) -> bool:
        """Return True if key is present."""
        self._validate_key(key)

        if self.min is None:
            return False
        if key == self.min or key == self.max:
            return True
        if self.u == 2:
            return False

        return self.clusters[self.high(key)].search(self.low(key))

    def contains(self, key: int) -> bool:
        """Alias for search(key)."""
        return self.search(key)

    def insert(self, key: int) -> bool:
        """Insert key. Return False if it was already present."""
        self._validate_key(key)
        if self.search(key):
            return False
        self._insert_empty(key)
        return True

    def _insert_empty(self, key: int) -> None:
        """Insert a known-absent key; used recursively by the tree."""
        if self.min is None:
            self.min = self.max = key
            return

        if self.u == 2:
            # key is absent and both values can only be 0 or 1.
            if key < self.min:
                self.min = key
            else:
                self.max = key
            return

        if key < self.min:
            key, self.min = self.min, key

        high_part = self.high(key)
        low_part = self.low(key)
        cluster = self.clusters[high_part]

        if cluster.min is None:
            self.summary.insert(high_part)
            cluster._insert_empty(low_part)
        else:
            cluster.insert(low_part)

        if key > self.max:
            self.max = key

    def delete(self, key: int) -> bool:
        """Delete key. Return False if it was not present."""
        self._validate_key(key)
        if not self.search(key):
            return False
        self._delete(key)
        return True

    def _delete(self, key: int) -> None:
        """Delete a known-present key; used recursively by the tree."""
        if self.min == self.max:
            self.min = self.max = None
            return

        if self.u == 2:
            # Exactly one of {0, 1} remains. Do not infer this from min alone:
            # the actual key being deleted determines the survivor.
            remaining = self.max if key == self.min else self.min
            self.min = self.max = remaining
            return

        if key == self.min:
            # The true minimum is stored outside the clusters. Promote the
            # smallest key from the first non-empty cluster to be the minimum.
            first_cluster = self.summary.minimum()
            key = self.index(
                first_cluster,
                self.clusters[first_cluster].minimum(),
            )
            self.min = key

        high_part = self.high(key)
        low_part = self.low(key)
        cluster = self.clusters[high_part]
        cluster._delete(low_part)

        if cluster.min is None:
            # The cluster became empty; remove its index from the summary.
            self.summary._delete(high_part)

            if self.summary.min is None:
                # No cluster has keys left, so the top-level minimum is also max.
                self.max = self.min
            elif key == self.max:
                last_cluster = self.summary.maximum()
                self.max = self.index(
                    last_cluster,
                    self.clusters[last_cluster].maximum(),
                )
        elif key == self.max:
            self.max = self.index(high_part, cluster.maximum())

    def minimum(self) -> Optional[int]:
        """Return the smallest stored key, or None if empty."""
        return self.min

    def maximum(self) -> Optional[int]:
        """Return the largest stored key, or None if empty."""
        return self.max

    def successor(self, key: int) -> Optional[int]:
        """Return the smallest stored key strictly greater than key, or None."""
        self._validate_key(key)

        if self.min is None or key >= self.max:
            return None
        if key < self.min:
            return self.min
        if self.u == 2:
            # The only remaining possibility is that key == 0 and 1 exists.
            return self.max

        high_part = self.high(key)
        low_part = self.low(key)
        cluster = self.clusters[high_part]

        if cluster.max is not None and low_part < cluster.max:
            offset = cluster.successor(low_part)
            if offset is not None:
                return self.index(high_part, offset)

        next_cluster = self.summary.successor(high_part)
        if next_cluster is None:
            return None

        return self.index(next_cluster, self.clusters[next_cluster].minimum())

    def predecessor(self, key: int) -> Optional[int]:
        """Return the largest stored key strictly less than key, or None."""
        self._validate_key(key)

        if self.min is None or key <= self.min:
            return None
        if key > self.max:
            return self.max
        if self.u == 2:
            # The only remaining possibility is that key == 1 and 0 exists.
            return self.min

        high_part = self.high(key)
        low_part = self.low(key)
        cluster = self.clusters[high_part]

        if cluster.min is not None and low_part > cluster.min:
            offset = cluster.predecessor(low_part)
            if offset is not None:
                return self.index(high_part, offset)

        previous_cluster = self.summary.predecessor(high_part)
        if previous_cluster is None:
            return self.min

        return self.index(
            previous_cluster,
            self.clusters[previous_cluster].maximum(),
        )

    def __len__(self) -> int:
        """Return the number of stored keys (calculated by traversal)."""
        if self.min is None:
            return 0
        if self.u == 2:
            return 1 if self.min == self.max else 2

        count = 1  # The top-level minimum is stored separately.
        for cluster in self.clusters:
            if cluster.min is not None:
                count += len(cluster)
        return count

    def __repr__(self) -> str:
        """Return a compact debug representation."""
        return f"VEBTree(universe_size={self.u}, min={self.min}, max={self.max})"


if __name__ == "__main__":
    # Simple demonstration: valid keys are 0 through 15.
    tree = VEBTree(16)
    for value in (3, 7, 2, 12, 5, 9):
        tree.insert(value)

    print("Search 7:", tree.search(7))
    print("Search 4:", tree.search(4))
    print("Minimum:", tree.minimum())
    print("Maximum:", tree.maximum())
    print("Successor of 5:", tree.successor(5))
    print("Predecessor of 7:", tree.predecessor(7))

    tree.delete(7)
    print("After deleting 7:")
    print("Search 7:", tree.search(7))
    print("Minimum:", tree.minimum())
    print("Maximum:", tree.maximum())
    print("Remaining keys:", [x for x in range(tree.u) if tree.search(x)])
