"""Interactive runner for automatic wafer allocation.

The operator enters each equipment resource ID and chooses a resource class from
an on-screen catalog. Slot IDs are generated automatically by AllocationEngine.
Wafer lots specify an operation; the engine selects compatible equipment and
allocates a conflict-free time window.

Run: python main.py
"""
from __future__ import annotations

from allocation_engine import AllocationEngine, RESOURCE_CLASS_OPERATIONS
from maintenanceAnalysis import run_simulation
from pairing_heap import Priority


def ask_text(prompt: str, *, default: str | None = None) -> str:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("Please enter a value.")


def ask_int(prompt: str, *, minimum: int | None = None,
            maximum: int | None = None, default: int | None = None) -> int:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Value must be at least {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Value must be no greater than {maximum}.")
            continue
        return value


def ask_menu(prompt: str, options: dict[str, object]):
    """Display numbered options and return the selected option's value."""
    while True:
        answer = input(f"{prompt}: ").strip()
        if answer in options:
            return options[answer]
        print(f"Choose a number from 1 to {len(options)}.")


def show_resource_class_catalog() -> None:
    print("\nAVAILABLE RESOURCE CLASSES")
    print("Each class has its own operation set; classes may share some operations.")
    for index, (resource_class, operations) in enumerate(RESOURCE_CLASS_OPERATIONS.items(), 1):
        print(f"  {index}. {resource_class:<14} -> {', '.join(sorted(operations))}")


def show_operation_catalog() -> dict[str, str]:
    operations = sorted({operation for ops in RESOURCE_CLASS_OPERATIONS.values() for operation in ops})
    options = {str(index): operation for index, operation in enumerate(operations, 1)}
    print("\nAVAILABLE WAFER OPERATIONS")
    for number, operation in options.items():
        compatible = [name for name, supported in RESOURCE_CLASS_OPERATIONS.items()
                      if operation in supported]
        print(f"  {number}. {operation:<14} (compatible classes: {', '.join(compatible)})")
    return options


def print_reservations(records: list[dict], heading: str) -> None:
    print(f"\n{heading}")
    print("-" * 82)
    if not records:
        print("No reservations.")
        return
    print(f"{'WAFER':<14} {'RESOURCE':<18} {'AUTO SLOT':>10} {'START':>8} {'END':>8}")
    print("-" * 82)
    for row in records:
        print(f"{row['wafer_id']:<14} {row['resource_id']:<18} "
              f"{row['slot_id']:>10} {row['start']:>8} {row['end']:>8}")


def collect_project_input() -> tuple[AllocationEngine, int]:
    app = AllocationEngine(veb_universe_size=65536)

    print("\nSETUP: EQUIPMENT RESOURCES")
    print("For each resource, enter its ID and choose a class. Slot IDs are automatic.")
    show_resource_class_catalog()
    class_options = {str(i): name for i, name in enumerate(RESOURCE_CLASS_OPERATIONS, 1)}
    resource_count = ask_int("Number of resources to register", minimum=1, maximum=100)

    for index in range(1, resource_count + 1):
        print(f"\nResource {index}/{resource_count}")
        resource_id = ask_text("  Resource ID (e.g. ETCH-01)")
        print("  Select resource class:")
        resource_class = ask_menu("  Class number", class_options)
        while True:
            try:
                resource = app.add_resource(resource_id, resource_class)
                slot = resource.slots[0]
                print(f"  Registered {resource.resource_id} as {resource.resource_class}.")
                print(f"  Automatically assigned slot ID: {slot.slot_id}")
                print(f"  Supported operations: {', '.join(sorted(resource.operations))}")
                break
            except (ValueError, TypeError) as exc:
                print(f"  Error: {exc}")
                resource_id = ask_text("  Enter a different resource ID")

    print("\nSETUP: WAFER LOTS")
    operation_options = show_operation_catalog()
    wafer_count = ask_int("Number of wafer lots to schedule", minimum=1, maximum=1000)
    priority_options = {
        "1": Priority.CRITICAL,
        "2": Priority.HIGH,
        "3": Priority.NORMAL,
        "4": Priority.LOW,
    }
    for index in range(1, wafer_count + 1):
        print(f"\nWafer lot {index}/{wafer_count}")
        wafer_id = ask_text("  Wafer lot ID")
        print("  Select required operation:")
        process_type = ask_menu("  Operation number", operation_options)
        duration = ask_int("  Processing duration (positive integer)", minimum=1)
        priority = ask_menu("  Priority (1=Critical, 2=High, 3=Normal, 4=Low)", priority_options)
        arrival = ask_int("  Arrival order/time", minimum=0, default=index)
        while True:
            try:
                # AUTO means the wafer may use any resource supporting its operation.
                app.add_wafer_lot(wafer_id, process_type, "AUTO", duration, priority, arrival)
                print(f"  Added {wafer_id}: {process_type}, duration={duration}, priority={priority.name}.")
                break
            except (ValueError, TypeError) as exc:
                print(f"  Error: {exc}")
                wafer_id = ask_text("  Enter a unique wafer lot ID")

    requested_start = ask_int("Earliest requested start time for all lots", minimum=0, default=0)
    return app, requested_start


def run_automatic_pipeline(app: AllocationEngine, requested_start: int) -> None:
    print("\n" + "=" * 82)
    print("AUTOMATIC ALLOCATION PIPELINE")
    print("Pairing Heap -> vEB Tree automatic slot index -> Interval Tree conflict checks")
    print("=" * 82)
    reservations = app.allocate_all(requested_start=requested_start)
    print(f"\nAllocation finished: {len(reservations)} wafer lot(s) allocated.")
    print_reservations(app.reservation_report(), "FINAL RESERVATION SCHEDULE")

    if app.pending_reasons:
        print("\nPENDING / UNALLOCATED WAFERS")
        for wafer_id, reason in app.pending_reasons.items():
            print(f"  - {wafer_id}: {reason}")

    all_reservations = app.reservation_manager.all_reservations()
    conflict_count = 0
    for resource_id in app.resources:
        resource_reservations = [r for r in all_reservations if r.resource_id == resource_id]
        for reservation in resource_reservations:
            overlaps = app.reservation_manager.find_overlapping_reservations(
                resource_id, reservation.start, reservation.end)
            if any(item is not reservation for item in overlaps):
                conflict_count += 1
    print("\nFINAL CONFLICT VALIDATION")
    print("  PASS: no overlapping reservations." if conflict_count == 0
          else f"  WARNING: {conflict_count} potential conflict entries detected.")

    print("\nAUTOMATIC SLOT INDEX (vEB TREE)")
    for slot_id in sorted(app.resource_slot_manager.slots_by_id):
        slot = app.resource_slot_manager.slots_by_id[slot_id]
        print(f"  Slot {slot_id:>5} -> resource={slot.resource_id}, class={slot.resource_class}")


def optional_maintenance(app: AllocationEngine) -> None:
    if not app.reservation_manager.all_reservations():
        print("\nMaintenance simulation skipped: there are no allocated reservations.")
        return
    should_run = ask_menu("\nRun a maintenance/failure simulation? (1=Yes, 2=No)", {
        "1": True, "2": False,
    })
    if not should_run:
        print("Maintenance simulation skipped.")
        return

    print("\nChoose a resource to take out of service:")
    resource_options = {}
    for index, (resource_id, resource) in enumerate(app.resources.items(), 1):
        count = sum(r.resource_id == resource_id for r in app.reservation_manager.all_reservations())
        resource_options[str(index)] = resource_id
        print(f"  {index}. {resource_id} (class={resource.resource_class}, reservations={count})")
    resource_id = ask_menu("Resource number", resource_options)
    start = ask_int("Maintenance start time", minimum=0)
    end = ask_int("Maintenance end time (must be after start)", minimum=start + 1)
    event_type = ask_menu("Event type (1=Maintenance, 2=Equipment failure)", {
        "1": "MAINTENANCE", "2": "FAILURE",
    })

    print("\nRunning maintenance impact analysis...")
    result = run_simulation(app, [{
        "resource_id": resource_id, "start": start, "end": end, "event_type": event_type,
    }])[0]
    print("\nMAINTENANCE IMPACT SUMMARY")
    print(f"  Event type          : {result['event_type']}")
    print(f"  Affected wafer lots : {result['affected_count']}")
    print(f"  Reallocated lots    : {result['reallocated_count']}")
    print(f"  Still pending       : {result['pending_count']}")
    print_reservations(app.reservation_report(), "UPDATED RESERVATION SCHEDULE")


def main() -> None:
    print("=" * 82)
    print("SEMICONDUCTOR WAFER ALLOCATION & EQUIPMENT CONFLICT ANALYZER")
    print("Choose equipment classes; slots and equipment assignments are automatic.")
    print("=" * 82)
    try:
        app, requested_start = collect_project_input()
        run_automatic_pipeline(app, requested_start)
        optional_maintenance(app)
        print("\nPROCESS COMPLETE")
    except (KeyboardInterrupt, EOFError):
        print("\nInput cancelled. Exiting safely.")


if __name__ == "__main__":
    main()
