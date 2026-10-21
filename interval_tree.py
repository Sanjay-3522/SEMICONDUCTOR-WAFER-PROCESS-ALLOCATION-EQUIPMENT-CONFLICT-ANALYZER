# Member 2: Reusable Interval Tree
# File: interval_tree.py
#
# Intervals are represented as (start, end) tuples.
# Optional payloads can be attached to intervals.
# Intervals overlap when start1 <= end2 and start2 <= end1.
# This implementation uses a randomized-priority treap augmented with max_end.

import random


class IntervalNode:
    def __init__(self, start, end, payload=None):
        if start > end:
            raise ValueError("Interval start cannot be greater than end")

        self.start = start
        self.end = end
        self.payload = payload
        self.max_end = end
        self.priority = random.random()
        self.left = None
        self.right = None


class IntervalTree:
    def __init__(self):
        self.root = None
        self._count = 0

    def __len__(self):
        return self._count

    def is_empty(self):
        return self.root is None

    @staticmethod
    def _key(node):
        return (node.start, node.end, id(node))

    @staticmethod
    def _update(node):
        if node is not None:
            node.max_end = node.end
            if node.left is not None:
                node.max_end = max(node.max_end, node.left.max_end)
            if node.right is not None:
                node.max_end = max(node.max_end, node.right.max_end)
        return node

    @staticmethod
    def _rotate_right(node):
        new_root = node.left
        node.left = new_root.right
        new_root.right = node
        IntervalTree._update(node)
        IntervalTree._update(new_root)
        return new_root

    @staticmethod
    def _rotate_left(node):
        new_root = node.right
        node.right = new_root.left
        new_root.left = node
        IntervalTree._update(node)
        IntervalTree._update(new_root)
        return new_root

    def _insert(self, root, new_node):
        if root is None:
            return new_node

        if (new_node.start, new_node.end, id(new_node)) < (
            root.start, root.end, id(root)
        ):
            root.left = self._insert(root.left, new_node)
            if root.left.priority < root.priority:
                root = self._rotate_right(root)
        else:
            root.right = self._insert(root.right, new_node)
            if root.right.priority < root.priority:
                root = self._rotate_left(root)

        return self._update(root)

    def insert_interval(self, interval, payload=None):
        start, end = self._read_interval(interval)
        node = IntervalNode(start, end, payload)
        self.root = self._insert(self.root, node)
        self._count += 1
        return node

    def _merge(self, left, right):
        if left is None:
            return right
        if right is None:
            return left

        if left.priority < right.priority:
            left.right = self._merge(left.right, right)
            return self._update(left)

        right.left = self._merge(left, right.left)
        return self._update(right)

    def _delete(self, root, target_key):
        if root is None:
            return None, False

        root_key = (root.start, root.end, id(root))

        if root_key == target_key:
            return self._merge(root.left, root.right), True

        if target_key < root_key:
            root.left, deleted = self._delete(root.left, target_key)
        else:
            root.right, deleted = self._delete(root.right, target_key)

        return self._update(root), deleted

    def delete_interval(self, interval_or_node):
        # A node returned by insert_interval can be passed to delete it exactly.
        if isinstance(interval_or_node, IntervalNode):
            node = interval_or_node
        else:
            start, end = self._read_interval(interval_or_node)
            node = self._find_exact(self.root, start, end)

        if node is None:
            return False

        self.root, deleted = self._delete(
            self.root, (node.start, node.end, id(node))
        )
        if deleted:
            self._count -= 1
        return deleted

    @staticmethod
    def _read_interval(interval):
        if not isinstance(interval, (tuple, list)) or len(interval) != 2:
            raise ValueError("Interval must be a (start, end) tuple or list")
        start, end = interval
        if start > end:
            raise ValueError("Interval start cannot be greater than end")
        return start, end

    def _find_exact(self, root, start, end):
        if root is None:
            return None
        if root.start == start and root.end == end:
            return root
        found = self._find_exact(root.left, start, end)
        if found is not None:
            return found
        return self._find_exact(root.right, start, end)

    @staticmethod
    def _overlaps(node, start, end):
        # Closed intervals: endpoints touching counts as overlap.
        return node.start <= end and start <= node.end

    def find_overlap(self, interval):
        start, end = self._read_interval(interval)
        node = self._find_overlap(self.root, start, end)
        return self._as_record(node) if node is not None else None

    def _find_overlap(self, node, start, end):
        if node is None:
            return None

        if self._overlaps(node, start, end):
            return node

        if node.left is not None and node.left.max_end >= start:
            found = self._find_overlap(node.left, start, end)
            if found is not None:
                return found

        if node.start <= end:
            return self._find_overlap(node.right, start, end)

        return None

    def find_all_overlaps(self, interval):
        start, end = self._read_interval(interval)
        result = []
        self._collect_overlaps(self.root, start, end, result)
        return result

    def _collect_overlaps(self, node, start, end, result):
        if node is None or node.max_end < start:
            return

        if node.left is not None:
            self._collect_overlaps(node.left, start, end, result)

        if self._overlaps(node, start, end):
            result.append(self._as_record(node))

        if node.start <= end and node.right is not None:
            self._collect_overlaps(node.right, start, end, result)

    @staticmethod
    def _as_record(node):
        return {
            "start": node.start,
            "end": node.end,
            "payload": node.payload,
        }

    def check_conflict(self, interval):
        return self.find_overlap(interval) is not None

    def inorder(self):
        result = []

        def traverse(node):
            if node is None:
                return
            traverse(node.left)
            result.append(self._as_record(node))
            traverse(node.right)

        traverse(self.root)
        return result


# Basic standalone test
if __name__ == "__main__":
    tree = IntervalTree()

    tree.insert_interval((10, 20), payload="Reservation A")
    tree.insert_interval((25, 35), payload="Reservation B")
    tree.insert_interval((15, 27), payload="Reservation C")
    tree.insert_interval((40, 50), payload="Reservation D")

    print("All intervals:", tree.inorder())
    print("One overlap with (18, 22):", tree.find_overlap((18, 22)))
    print("All overlaps with (18, 30):", tree.find_all_overlaps((18, 30)))
    print("Conflict with (21, 24):", tree.check_conflict((21, 24)))
    print("Conflict with (22, 26):", tree.check_conflict((22, 26)))

    print("Delete Reservation A:", tree.delete_interval((10, 20)))
    print("Remaining intervals:", tree.inorder())
