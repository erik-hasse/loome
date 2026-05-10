from __future__ import annotations

from ..model import Pin, WireEndpoint, WireSegment


def run_key_for_wire_id(harness, wire_id: str | None) -> str | None:
    if not getattr(harness, "_builder_enabled", False):
        return None
    return _run_key_for_wire_id(harness, wire_id)


def _run_key_for_wire_id(harness, wire_id: str | None) -> str | None:
    if not wire_id:
        return None
    assignment = getattr(harness, "_wire_id_assignment", None)
    if assignment is None:
        return None
    for entry in assignment.entries:
        if entry.id == wire_id:
            return entry.run_key
    return None


def run_key_for_segment(harness, seg: WireSegment, local_pin: WireEndpoint | None = None) -> str | None:
    can_id = _can_pair_id_for(local_pin, harness) if isinstance(local_pin, Pin) else None
    run_key = run_key_for_wire_id(harness, can_id or seg.wire_id)
    if run_key is None:
        return None
    can_side = _can_disconnect_side(local_pin if isinstance(local_pin, Pin) else None)
    if can_side:
        return f"{run_key}-{can_side}"
    side = _disconnect_side(seg, local_pin)
    return f"{run_key}-{side}" if side else run_key


def builder_entries_for_script(harness) -> list[dict[str, str]]:
    assignment = getattr(harness, "_wire_id_assignment", None)
    if assignment is None:
        return []
    entries: list[dict[str, str]] = []
    by_id = {entry.id: entry for entry in assignment.entries}
    split_ids: set[str] = set()

    for wire_id in _can_disconnect_wire_ids(harness):
        entry = by_id.get(wire_id)
        if entry is None:
            continue
        split_ids.add(entry.id)
        for side in ("a", "b"):
            entries.append(_entry_dict(entry, f"{entry.run_key}-{side}"))

    for seg in harness.segments():
        if seg.disconnect_pin is None or seg.disconnect_pin._can_bus is not None or not seg.wire_id:
            continue
        entry = by_id.get(seg.wire_id)
        if entry is None:
            continue
        split_ids.add(entry.id)
        for side in ("a", "b"):
            entries.append(_entry_dict(entry, f"{entry.run_key}-{side}"))

    for entry in assignment.entries:
        if entry.id in split_ids:
            continue
        entries.append(_entry_dict(entry, entry.run_key))
    return list({entry["run_key"]: entry for entry in entries}.values())


def _entry_dict(entry, run_key: str) -> dict[str, str]:
    return {
        "run_key": run_key,
        "id": entry.id,
        "fingerprint": entry.fingerprint,
        "system": entry.system,
        "kind": entry.kind,
    }


def _disconnect_side(seg: WireSegment, local_pin: WireEndpoint | None) -> str | None:
    if seg.disconnect_pin is None or seg.disconnect_pin._can_bus is not None or local_pin is None:
        return None
    if local_pin is seg.end_a:
        return "a"
    if local_pin is seg.end_b:
        return "b"
    return None


def _can_disconnect_side(local_pin: Pin | None) -> str | None:
    if local_pin is None or not local_pin.disconnect_pins:
        return None
    if not any(pin._can_bus is not None for pin in local_pin.disconnect_pins):
        return None
    signal = (local_pin.signal_name or "").lower()
    if "low" in signal:
        return "a"
    if "high" in signal:
        return "b"
    return None


def _can_disconnect_wire_ids(harness) -> set[str]:
    pair_ids = getattr(harness, "_can_pair_ids", None)
    if not pair_ids:
        return set()
    wire_ids: set[str] = set()
    for bus in harness.can_buses:
        for disc in harness.disconnects:
            if not any(pin._can_bus is bus for pin in disc._pins.values()):
                continue
            low_dev = high_dev = None
            for dev in bus.devices:
                for pin in vars(dev).values():
                    if not isinstance(pin, Pin):
                        continue
                    if not any(dpin._disconnect is disc for dpin in pin.disconnect_pins):
                        continue
                    signal = pin.signal_name or ""
                    if signal == "CAN Low":
                        low_dev = dev
                    elif signal == "CAN High":
                        high_dev = dev
            if low_dev is None or high_dev is None:
                continue
            wire_id = pair_ids.get((id(bus), id(low_dev), id(high_dev)))
            if wire_id:
                wire_ids.add(wire_id)
    return wire_ids


def _can_pair_id_for(pin: Pin | None, harness) -> str | None:
    if pin is None or pin.shield_group is None or not pin.shield_group.single_oval:
        return None
    pair_ids = getattr(harness, "_can_pair_ids", None)
    if not pair_ids:
        return None
    for bus in harness.can_buses:
        if not bus.covers_pin(pin):
            continue
        dev = bus.connector_for_pin(pin)
        if dev is None:
            return None
        idx = bus.devices.index(dev)
        is_high = "high" in (pin.signal_name or "").lower()
        if is_high:
            if idx == 0:
                return None
            neighbor = bus.devices[idx - 1]
            return pair_ids.get((id(bus), id(neighbor), id(dev)))
        if idx + 1 >= len(bus.devices):
            return None
        neighbor = bus.devices[idx + 1]
        return pair_ids.get((id(bus), id(dev), id(neighbor)))
    return None
