# SEMICONDUCTOR-WAFER-PROCESS-ALLOCATION-EQUIPMENT-CONFLICT-ANALYZER
# Semiconductor Wafer Process Allocation & Equipment Conflict Analyzer

An in-memory simulation for prioritizing semiconductor wafer lots, allocating available processing resources, detecting equipment scheduling conflicts, and handling maintenance-related reallocations using reusable data structures.

## 1. Project Overview

Semiconductor wafer fabrication involves multiple wafer lots, processing requirements, equipment resources, reservations, and maintenance schedules. A wafer must be assigned to a compatible resource and a valid processing window without conflicting with existing reservations or equipment downtime.

This project simulates that process using three core data structures:

- **Van Emde Boas (vEB) Tree** — manages available integer resource or slot identifiers and supports predecessor/successor searches.
- **Interval Tree** — stores time intervals and identifies overlapping reservations and maintenance windows.
- **Pairing Heap** — prioritizes pending wafer lots so higher-priority wafers can be considered first.

The application connects these structures to perform allocation, conflict detection, alternative-resource selection, and maintenance-impact analysis.

The project is designed as an **in-memory application**. It does not require a database or a separate global optimization algorithm.

## 2. Problem Statement

A wafer-processing facility must decide:

1. Which pending wafer should be processed next?
2. Which compatible resource or available slot can be considered?
3. Does the requested processing window conflict with an existing reservation, maintenance period, or calibration interval?
4. If the requested allocation is unavailable, can another suitable resource be found?
5. When equipment fails or enters maintenance, which reservations are affected, and which wafers can be reallocated?

A conventional implementation using basic collections may require repeated searches to answer these questions. This project demonstrates how specialized data structures can support the required operations and work together within a single application.

## 3. Project Objectives

- Implement three reusable data structures independently of the semiconductor application.
- Model wafer lots, equipment resources, available slots, and reservations as application entities.
- Establish explicit aggregation relationships between application managers and the data structures.
- Schedule pending wafers according to priority.
- Identify available resource or slot candidates.
- Detect reservation and maintenance conflicts.
- Search for alternative resources when an allocation cannot proceed.
- Analyze the impact of maintenance and equipment failures.
- Reallocate affected wafers where possible and retain unresolved wafers in the pending queue.
- Demonstrate the complete workflow through an integrated Python program.

## 4. Technology and Scope

| Item | Description |
|---|---|
| Programming language | Python |
| Data structures | Van Emde Boas Tree, Interval Tree, Pairing Heap |
| Application model | In-memory simulation |
| User interface | Command-line menu or demonstration interface |
| Database | Not required |
| Main application domain | Semiconductor wafer processing and equipment scheduling |

The project focuses on data-structure implementation, integration, and application behavior rather than real semiconductor equipment control.

## 5. Core Data Structures

### 5.1 Van Emde Boas Tree

**Purpose:** Maintain a set of available integer resource or process-slot identifiers.

Required operations:

- `insert(x)` — insert an integer key.
- `delete(x)` — remove a key.
- `search(x)` — check whether a key exists.
- `minimum()` — obtain the smallest key.
- `maximum()` — obtain the largest key.
- `predecessor(x)` — find the largest key smaller than `x`.
- `successor(x)` — find the smallest key greater than `x`.

**Application:** When the scheduler needs a candidate, the resource-slot manager uses the tree to search available integer identifiers. The application then checks whether the corresponding resource supports the wafer's process requirements.

The vEB Tree does not store semiconductor-specific business rules. It remains a reusable integer-set implementation.

### 5.2 Interval Tree

**Purpose:** Store intervals and efficiently identify overlaps.

Required operations:

- `insertInterval(...)` — insert an interval.
- `deleteInterval(...)` — remove an interval.
- `findOverlap(...)` — find an overlapping interval.
- `findAllOverlaps(...)` — retrieve all overlapping intervals.
- `checkConflict(...)` — determine whether an interval conflicts with existing intervals.

**Application:** The reservation manager uses Interval Tree instances to represent processing reservations, maintenance windows, and calibration periods.

Intervals must be checked against the relevant resource. Two reservations on different independent machines must not be treated as conflicting solely because their time intervals overlap.

The interval implementation may support an optional payload or identifier to associate an interval with an application reservation without depending on the reservation class itself.

### 5.3 Pairing Heap

**Purpose:** Maintain pending wafer lots according to priority.

Required operations:

- `insert(item)` — insert an item.
- `findMin()` — return the item with the smallest priority key.
- `deleteMin()` — remove and return the minimum-key item.
- `meld(other_heap)` — combine two heaps.

The application uses a consistent priority mapping. For example:

| Priority | Numeric key |
|---|---:|
| Critical | 0 |
| High | 1 |
| Normal | 2 |

With this convention, `findMin()` returns the highest-priority pending wafer.

The Pairing Heap must remain generic. It should accept suitable items and a priority key or comparison mechanism rather than depending directly on semiconductor-specific entities.

## 6. Application Entities and Aggregation

The application models the domain through the following entities:

| Entity | Responsibilities |
|---|---|
| `WaferLot` | Stores wafer ID, process type, duration, preferred or valid resource class, priority, and status. |
| `Resource` | Represents equipment, its resource class, supported processes, and availability status. |
| `ResourceSlot` | Represents a slot or processing opportunity associated with a resource. |
| `Reservation` | Records the resource, time interval, wafer association, and reservation type. |

### Aggregation relationships

The application must use **has-a relationships (aggregation)** to connect the entities and data structures.

```text
ResourceSlotManager
    ├── VEBTree
    └── ResourceSlot references

WaferScheduler
    ├── PairingHeap
    └── Pending WaferLot references

ReservationManager
    ├── IntervalTree instances
    └── Reservation references
```

These relationships allow the application managers to use the data structures without coupling the underlying algorithms to the application entities.

For example, the vEB Tree stores integer slot IDs, while the `ResourceSlotManager` maintains the mapping from each ID to its `ResourceSlot` entity.

The Interval Tree stores interval information and optional payload references, while the `ReservationManager` manages the corresponding reservation objects.

The Pairing Heap stores generic items, which are `WaferLot` instances when used by the `WaferScheduler`.

**Design rule:** The three data-structure modules must not import `WaferLot`, `Resource`, `ResourceSlot`, or `Reservation`. They must be reusable in unrelated applications.

## 7. Five-Member Module Division

Each member owns one Python file. The public method signatures and shared data representations must be agreed upon before parallel implementation begins.

### Member 1 — `veb_tree.py`

**Responsibility:** Implement the reusable Van Emde Boas Tree.

Core methods:

`insert`, `delete`, `search`, `minimum`, `maximum`, `predecessor`, `successor`

Expected result: a tested integer-set data structure that can be used by the resource-slot manager.

### Member 2 — `interval_tree.py`

**Responsibility:** Implement the reusable Interval Tree.

Core methods:

`insertInterval`, `deleteInterval`, `findOverlap`, `findAllOverlaps`, `checkConflict`

Expected result: a tested interval structure that supports overlap detection without importing application-specific classes.

### Member 3 — `pairing_heap.py`

**Responsibility:** Implement the reusable Pairing Heap.

Core methods:

`insert`, `findMin`, `deleteMin`, `meld`

Expected result: a tested priority queue that supports configurable priority keys and can store different kinds of items.

### Member 4 — `application.py`

**Responsibility:** Define application entities, aggregation managers, and allocation-related operations.

Expected components:

- `WaferLot`, `Resource`, `ResourceSlot`, and `Reservation`
- `ResourceSlotManager`, `WaferScheduler`, and `ReservationManager`
- Wafer registration and priority updates
- Resource and slot management
- Reservation creation and release
- Conflict checking and overlapping-reservation lookup
- Wafer allocation and alternative-resource search
- Equipment-failure support and report generation

Expected result: an application layer that coordinates the data structures without reimplementing their algorithms.

### Member 5 — `main.py`

**Responsibility:** Integrate the application, handle user interaction, coordinate events, and test the complete workflow.

Expected components:

- `main()` and system initialization
- Menu and input handling
- Wafer and resource registration
- Allocation execution
- Maintenance and equipment-failure event handling
- End-to-end `maintenanceImpactAnalysis()` orchestration
- Process completion
- Report display
- Integrated scenario testing and demonstration

Expected result: a runnable program demonstrating that all three data structures work together through the application layer.

## 8. System Workflow

The normal allocation workflow is:

1. Initialize the application, resources, available slots, reservation managers, and wafer scheduler.
2. Register a wafer with its ID, process type, duration, resource requirements, and priority.
3. Insert the wafer into the Pairing Heap.
4. Retrieve the next wafer according to priority.
5. Search for a candidate integer slot or resource identifier using the vEB Tree.
6. Validate that the corresponding resource supports the wafer's process.
7. Check the requested time window using the relevant Interval Tree.
8. If a conflict exists, search for another suitable candidate.
9. If a valid candidate is found, create the reservation, update availability, and mark the wafer as allocated.
10. If no valid candidate exists, retain the wafer as pending.
11. When processing completes, release the reservation and restore the slot to availability when it is genuinely available.

```text
Wafer Registration
        |
        v
Pairing Heap
Select next wafer
        |
        v
vEB Tree
Find candidate slot
        |
        v
Validate resource compatibility
        |
        v
Interval Tree
Check time-window conflict
        |
        +---- Conflict ----> Search alternative
        |                         |
        |                         v
        |                  Check alternative
        |
        +---- No conflict
                    |
                    v
              Create reservation
                    |
                    v
          Update slot availability
                    |
                    v
               Allocation
```

## 9. Maintenance Impact Analysis

Maintenance Impact Analysis is the project's main integrated feature. It demonstrates how the three data structures cooperate when a resource becomes unavailable or requires maintenance.

### Required workflow

1. **Identify affected reservations:** Use the relevant Interval Tree to locate reservations overlapping the maintenance or failure window.
2. **Re-evaluate affected wafers:** Use the Pairing Heap to prioritize affected wafers for reallocation. The implementation must avoid incorrectly treating already-allocated wafers as ordinary pending items.
3. **Find alternatives:** Use the vEB Tree to obtain available slot candidates.
4. **Validate alternatives:** Check process compatibility and use the Interval Tree to ensure that the alternative time window is conflict-free.
5. **Reallocate:** Create a new reservation and update availability for each successful reallocation.
6. **Handle unresolved wafers:** Retain wafers that cannot be reassigned in a pending state.
7. **Generate a report:** Record affected reservations, successful reallocations, and unresolved cases.

```text
Maintenance / Equipment Failure
                |
                v
Interval Tree
Find affected reservations
                |
                v
Pairing Heap
Prioritize affected wafers
                |
                v
vEB Tree
Search available alternatives
                |
                v
Interval Tree
Check alternative conflicts
                |
                v
Reallocate or retain as pending
                |
                v
Generate reallocation report
```

This feature must be implemented as a connected workflow, not merely as separate demonstrations of the three data structures.

## 10. Required Test Scenarios

The integrated application must demonstrate the following cases:

| Scenario | Expected behavior |
|---|---|
| Normal allocation | A compatible, conflict-free candidate is allocated. |
| Reservation conflict | The conflicting candidate is rejected. |
| Alternative candidate | Another compatible, conflict-free candidate is selected. |
| No available candidate | The wafer remains pending. |
| Planned maintenance | Affected reservations are identified and considered for reallocation. |
| Unexpected equipment failure | The affected resource is treated as unavailable and impact analysis is triggered. |
| Successful reallocation | The alternative reservation is created and availability is updated. |
| Failed reallocation | The wafer remains pending and is included in the report. |
| Process completion | The reservation is released and the slot is restored when available. |
| Priority change | The scheduler reflects the updated priority correctly. |

Individual data structures should also be tested independently before integration.

## 11. Shared Interface Rules

Before coding, all five members must agree on:

- Class names, filenames, method signatures, and imports.
- Wafer, resource, slot, and reservation fields.
- Priority ordering and how priority updates are handled.
- Interval boundary conventions and time units.
- How resource-specific Interval Trees are created and accessed.
- What each operation returns when an item is missing or a conflict is found.
- How exceptions and invalid inputs are handled.
- How reservation state and slot availability remain consistent.

The application must be the integration layer. `main.py` should call the application interface rather than manipulating the internal nodes of the three data structures.

## 12. Project Completion Criteria

The project is complete when:

- All three data structures are implemented and independently tested.
- All data structures are reusable without importing application entities.
- The aggregation relationships are explicit in the application architecture.
- Wafer allocation uses priority selection, candidate lookup, and conflict checking.
- Alternative-resource selection works correctly.
- Maintenance Impact Analysis connects all three structures.
- Successful and unsuccessful reallocations are handled correctly.
- Reservation and availability states remain consistent.
- The integrated program runs and demonstrates the required scenarios.
- All five modules have consistent interfaces and work together.

## 13. Conclusion

The Semiconductor Wafer Process Allocation & Equipment Conflict Analyzer demonstrates how a Van Emde Boas Tree, an Interval Tree, and a Pairing Heap can be integrated into a practical scheduling simulation.

The vEB Tree supports available-slot searches, the Interval Tree supports conflict detection, and the Pairing Heap prioritizes pending wafer lots. Application entities and aggregation managers connect these structures to the fabrication workflow, while Maintenance Impact Analysis demonstrates their combined use during equipment downtime.

The design emphasizes modularity, reusable data structures, clear separation of responsibilities, and reliable integration.

---

**Repository files**

```text
Semiconductor-Wafer-Analyzer/
├── README.md
├── veb_tree.py
├── interval_tree.py
├── pairing_heap.py
├── application.py
└── main.py
```

*Implementation note: This README specifies the intended architecture and required behavior. Method signatures, interval semantics, and integration contracts should be finalized by the team before implementation.*
