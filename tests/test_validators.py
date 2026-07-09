from loome import (
    RS232,
    Component,
    Connector,
    GroundSymbol,
    Harness,
    Pin,
    present,
    require,
    require_all,
    require_any,
)
from loome.validators import run_checks, unconnected_report


class Radio(Component):
    class J1(Connector):
        power = Pin(1, "Power In", required=True)
        ground = Pin(2, "Ground", required=True)
        remote = Pin(3, "Remote Head", required=lambda ctx: ctx.has_component("Display"))
        cfg_data = Pin(4, "Config Data", required=lambda ctx: ctx.any_connected("cfg_*"))
        cfg_clock = Pin(5, "Config Clock", required=lambda ctx: ctx.any_connected("cfg_*"))
        aux = Pin(6, "Aux")  # never required


class Display(Component):
    class J1(Connector):
        power = Pin(1, "Power In", required=True)


def _codes(issues):
    return [i.code for i in issues]


def test_static_required_pin_flags_when_unconnected():
    radio = Radio("Com Radio")
    gnd = GroundSymbol("GND")
    radio.J1.power >> gnd
    harness = Harness("t")
    harness.autodetect(dict(radio=radio, gnd=gnd, harness=harness))

    issues = run_checks(harness)
    msgs = [i.message for i in issues if i.code == "required-pin"]
    assert any("Ground" in m for m in msgs)
    assert not any("Power In" in m for m in msgs)  # power is wired


def test_required_pin_satisfied_when_connected():
    radio = Radio("Com Radio")
    gnd = GroundSymbol("GND")
    radio.J1.power >> gnd
    radio.J1.ground >> gnd
    harness = Harness("t")
    harness.autodetect(dict(radio=radio, gnd=gnd, harness=harness))

    msgs = [i.message for i in run_checks(harness) if i.code == "required-pin"]
    assert not any("Ground" in m for m in msgs)


def test_conditional_required_triggered_by_other_component():
    radio = Radio("Com Radio")
    display = Display("Display")
    gnd = GroundSymbol("GND")
    radio.J1.power >> gnd
    radio.J1.ground >> gnd
    display.J1.power >> gnd
    harness = Harness("t")
    harness.autodetect(dict(radio=radio, display=display, gnd=gnd, harness=harness))

    msgs = [i.message for i in run_checks(harness) if i.code == "required-pin"]
    assert any("Remote Head" in m for m in msgs)  # required because Display present


def test_conditional_not_required_without_trigger():
    radio = Radio("Com Radio")
    gnd = GroundSymbol("GND")
    radio.J1.power >> gnd
    radio.J1.ground >> gnd
    harness = Harness("t")
    harness.autodetect(dict(radio=radio, gnd=gnd, harness=harness))

    msgs = [i.message for i in run_checks(harness) if i.code == "required-pin"]
    assert not any("Remote Head" in m for m in msgs)  # no Display -> not required


def test_all_or_nothing_group_via_any_connected():
    radio = Radio("Com Radio")
    gnd = GroundSymbol("GND")
    radio.J1.power >> gnd
    radio.J1.ground >> gnd
    radio.J1.cfg_data >> gnd  # wiring one config pin makes the sibling required
    harness = Harness("t")
    harness.autodetect(dict(radio=radio, gnd=gnd, harness=harness))

    msgs = [i.message for i in run_checks(harness) if i.code == "required-pin"]
    assert any("Config Clock" in m for m in msgs)
    assert not any("Config Data" in m for m in msgs)  # it's the one that's wired


def test_duplicate_labels_warn():
    a = Radio("Same")
    b = Radio("Same")
    gnd = GroundSymbol("GND")
    for r in (a, b):
        r.J1.power >> gnd
        r.J1.ground >> gnd
    harness = Harness("t")
    harness.autodetect(dict(a=a, b=b, gnd=gnd, harness=harness))

    assert "duplicate-label" in _codes(run_checks(harness))


class Box(Component):
    class J1(Connector):
        power = Pin(1, "Power", required=True)
        serial = RS232(2, 3, 4, name="Serial")


class Peer(Component):
    class J1(Connector):
        serial = RS232(2, 3, 4, name="Serial")


def test_port_required_flag_flags_unwired_port():
    box = Box("Box")
    gnd = GroundSymbol("GND")
    box.J1.power >> gnd
    require(box.J1.serial)  # required, but not connected
    harness = Harness("t")
    harness.autodetect(dict(box=box, gnd=gnd, harness=harness))

    msgs = [i.message for i in run_checks(harness) if i.code == "required-pin"]
    assert sum("Serial" in m for m in msgs) == 1  # one issue per port, not per conductor


def test_port_required_satisfied_when_connected():
    box = Box("Box")
    peer = Peer("Peer")
    gnd = GroundSymbol("GND")
    box.J1.power >> gnd
    box.J1.serial >> peer.J1.serial
    require(box.J1.serial, when=lambda ctx: ctx.has_component("Peer"))
    harness = Harness("t")
    harness.autodetect(dict(box=box, peer=peer, gnd=gnd, harness=harness))

    msgs = [i.message for i in run_checks(harness) if i.code == "required-pin"]
    assert not any("Serial" in m for m in msgs)


class TwoLink(Component):
    class J1(Connector):
        a = Pin(1, "Link A")
        b = Pin(2, "Link B")


def _oat_free_harness(*, wire_a=False, wire_b=False):
    dev = TwoLink("Dev")
    gnd = GroundSymbol("g")
    if wire_a:
        dev.J1.a >> gnd
    if wire_b:
        dev.J1.b >> gnd
    harness = Harness("t")
    harness.autodetect(dict(dev=dev, gnd=gnd, harness=harness))
    return dev, harness


def _req_msgs(harness):
    return [i.message for i in run_checks(harness) if i.code == "required-pin"]


def test_require_all_flags_each_unwired_target():
    dev, harness = _oat_free_harness(wire_a=True)  # a wired, b not
    require_all(dev.J1.a, dev.J1.b)
    msgs = _req_msgs(harness)
    assert any("Link B" in m for m in msgs)
    assert not any("Link A" in m for m in msgs)


def test_require_any_satisfied_when_one_wired():
    dev, harness = _oat_free_harness(wire_a=True)  # a wired -> group satisfied
    require_any(dev.J1.a, dev.J1.b)
    assert not _req_msgs(harness)


def test_require_any_flags_when_none_wired():
    dev, harness = _oat_free_harness()  # neither wired
    require_any(dev.J1.a, dev.J1.b)
    msgs = _req_msgs(harness)
    assert any("Link A" in m for m in msgs)
    assert any("Link B" in m for m in msgs)


def test_present_predicate_gates_requirement():
    dev, harness = _oat_free_harness()  # only TwoLink present
    require(dev.J1.a, when=present("Nonexistent"))
    assert not _req_msgs(harness)  # gate false -> not required
    require(dev.J1.a, when=present("Dev"))
    assert any("Link A" in m for m in _req_msgs(harness))  # gate true -> required


def test_unconnected_report_lists_floating_pins():
    radio = Radio("Com Radio")
    gnd = GroundSymbol("GND")
    radio.J1.power >> gnd
    harness = Harness("t")
    harness.autodetect(dict(radio=radio, gnd=gnd, harness=harness))

    report = unconnected_report(harness)
    assert "Com Radio" in report
    signals = {sig for _num, sig in report["Com Radio"]}
    assert "Ground" in signals
    assert "Aux" in signals
    assert "Power In" not in signals  # wired
