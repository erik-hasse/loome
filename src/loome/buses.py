"""First-class bus entities (CAN, future: 1-Wire, I2C, etc.).

A `CanBusLine` models the physical ordering of CAN devices along a daisy-chain
and lets the bundle renderer draw one continuous bus track with stubs at each
device. Bus length is derived from bundle trunk distances between adjacent
devices. Per-pin "wire" length (for BoM / schematic annotations) is just the
stub from the connector to the tap point at its breakout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .model import Connector, Pin

if TYPE_CHECKING:
    from .bundles import Attachment
    from .harness import Harness


@dataclass
class CanBusLine:
    name: str
    devices: list[Connector]
    terminations: tuple[Connector, Connector] | None = None
    _pin_ids: set[int] = field(default_factory=set, init=False, repr=False)
    _connector_of_pin: dict[int, Connector] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for dev in self.devices:
            # Register instance pins
            for pv in vars(dev).values():
                if isinstance(pv, Pin) and pv.shield_group is not None and pv.shield_group.single_oval:
                    self._pin_ids.add(id(pv))
                    self._connector_of_pin[id(pv)] = dev
            # Register class-level pins too — Port auto-connections live on the
            # class, so segments emitted from class pins need to map back here.
            # Walk the MRO so subclassed connectors (e.g. GSA28RollServo.J281
            # inheriting from GSA28.J281) pick up pins defined on the parent.
            seen: set[str] = set()
            for c in type(dev).__mro__:
                if not (isinstance(c, type) and issubclass(c, Connector)):
                    continue
                for name, pv in vars(c).items():
                    if name in seen:
                        continue
                    if isinstance(pv, Pin) and pv.shield_group is not None and pv.shield_group.single_oval:
                        seen.add(name)
                        self._pin_ids.add(id(pv))
                        self._connector_of_pin.setdefault(id(pv), dev)

    def covers_pin(self, pin: Pin) -> bool:
        return id(pin) in self._pin_ids

    def connector_for_pin(self, pin: Pin) -> Connector | None:
        return self._connector_of_pin.get(id(pin))

    def segments(self, harness: "Harness") -> list[tuple[Connector, Connector, float]]:
        """Return (device_a, device_b, trunk_distance) for each adjacent pair."""
        result: list[tuple[Connector, Connector, float]] = []
        for a, b in zip(self.devices, self.devices[1:]):
            att_a = _attachment_for(harness, a)
            att_b = _attachment_for(harness, b)
            if att_a is None or att_b is None:
                continue
            if att_a.breakout.bundle is not att_b.breakout.bundle:
                continue
            d = att_a.breakout.bundle.distance(att_a.breakout, att_b.breakout)
            result.append((a, b, d))
        return result

    def resolved_length(self, harness: "Harness") -> float | None:
        segs = self.segments(harness)
        if not segs or len(segs) != len(self.devices) - 1:
            return None
        return sum(d for _, _, d in segs)

    def segment_length_for(self, pin: Pin, harness: "Harness") -> float | None:
        """Length of the stub from a CAN pin's connector out to the bus tap."""
        dev = self.connector_for_pin(pin)
        if dev is None:
            return None
        att = _attachment_for(harness, dev)
        return att.leg_length if att is not None else None

    def stub_lengths_for(self, pin: Pin, harness: "Harness") -> list[tuple[float, Connector]]:
        """Physical wire lengths out of this pin to each adjacent bus device.

        Returns ``(length, neighbor)`` pairs: an intermediate device yields two
        (prev and next); an end device yields one. Each length is
        ``leg_self + trunk_distance(self, neighbor) + leg_neighbor``.
        """
        dev = self.connector_for_pin(pin)
        if dev is None:
            return []
        try:
            dev_idx = self.devices.index(dev)
        except ValueError:
            return []
        att = _attachment_for(harness, dev)
        if att is None:
            return []
        results: list[tuple[float, Connector]] = []
        for neighbor_idx in (dev_idx - 1, dev_idx + 1):
            if not (0 <= neighbor_idx < len(self.devices)):
                continue
            neighbor = self.devices[neighbor_idx]
            neighbor_att = _attachment_for(harness, neighbor)
            if neighbor_att is None:
                continue
            if neighbor_att.breakout.bundle is not att.breakout.bundle:
                continue
            d = att.breakout.bundle.distance(att.breakout, neighbor_att.breakout)
            results.append((att.leg_length + d + neighbor_att.leg_length, neighbor))
        return results


def _attachment_for(harness: "Harness", target: object) -> "Attachment | None":
    for bundle in harness.bundles:
        att = bundle.attachment_for(target)
        if att is not None:
            return att
    return None
