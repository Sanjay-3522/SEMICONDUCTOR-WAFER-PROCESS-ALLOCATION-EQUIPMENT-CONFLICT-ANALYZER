"""
Member 5: Maintenance Impact Analysis & Simulation Runner
File: maintenanceAnalysis.py

Purpose
-------
Coordinates the existing reusable Interval Tree, Pairing Heap, and vEB Tree
through the application's public interface. It does NOT reimplement any of
the three data structures.

Integration contract expected from the application object
---------------------------------------------------------
app.reservation_manager.find_overlapping_reservations(resource_id, start, end)
    -> iterable of Reservation objects

app.wafer_scheduler.rebuild_priority_queue(wafers)
    -> rebuilds/updates the existing Pairing Heap with the supplied wafers
       using the agreed priority convention

app.resource_slot_manager.find_next_available_slot(after_slot_id, resource_class=None)
    -> ResourceSlot or None; internally uses the existing vEB Tree

app.reservation_manager.check_conflict(resource_id, start, end)
    -> bool

app.find_alternative_resource(wafer, excluded_resource_ids, start, end)
    -> (resource, slot) or None; uses vEB + Interval Tree through the app

app.release_reservation(reservation)
app.reserve_equipment(wafer, resource, slot, start, end)
    -> Reservation or None / False on failure

app.mark_pending(wafer, reason)
app.generate_conflict_report(records)
app.generate_reallocation_report(records)

Entity attribute contract
------------------------
Reservation: wafer_id, resource_id, start, end
Wafer: wafer_id, priority (other fields may be present)
Resource/slot: resource_id and slot_id (or equivalent attributes)

If your Member 4 implementation uses different method or field names, adapt
this file's small helper methods rather than changing the data structures.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Iterable, Optional


@dataclass
class ImpactRecord:
    wafer_id: str
    old_resource_id: str
    old_start: Any
    old_end: Any
    outcome: str
    new_resource_id: Optional[str] = None
    new_slot_id: Optional[str] = None
    reason: str = ""


class MaintenanceImpactAnalyzer:
    """Coordinates maintenance/failure recovery using the application's ADTs."""

    def __init__(self, app: Any):
        self.app = app
        self.conflict_records: list[dict] = []
        self.reallocation_records: list[dict] = []

    @staticmethod
    def _get(obj: Any, *names: str, default=None):
        """Read the first available attribute/key from an entity."""
        for name in names:
            if isinstance(obj, dict) and name in obj:
                return obj[name]
            if hasattr(obj, name):
                return getattr(obj, name)
        return default

    @staticmethod
    def _identifier(value: Any) -> str:
        return str(value) if value is not None else "UNKNOWN"

    def _affected_reservations(self, resource_id: str, start: Any, end: Any):
        # The reservation manager must query the resource's Interval Tree.
        return list(
            self.app.reservation_manager.find_overlapping_reservations(
                resource_id, start, end
            )
        )

    def _get_wafer(self, wafer_id: str):
        # The application should expose a wafer registry or lookup method.
        if hasattr(self.app, "get_wafer"):
            return self.app.get_wafer(wafer_id)
        wafers = getattr(self.app, "wafers_by_id", {})
        return wafers.get(wafer_id)

    def _prioritize_affected_wafers(self, wafers: list[Any]):
        """Use the application's Pairing Heap scheduler to order affected work."""
        if hasattr(self.app.wafer_scheduler, "rebuild_priority_queue"):
            self.app.wafer_scheduler.rebuild_priority_queue(wafers)
            ordered = []
            # This interface should return wafers in priority order by repeatedly
            # reading/removing the heap minimum. It must not lose pending items.
            if hasattr(self.app.wafer_scheduler, "pop_next"):
                while self.app.wafer_scheduler.has_pending():
                    item = self.app.wafer_scheduler.pop_next()
                    if item is None:
                        break
                    ordered.append(item)
                return ordered
            return sorted(
                wafers,
                key=lambda w: self._get(w, "priority", default=999)
            )

        # Adapter fallback: the heap itself should be connected by Member 4.
        # Sorting is only a safe fallback for demo/integration compatibility;
        # production ordering should come from the Pairing Heap.
        return sorted(wafers, key=lambda w: self._get(w, "priority", default=999))

    def _find_alternative(self, wafer: Any, excluded_resource_ids: set[str],
                          start: Any, end: Any):
        # This application method should search candidate slots using vEB,
        # then validate each candidate against its resource's Interval Tree.
        return self.app.find_alternative_resource(
            wafer, excluded_resource_ids, start, end
        )

    def analyze(self, resource_id: str, start: Any, end: Any,
                event_type: str = "MAINTENANCE") -> dict:
        """
        Analyze a maintenance/failure window and attempt to reallocate affected
        wafers. Returns a summary with conflict and reallocation records.
        """
        if start >= end:
            raise ValueError("Event start must be earlier than event end.")

        affected = self._affected_reservations(resource_id, start, end)
        self.conflict_records = []
        self.reallocation_records = []

        if not affected:
            summary = {
                "event_type": event_type,
                "resource_id": resource_id,
                "start": start,
                "end": end,
                "affected_count": 0,
                "reallocated_count": 0,
                "pending_count": 0,
                "message": "No reservations overlap this event window.",
                "conflicts": [],
                "reallocations": [],
            }
            self._emit_reports()
            return summary

        # Resolve reservation -> wafer references, preserving one entry per wafer.
        reservations_by_wafer = {}
        wafers = []
        for reservation in affected:
            wafer_id = self._identifier(
                self._get(reservation, "wafer_id", "waferId")
            )
            reservations_by_wafer.setdefault(wafer_id, []).append(reservation)
            wafer = self._get(reservation, "wafer", default=None) or self._get_wafer(wafer_id)
            if wafer is not None and wafer_id not in {
                self._identifier(self._get(w, "wafer_id", "waferId")) for w in wafers
            }:
                wafers.append(wafer)

        ordered_wafers = self._prioritize_affected_wafers(wafers)
        processed_ids = set()
        reallocated_count = 0
        pending_count = 0

        # Handle any reservation whose wafer lookup was unavailable as unresolved.
        for wafer_id, reservations in reservations_by_wafer.items():
            if not any(
                self._identifier(self._get(w, "wafer_id", "waferId")) == wafer_id
                for w in ordered_wafers
            ):
                for reservation in reservations:
                    self._record_pending(
                        reservation, wafer_id,
                        "Wafer entity could not be found in the application registry."
                    )
                    pending_count += 1

        for wafer in ordered_wafers:
            wafer_id = self._identifier(self._get(wafer, "wafer_id", "waferId"))
            if wafer_id in processed_ids:
                continue
            processed_ids.add(wafer_id)

            reservations = reservations_by_wafer.get(wafer_id, [])
            if not reservations:
                continue

            # A wafer may have multiple affected reservations; process each
            # affected reservation without double-counting the wafer.
            successful_for_wafer = True
            for old_reservation in reservations:
                old_resource = self._identifier(
                    self._get(old_reservation, "resource_id", "resourceId")
                )
                old_start = self._get(old_reservation, "start", "start_time")
                old_end = self._get(old_reservation, "end", "end_time")

                self.conflict_records.append({
                    "event_type": event_type,
                    "wafer_id": wafer_id,
                    "resource_id": old_resource,
                    "start": old_start,
                    "end": old_end,
                    "status": "AFFECTED",
                })

                # Do not release the original reservation until an alternative
                # is found, so a failed search does not silently lose the work.
                alternative = self._find_alternative(
                    wafer, {resource_id, old_resource}, old_start, old_end
                )

                if not alternative:
                    successful_for_wafer = False
                    self._record_pending(
                        old_reservation, wafer_id,
                        "No compatible conflict-free alternative was found."
                    )
                    continue

                new_resource, new_slot = alternative
                new_resource_id = self._identifier(
                    self._get(new_resource, "resource_id", "resourceId", "id")
                )
                new_slot_id = self._identifier(
                    self._get(new_slot, "slot_id", "slotId", "id")
                )

                # Final conflict check is required before changing reservations.
                conflict = self.app.reservation_manager.check_conflict(
                    new_resource_id, old_start, old_end
                )
                if conflict:
                    successful_for_wafer = False
                    self._record_pending(
                        old_reservation, wafer_id,
                        "Alternative candidate failed the final Interval Tree check."
                    )
                    continue

                # Reserve the alternative first. Only release old reservation
                # after the new reservation is successfully created.
                new_reservation = self.app.reserve_equipment(
                    wafer, new_resource, new_slot, old_start, old_end
                )
                if not new_reservation:
                    successful_for_wafer = False
                    self._record_pending(
                        old_reservation, wafer_id,
                        "The application could not create the alternative reservation."
                    )
                    continue

                self.app.release_reservation(old_reservation)
                self.reallocation_records.append(asdict(ImpactRecord(
                    wafer_id=wafer_id,
                    old_resource_id=old_resource,
                    old_start=old_start,
                    old_end=old_end,
                    outcome="REALLOCATED",
                    new_resource_id=new_resource_id,
                    new_slot_id=new_slot_id,
                    reason=f"{event_type} impact; alternative passed conflict check.",
                )))

            if successful_for_wafer:
                reallocated_count += 1
            else:
                pending_count += 1

        self._emit_reports()
        return {
            "event_type": event_type,
            "resource_id": resource_id,
            "start": start,
            "end": end,
            "affected_count": len(reservations_by_wafer),
            "reallocated_count": reallocated_count,
            "pending_count": pending_count,
            "conflicts": self.conflict_records,
            "reallocations": self.reallocation_records,
        }

    def _record_pending(self, reservation: Any, wafer_id: str, reason: str):
        resource_id = self._identifier(
            self._get(reservation, "resource_id", "resourceId")
        )
        start = self._get(reservation, "start", "start_time")
        end = self._get(reservation, "end", "end_time")

        record = asdict(ImpactRecord(
            wafer_id=wafer_id,
            old_resource_id=resource_id,
            old_start=start,
            old_end=end,
            outcome="PENDING",
            reason=reason,
        ))
        self.reallocation_records.append(record)

        if hasattr(self.app, "mark_pending"):
            self.app.mark_pending(wafer_id, reason)

    def _emit_reports(self):
        if hasattr(self.app, "generate_conflict_report"):
            self.app.generate_conflict_report(self.conflict_records)
        if hasattr(self.app, "generate_reallocation_report"):
            self.app.generate_reallocation_report(self.reallocation_records)


def run_simulation(app: Any, scenarios: Iterable[dict]) -> list[dict]:
    """
    Run a set of command-line scenarios through the integrated application.

    Each scenario must contain:
      resource_id, start, end
    Optional:
      event_type ("MAINTENANCE" or "FAILURE")

    The caller supplies the real application instance, which must be connected
    to the three reusable data structures.
    """
    analyzer = MaintenanceImpactAnalyzer(app)
    results = []

    for index, scenario in enumerate(scenarios, start=1):
        print(f"\\n=== Scenario {index}: {scenario.get('event_type', 'MAINTENANCE')} ===")
        result = analyzer.analyze(
            resource_id=scenario["resource_id"],
            start=scenario["start"],
            end=scenario["end"],
            event_type=scenario.get("event_type", "MAINTENANCE"),
        )
        results.append(result)
        print(f"Affected wafers: {result['affected_count']}")
        print(f"Reallocated:     {result['reallocated_count']}")
        print(f"Still pending:   {result['pending_count']}")
        print(f"Conflicts logged:{len(result['conflicts'])}")
        print(f"Reallocations:   {len(result['reallocations'])}")

    return results


if __name__ == "__main__":
    print("Maintenance Impact Analysis & Simulation Runner")
    print("This module is designed to run with the integrated application.")
    print("Import run_simulation(app, scenarios) from main.py after Member 4")
    print("implements the integration contract documented at the top of this file.")
