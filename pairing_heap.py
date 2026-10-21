"""
pairing_heap.py - Member 3 module: Priority Queue ADT implemented as a Pairing Heap.
Project: Semiconductor Wafer Process Allocation & Equipment Conflict Analyzer

Run the built-in tests:  python pairing_heap.py
Reuse as a library:      from pairing_heap import PairingHeap, Wafer, Priority

Design notes
------------
* PairingHeap is a generic, reusable min-heap ADT. It knows nothing about wafers.
* AGGREGATION: the heap stores *references* to entity objects (e.g. Wafer). It does not
  create, copy or own them; the scheduler, allocator or conflict analyzer can hold the same
  Wafer. Discarding the heap never destroys a wafer that is referenced elsewhere.
* Min-heap convention: a smaller Wafer (CRITICAL < HIGH < NORMAL < LOW) is MORE urgent.
  Ties are broken by earlier arrival_time (FIFO), then by id.
* Nodes keep children in a ``subheaps`` list (the "linking structure").
* Core ADT (case study Sec. 3.3): insert, find_min, delete_min, meld (+ is_empty).
  camelCase aliases (findMin, deleteMin, isEmpty) match the document's naming.
* Support for application functions (Sec. 4: removeWaferLot, updatePriority, getNextWafer and
  the re-prioritisation step of Maintenance Impact Analysis): find_if, remove, remove_if, update.
* Every traversal/destruction is iterative, so degenerate (very deep) heaps cannot hit
  Python's recursion limit.
"""

from enum import IntEnum
from typing import Callable, Generic, List, Optional, TypeVar

T = TypeVar("T")


# =============================================================================
#  ENTITY: Wafer (the object aggregated by the heap)
# =============================================================================

class Priority(IntEnum):
    """Urgency ranks. Smaller value = higher urgency (min-heap convention)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class Wafer:
    """A pending wafer lot. Fields follow case study Sec. 2 step 1: wafer ID, process type,
    duration, preferred/valid resource class, priority (+ arrival time for FIFO tie-breaking)."""

    __slots__ = ("id", "process_type", "resource_class", "duration", "priority", "arrival_time")

    def __init__(self, id: str, process_type: str, resource_class: str,
                 duration: int, priority: Priority, arrival_time: int) -> None:
        self.id = id
        self.process_type = process_type
        self.resource_class = resource_class
        self.duration = duration
        self.priority = Priority(priority)
        self.arrival_time = arrival_time

    def set_priority(self, priority: Priority) -> None:
        """Change urgency. Only do this while NOT inside a heap; use PairingHeap.update."""
        self.priority = Priority(priority)

    def _key(self):
        return (int(self.priority), self.arrival_time, self.id)

    def __lt__(self, other: "Wafer") -> bool:
        """a < b means a is MORE urgent than b."""
        return self._key() < other._key()

    def __repr__(self) -> str:
        return (f"{self.id} [{self.priority.name.capitalize()}, {self.process_type}/"
                f"{self.resource_class}, dur={self.duration}, arr={self.arrival_time}]")


# =============================================================================
#  ADT: PairingHeap
# =============================================================================

class _Node(Generic[T]):
    """Node of the pairing heap: an element reference plus its child subheaps."""

    __slots__ = ("element", "subheaps")

    def __init__(self, element: T) -> None:
        self.element = element              # aggregated entity (e.g. wafer)
        self.subheaps: List["_Node[T]"] = []  # child heaps; each root is >= this element


class PairingHeap(Generic[T]):
    """
    Generic min-oriented Pairing Heap (priority queue ADT).

    ``less(a, b)`` must be a strict weak ordering returning True when a is higher priority
    than b. The default uses ``a < b`` (so Wafer's __lt__ applies).

    Complexity (n = number of elements):
        insert      O(1) worst case
        find_min    O(1)
        meld        O(1)
        delete_min  O(log n) amortized (O(n) worst case for a single call)
        is_empty    O(1)
        find_if     O(n)
        remove      O(n) to locate + O(log n) amortized to repair
        update      O(n) to locate + O(log n) amortized to repair/reinsert
        remove_if   O(n + k*n) for k matches
    """

    def __init__(self, less: Optional[Callable[[T, T], bool]] = None) -> None:
        self._less: Callable[[T, T], bool] = less if less is not None else (lambda a, b: a < b)
        self._root: Optional[_Node[T]] = None
        self._size = 0

    # ------------------------------------------------------------------ core ADT

    def insert(self, element: T) -> None:
        """Insert an entity reference (aggregation: the heap does not copy or own it). O(1)."""
        if element is None:
            raise ValueError("PairingHeap.insert: element must not be None")
        self._root = self._meld_nodes(self._root, _Node(element))
        self._size += 1

    def find_min(self) -> T:
        """Return the highest-priority element without removing it. O(1).
        Raises IndexError if the heap is empty."""
        if self._root is None:
            raise IndexError("PairingHeap.find_min: heap is empty")
        return self._root.element

    def delete_min(self) -> T:
        """Remove and return the highest-priority element using the standard two-pass pairing:
        (1) meld children pairwise left-to-right, (2) meld the results right-to-left.
        O(log n) amortized. Raises IndexError if the heap is empty."""
        if self._root is None:
            raise IndexError("PairingHeap.delete_min: heap is empty")
        top = self._root.element
        children = self._root.subheaps
        self._root.subheaps = []
        self._root = self._merge_pairs(children)
        self._size -= 1
        return top

    def meld(self, other: "PairingHeap[T]") -> None:
        """H1.meld(H2): move every element of ``other`` into this heap; ``other`` is left
        empty. Both heaps must use equivalent ordering. O(1)."""
        if other is self or other._root is None:
            return
        self._root = self._meld_nodes(self._root, other._root)
        self._size += other._size
        other._root = None
        other._size = 0

    @staticmethod
    def meld_heaps(h1: "PairingHeap[T]", h2: "PairingHeap[T]") -> "PairingHeap[T]":
        """Two-heap form from the case study, meld(H1, H2): returns a NEW heap holding all
        elements of both; h1 and h2 are left empty. O(1)."""
        result: PairingHeap[T] = PairingHeap(h1._less)
        result.meld(h1)
        result.meld(h2)
        return result

    def is_empty(self) -> bool:
        """True if there are no pending elements. O(1)."""
        return self._root is None

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._root is not None

    # ------------------------------------------- support for application functions

    def find_if(self, pred: Callable[[T], bool]) -> Optional[T]:
        """Return the first element (unspecified order) satisfying pred, or None. O(n)."""
        stack = [self._root] if self._root is not None else []
        while stack:
            node = stack.pop()
            if pred(node.element):
                return node.element
            stack.extend(node.subheaps)
        return None

    def remove(self, target: T) -> bool:
        """Remove a specific element (matched by identity, ``is``) from anywhere in the heap
        (removeWaferLot support). Returns True if found and removed.
        O(n) to locate + O(log n) amortized to repair."""
        if self._root is None or target is None:
            return False
        stack = [(self._root, None)]  # (node, parent)
        while stack:
            node, parent = stack.pop()
            if node.element is target:
                self._detach(node, parent)
                return True
            for child in node.subheaps:
                stack.append((child, node))
        return False

    def remove_if(self, pred: Callable[[T], bool]) -> int:
        """Remove every element satisfying pred. Returns the number removed."""
        victims: List[T] = []
        stack = [self._root] if self._root is not None else []
        while stack:
            node = stack.pop()
            if pred(node.element):
                victims.append(node.element)
            stack.extend(node.subheaps)
        return sum(1 for v in victims if self.remove(v))

    def update(self, target: T, mutate: Callable[[T], None]) -> bool:
        """Change an element's priority (updatePriority support): remove it, apply
        ``mutate(element)``, reinsert it so the heap invariant always holds.
        Returns True if the element was in the heap."""
        if not self.remove(target):
            return False
        mutate(target)
        self.insert(target)
        return True

    def clear(self) -> None:
        """Remove all elements iteratively. O(n)."""
        pending = [self._root] if self._root is not None else []
        self._root = None
        self._size = 0
        while pending:
            node = pending.pop()
            pending.extend(node.subheaps)
            node.subheaps = []

    def __del__(self) -> None:  # iterative teardown: deep chains cannot overflow the stack
        try:
            self.clear()
        except Exception:
            pass

    # camelCase aliases matching the case-study document
    findMin = find_min
    deleteMin = delete_min
    isEmpty = is_empty

    # ------------------------------------------------------------------ internals

    def _meld_nodes(self, a: Optional[_Node[T]], b: Optional[_Node[T]]) -> Optional[_Node[T]]:
        """Link two heap roots: the loser becomes the last child of the winner. O(1)."""
        if a is None:
            return b
        if b is None:
            return a
        if self._less(b.element, a.element):
            a, b = b, a
        a.subheaps.append(b)
        return a

    def _merge_pairs(self, heaps: List[_Node[T]]) -> Optional[_Node[T]]:
        """Two-pass pairing of a list of heaps into one heap."""
        n = len(heaps)
        if n == 0:
            return None
        # Pass 1 (left to right): meld adjacent pairs.
        paired: List[_Node[T]] = []
        for i in range(0, n - 1, 2):
            paired.append(self._meld_nodes(heaps[i], heaps[i + 1]))
        if n % 2 == 1:
            paired.append(heaps[-1])
        # Pass 2 (right to left): accumulate into the last heap.
        result = paired[-1]
        for i in range(len(paired) - 2, -1, -1):
            result = self._meld_nodes(paired[i], result)
        return result

    def _detach(self, node: _Node[T], parent: Optional[_Node[T]]) -> None:
        """Cut ``node`` out of the heap and re-link its children. parent None means root."""
        if parent is None:
            self.delete_min()
            return
        for i, sibling in enumerate(parent.subheaps):
            if sibling is node:
                del parent.subheaps[i]
                break
        merged = self._merge_pairs(node.subheaps)
        node.subheaps = []
        self._root = self._meld_nodes(self._root, merged)
        self._size -= 1


#: Priority queue of pending wafer lots, ordered by Wafer.__lt__.
def WaferPriorityQueue() -> "PairingHeap[Wafer]":
    return PairingHeap()


# =============================================================================
#  TEST / DEMO
# =============================================================================

def _run_tests() -> None:
    import random

    passed = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal passed
        if not cond:
            raise AssertionError(f"[FAIL] {msg}")
        passed += 1
        print(f"  [PASS] {msg}")

    def mk(id, proc, rc, dur, pr, arr) -> Wafer:
        return Wafer(id, proc, rc, dur, pr, arr)

    def drain_ids(h: PairingHeap) -> str:
        out = []
        while not h.is_empty():
            out.append(h.delete_min().id)
        return " ".join(out)

    print("=== Test 1: insert + find_min ===")
    heap = WaferPriorityQueue()
    check(heap.is_empty(), "new heap is empty")
    w101 = mk("W101", "Etching", "ETCH", 30, Priority.NORMAL, 1)
    w202 = mk("W202", "Lithography", "LITH", 45, Priority.HIGH, 2)
    w204 = mk("W204", "Etching", "ETCH", 30, Priority.CRITICAL, 3)
    w305 = mk("W305", "Cleaning", "CLEAN", 10, Priority.LOW, 4)
    w206 = mk("W206", "Etching", "ETCH", 25, Priority.HIGH, 5)
    for w in (w101, w202, w204, w305, w206):
        heap.insert(w)
    check(not heap.is_empty() and len(heap) == 5, "heap holds 5 pending lots")
    print("  Most urgent:", heap.find_min())
    check(heap.find_min().id == "W204", "find_min returns W204 (Critical)")
    check(len(heap) == 5, "find_min does not remove")
    check(heap.findMin() is w204, "aggregation: heap references the SAME wafer object")

    print("\n=== Test 2: delete_min ordering ===")
    for wid in ["W204", "W202", "W206", "W101", "W305"]:
        w = heap.delete_min()
        print("  Dequeued:", w)
        check(w.id == wid, f"dequeued {wid} in correct order")
    check(heap.is_empty(), "heap empty after draining")
    check(w204.id == "W204", "wafer object outlives heap removal (aggregation)")
    for name, fn in (("delete_min", heap.delete_min), ("find_min", heap.find_min)):
        try:
            fn()
            ok = False
        except IndexError:
            ok = True
        check(ok, f"{name} on empty heap raises IndexError")

    print("\n=== Test 3: meld two heaps (H1.meld(H2)) ===")
    a, b = WaferPriorityQueue(), WaferPriorityQueue()
    a.insert(mk("A1", "Etching", "ETCH", 30, Priority.NORMAL, 10))
    a.insert(mk("A2", "Lithography", "LITH", 40, Priority.HIGH, 11))
    b.insert(mk("B1", "Deposition", "DEPO", 20, Priority.CRITICAL, 12))
    b.insert(mk("B2", "Cleaning", "CLEAN", 15, Priority.LOW, 13))
    b.insert(mk("B3", "Implant", "IMPL", 25, Priority.NORMAL, 9))
    a.meld(b)
    check(len(a) == 5, "melded heap has 5 lots")
    check(b.is_empty() and len(b) == 0, "source heap is emptied after meld")
    check(a.find_min().id == "B1", "melded min is B1 (Critical)")
    check(drain_ids(a) == "B1 A2 B3 A1 B2", "melded order correct")
    a.meld(a)
    check(a.is_empty(), "self-meld / empty meld is safe")

    print("\n=== Test 4: static meld(H1,H2) from the case study ===")
    h1, h2 = WaferPriorityQueue(), WaferPriorityQueue()
    h1.insert(mk("X1", "Etching", "ETCH", 5, Priority.NORMAL, 1))
    h2.insert(mk("X2", "Etching", "ETCH", 5, Priority.CRITICAL, 2))
    merged = PairingHeap.meld_heaps(h1, h2)
    check(len(merged) == 2 and h1.is_empty() and h2.is_empty(),
          "meld(H1,H2) returns merged heap, inputs emptied")
    check(merged.find_min().id == "X2", "merged min is X2")

    print("\n=== Test 5: tie-breaking (FIFO by arrival time) ===")
    t = WaferPriorityQueue()
    t.insert(mk("T3", "Etching", "ETCH", 5, Priority.HIGH, 30))
    t.insert(mk("T1", "Etching", "ETCH", 5, Priority.HIGH, 10))
    t.insert(mk("T2", "Etching", "ETCH", 5, Priority.HIGH, 20))
    check(drain_ids(t) == "T1 T2 T3", "earliest arrival first among equal priorities")

    print("\n=== Test 6: removeWaferLot / updatePriority / find_if support ===")
    q = WaferPriorityQueue()
    r1 = mk("R1", "Etching", "ETCH", 10, Priority.CRITICAL, 1)
    r2 = mk("R2", "Lithography", "LITH", 10, Priority.HIGH, 2)
    r3 = mk("R3", "Etching", "ETCH", 10, Priority.NORMAL, 3)
    r4 = mk("R4", "Cleaning", "CLEAN", 10, Priority.NORMAL, 4)
    r5 = mk("R5", "Etching", "ETCH", 10, Priority.LOW, 5)
    for w in (r1, r2, r3, r4, r5):
        q.insert(w)
    check(q.find_if(lambda w: w.id == "R3") is r3, "find_if locates wafer by id (same object)")
    check(q.find_if(lambda w: w.id == "NOPE") is None, "find_if returns None if absent")
    check(q.remove(r2), "remove arbitrary (non-root) wafer R2")
    check(not q.remove(r2), "removing it again returns False")
    check(len(q) == 4, "size decremented after remove")
    check(q.update(r5, lambda w: w.set_priority(Priority.CRITICAL)), "update R5 -> Critical")
    check(q.find_min().id == "R1", "R1 (earlier arrival) still wins the Critical tie")
    check(q.remove(r1), "remove current root R1")
    check(q.find_min().id == "R5", "after root removal, R5 (now Critical) is next")
    cnt = q.remove_if(lambda w: w.process_type == "Etching")
    check(cnt == 2 and len(q) == 1, "remove_if deleted R5 and R3 (Etching), leaving 1")
    check(drain_ids(q) == "R4", "remaining lot is R4")

    print("\n=== Test 7: Maintenance-Impact style re-prioritisation ===")
    affected = WaferPriorityQueue()
    affected.insert(mk("M3", "Etching", "ETCH", 10, Priority.NORMAL, 3))
    affected.insert(mk("M1", "Etching", "ETCH", 10, Priority.CRITICAL, 1))
    affected.insert(mk("M2", "Etching", "ETCH", 10, Priority.HIGH, 2))
    check(drain_ids(affected) == "M1 M2 M3", "affected wafers re-evaluated in priority order")

    print("\n=== Test 8: randomized stress vs. sorted() (20000 lots, with removals) ===")
    rng = random.Random(12345)
    s1, s2 = WaferPriorityQueue(), WaferPriorityQueue()
    everything: List[Wafer] = []
    for i in range(20000):
        w = mk(f"S{i}", "Proc", "RC", 1, Priority(rng.randint(0, 3)), rng.randint(0, 1000))
        everything.append(w)
        (s1 if i % 2 else s2).insert(w)
    s1.meld(s2)
    rng.shuffle(everything)
    for _ in range(300):
        check_ok = s1.remove(everything.pop())
        assert check_ok, "stress remove failed"
    everything.sort()
    ok = len(s1) == len(everything)
    for expected_wafer in everything:
        if not ok:
            break
        ok = s1.delete_min() is expected_wafer
    check(ok and s1.is_empty(), "19700 remaining lots dequeue in fully sorted order")

    print("\n=== Test 9: degenerate deep heap (no recursion / stack problems) ===")
    deep = WaferPriorityQueue()
    for i in range(200000, 0, -1):  # each insert becomes the new root over a long chain
        deep.insert(mk(f"D{i}", "Proc", "RC", 1, Priority.NORMAL, i))
    check(len(deep) == 200000, "200000 lots inserted")
    check(deep.find_min().id == "D1", "deep heap min is correct")
    del deep  # iterative teardown via __del__
    check(True, "deep heap destroyed safely")

    print(f"\nAll {passed} checks passed.")


if __name__ == "__main__":
    _run_tests()
