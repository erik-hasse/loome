"""Single source of truth for connector pin and wire-leg ordering.

Two orderings live here:

1. **Pin row order within a connector** — which row appears on top inside each
   connector block. Driven by ``pin_sort_keys``.
2. **Leg order within a multi-direct pin** — which destination is the primary
   row vs. continuation rows. Driven by ``leg_sort_key``.

Both return tuple sort keys so the rule priority is visible at a glance. To
add or reorder a rule, edit the tuple here — no engine changes required.

──────────────────────────────────────────────────────────────────────────────
Pin row rules (priority order, highest first):

1. Shield grouping is inviolable. Pins of the same shield are always
   contiguous, regardless of where their wires lead. Two shields are kept in
   separate sub-clusters even when they share a remote, so wire-color order
   inside each shield is preserved.
2. Outer (cluster) grouping. Single-target shields collapse into the remote-
   connector group: four 1-wire shields all targeting SDSECU sit in one
   SDSECU cluster, but each shield is its own sub-cluster within. Mixed-
   target shields (RS-232 cross-connect etc.) form their own outer cluster
   so the oval can wrap them.
3. Remote-component adjacency. Falls out of rule 2 — group keys for
   connectors of the same remote component sort adjacently because they share
   the component half of the key.
4. Cluster sort position by lowest pin number. CAN/RS-232 ports have low pin
   numbers but expand last in the MRO walk; this puts them at the top instead
   of the bottom. Within a cluster, sub-clusters (each shield) are likewise
   ordered by their lowest pin number.
5. Within-shield order. Wire color depends on this position (svg.render walks
   ``sg.pins`` to assign palette entries); preserve source-pin order in the
   shield as the intra-shield sort.
6. Self-jumper pairing. Inside a (``"jumper"``,) cluster, sort by
   ``min(self, other)`` then ``self`` so each jumper pair is contiguous.
7. Numerical pin order. Final tiebreaker.

──────────────────────────────────────────────────────────────────────────────
Leg rules for multi-direct pins (priority order):

1. Terminal legs first. A leg ending at a Terminal (ground triangle, off-page
   ref) takes the primary row so its wire runs straight to the right edge;
   Pin legs become continuation rows hanging off the jumper bar below.
2. Same-remote-connector clustering among Pin legs.
3. Remote pin number as tiebreaker.
"""

from __future__ import annotations

from ..model import Pin, SpliceNode, Terminal, WireSegment

_INF = 10**9
_PAIR_NONE = (_INF, _INF)
_INTRA_LAST = (_INF, _PAIR_NONE, _PAIR_NONE, _PAIR_NONE)


def _effective(class_pin: Pin, inst_pin: Pin | None) -> Pin:
    return inst_pin if (inst_pin is not None and inst_pin._connections) else class_pin


def _pin_number_key(pin: Pin) -> tuple:
    n = pin.number
    return (0, n) if isinstance(n, int) else (1, str(n))


def _shield_ids(class_pin: Pin, inst_pin: Pin | None) -> set[int]:
    ids: set[int] = set()
    if class_pin.shield_group is not None:
        ids.add(id(class_pin.shield_group))
    use = _effective(class_pin, inst_pin)
    for seg in use._connections:
        if seg.shield_group is not None:
            ids.add(id(seg.shield_group))
    return ids


def _shield_order(class_pin: Pin, inst_pin: Pin | None) -> int:
    """Position within the pin's shield (drives wire color and row order).

    Returns the canonical wire index (0=W, 1=WB, 2=WO) for this pin so that
    row order always matches wire color on both sides of a cross-connect.
    """
    use = _effective(class_pin, inst_pin)
    # Connection-level shield: position by segment index in sg.segments.
    for seg in use._connections:
        sg = seg.shield_group
        if sg is None:
            continue
        for idx, s in enumerate(sg.segments):
            if s is seg:
                return idx
    # Class-body shield with explicit port_order: use it directly.  This
    # handles RS-232 cross-connects where the receiving pin (end_b) has a
    # different class-body index than the wire it carries.
    for seg in use._connections:
        if seg.shield_group is None and seg.port_order is not None:
            return seg.port_order
    # Class-body shield: own index in sg.pins.
    sg = class_pin.shield_group
    if sg is not None:
        for idx, p in enumerate(sg.pins):
            if p is class_pin:
                return idx
    return _INF


def _is_self_jumper(seg: WireSegment, source_pin: Pin, inst_pin: Pin | None) -> bool:
    """True when this segment connects two pins on the same connector or component."""
    remote = seg.end_b if seg.end_a is source_pin else seg.end_a
    if not isinstance(remote, Pin):
        return False
    if inst_pin is not None:
        if inst_pin._connector is not None and inst_pin._connector is remote._connector:
            return True
        if (
            inst_pin._component is not None
            and inst_pin._component is remote._component
            and inst_pin._connector is None
            and remote._connector is None
        ):
            return True
    return False


def _segment_remote_pin(seg: WireSegment, source_pin: Pin) -> Pin | None:
    remote = seg.end_b if seg.end_a is source_pin else seg.end_a
    return remote if isinstance(remote, Pin) else None


def segment_target_key(seg: WireSegment, source_pin: Pin, inst_pin: Pin | None) -> tuple:
    """Grouping key for one outgoing segment's remote endpoint.

    Used by both the pin-row grouping (rule 3) and by the engine to decide
    which ``PinGroup`` a row belongs to (so the remote box on the right can
    label that connector).
    """
    if _is_self_jumper(seg, source_pin, inst_pin):
        return ("jumper",)
    remote = seg.end_b if seg.end_a is source_pin else seg.end_a
    if isinstance(remote, Pin):
        comp_key = id(remote._component) if remote._component is not None else id(remote._component_class)
        conn_key = id(remote._connector) if remote._connector is not None else id(remote._connector_class)
        return ("component", comp_key, conn_key)
    if isinstance(remote, Terminal):
        return ("terminal", id(remote))
    return ("other", id(remote))


def pin_target_key(class_pin: Pin, inst_pin: Pin | None) -> tuple:
    """Grouping key for a pin row, based on its first connection."""
    use = _effective(class_pin, inst_pin)
    if not use._connections:
        return ("unconnected",)
    return segment_target_key(use._connections[0], use, inst_pin)


def _self_jumper_pair_key(class_pin: Pin, inst_pin: Pin | None) -> tuple:
    """Sort key inside a ('jumper',) group: (min(self,other), self).

    Pairs each jumper with its partner so the two rows are contiguous, which
    keeps the renderer's per-segment jumper bars from overlapping.
    """
    use = _effective(class_pin, inst_pin)
    self_key = _pin_number_key(class_pin)
    if not use._connections:
        return (self_key, self_key)
    seg = use._connections[0]
    remote = seg.end_b if seg.end_a is use else seg.end_a
    if not isinstance(remote, Pin):
        return (self_key, self_key)
    remote_key = _pin_number_key(remote)
    return (min(self_key, remote_key), self_key)


def _shield_local_targets(sg, local_class_pin, get_inst_pin) -> set[tuple]:
    """Remote-target keys for the pins of ``sg`` that live on the local connector.

    "Local" = same connector class as ``local_class_pin`` on the same component
    class. Used to decide whether a shield's group key should be the shared
    remote (single target) or the shield itself (mixed targets).

    Class-body shields (``sg.pins``) hold *class* pins whose ``_connections``
    list is empty — wires live on the instance pin. Resolve each via
    ``get_inst_pin`` so the local-pin connection is visible.
    """
    local_conn_cls = local_class_pin._connector_class
    local_comp_cls = local_class_pin._component_class

    def _is_local(p: Pin) -> bool:
        return p._connector_class is local_conn_cls and p._component_class is local_comp_cls

    targets: set[tuple] = set()
    for p in sg.pins:
        if not _is_local(p):
            continue
        ip = get_inst_pin(p._attr_name) if p._attr_name else None
        use = ip if (ip is not None and ip._connections) else p
        if use._connections:
            targets.add(segment_target_key(use._connections[0], use, None))
    for seg in sg.segments:
        for ep in (seg.end_a, seg.end_b):
            if isinstance(ep, Pin) and _is_local(ep):
                targets.add(segment_target_key(seg, ep, None))
    return targets


def _shield_group_for_pin(class_pin: Pin, inst_pin: Pin | None):
    """Return the ShieldGroup this pin participates in, or None.

    A pin can be in at most one shield in practice; if multiple, prefer the
    connection-level shield (matches ``_shield_order`` semantics).
    """
    use = _effective(class_pin, inst_pin)
    for seg in use._connections:
        if seg.shield_group is not None:
            return seg.shield_group
    return class_pin.shield_group


def _pin_group_key(class_pin: Pin, inst_pin: Pin | None, get_inst_pin) -> tuple:
    """Group key for ``class_pin`` per rules 1–3.

    A shielded pin gets the shield's shared remote target when all of the
    shield's *local* pins target the same remote (rule 2 — single-target shield
    collapses into the remote group). When the shield bridges multiple remotes
    (RS-232 cross-connect etc.), use the shield id (rule 1 — keep it tight so
    one oval can still wrap it).
    """
    sg = _shield_group_for_pin(class_pin, inst_pin)
    if sg is not None:
        targets = _shield_local_targets(sg, class_pin, get_inst_pin)
        if len(targets) == 1:
            return next(iter(targets))
        return ("shield", id(sg))
    return pin_target_key(class_pin, inst_pin)


def pin_sort_keys(
    pin_attrs: list[str],
    get_class_pin,
    get_inst_pin,
) -> list[str]:
    """Return ``pin_attrs`` sorted according to the pin-row rules.

    Two-level grouping: each pin gets an outer cluster key (rule 2) and a
    sub-cluster key (rule 1, the shield id or ``None``). Both levels are
    ordered by lowest pin number (rule 4); pins inside a sub-cluster are
    ordered by rules 5–7.
    """
    raw: list[tuple] = []
    # (outer_key, sub_key, class_pin, inst_pin, attr_name, decl_idx)
    for idx, attr_name in enumerate(pin_attrs):
        cp = get_class_pin(attr_name)
        ip = get_inst_pin(attr_name)
        if cp is None:
            raw.append((("__missing__",), None, None, None, attr_name, idx))
            continue
        outer = _pin_group_key(cp, ip, get_inst_pin)
        sg = _shield_group_for_pin(cp, ip)
        sub = ("shield", id(sg)) if sg is not None else ("noshield",)
        raw.append((outer, sub, cp, ip, attr_name, idx))

    # Rule 4 at outer level: cluster sort position by min pin in the cluster,
    # tiebroken by first appearance.
    outer_min: dict[tuple, tuple] = {}
    outer_first: dict[tuple, int] = {}
    for outer, _sub, cp, _ip, _name, idx in raw:
        pn = _pin_number_key(cp) if cp is not None else (_INF, _INF)
        if outer not in outer_min or pn < outer_min[outer]:
            outer_min[outer] = pn
        outer_first.setdefault(outer, idx)

    # Rule 4 at sub-cluster level: ordered by min pin within (outer, sub).
    sub_min: dict[tuple, tuple] = {}
    sub_first: dict[tuple, int] = {}
    for outer, sub, cp, _ip, _name, idx in raw:
        key = (outer, sub)
        pn = _pin_number_key(cp) if cp is not None else (_INF, _INF)
        if key not in sub_min or pn < sub_min[key]:
            sub_min[key] = pn
        sub_first.setdefault(key, idx)

    keyed: list[tuple] = []
    for outer, sub, cp, ip, attr_name, idx in raw:
        opos = (outer_min[outer], outer_first[outer])
        spos = (sub_min[(outer, sub)], sub_first[(outer, sub)])
        if cp is None:
            keyed.append((opos, spos, _INTRA_LAST, attr_name))
            continue
        pn = _pin_number_key(cp)
        if sub[0] == "shield":
            intra: tuple = (_shield_order(cp, ip), _PAIR_NONE, _PAIR_NONE, pn)
        elif outer == ("jumper",):
            pair_min, pair_self = _self_jumper_pair_key(cp, ip)
            intra = (_INF, pair_min, pair_self, pn)
        else:
            intra = (_INF, _PAIR_NONE, _PAIR_NONE, pn)
        keyed.append((opos, spos, intra, attr_name))

    keyed.sort(key=lambda x: (x[0], x[1], x[2]))
    return [x[3] for x in keyed]


def sort_legs(segments: list[WireSegment], source_pin: Pin) -> list[WireSegment]:
    """Reorder a multi-direct pin's outgoing segments by the leg rules.

    Terminal legs come first (so the terminal wire takes the primary row and
    runs to the right edge); Pin legs cluster by remote connector then sort by
    remote pin number.
    """

    def key(seg: WireSegment) -> tuple:
        remote = seg.end_b if seg.end_a is source_pin else seg.end_a
        # Shielded legs sort before unshielded so the primary row (pin label)
        # stays with the shield-mates and the unshielded continuation goes to
        # its own group below.
        shield_priority = 0 if (seg.shield_group is not None and not seg.shield_group.cable_only) else 1
        if isinstance(remote, Terminal):
            return (shield_priority, 0, 0, id(remote))
        if isinstance(remote, SpliceNode):
            return (shield_priority, 1, id(remote), (2, 0))
        if isinstance(remote, Pin):
            comp_key = id(remote._component) if remote._component is not None else id(remote._component_class)
            conn_key = id(remote._connector) if remote._connector is not None else id(remote._connector_class)
            return (shield_priority, 1, comp_key, conn_key, _pin_number_key(remote))
        return (shield_priority, 2, id(remote))

    return sorted(segments, key=key)
