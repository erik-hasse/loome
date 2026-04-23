from __future__ import annotations

from loome import Harness


def test_default_length_unit_is_inches():
    h = Harness("h")
    assert h.length_unit == "in"


def test_length_unit_is_round_tripped():
    h = Harness("h", length_unit="mm")
    assert h.length_unit == "mm"
