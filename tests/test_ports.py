from __future__ import annotations

import pytest

from loome.model import Component, Connector
from loome.ports import ARINC429, GarminEthernet


class _ARINCDevice(Component):
    class J1(Connector):
        tx = ARINC429(1, 2, "out", name="TX")
        rx = ARINC429(3, 4, "in", name="RX")


class _EthernetDevice(Component):
    class J1(Connector):
        tx = GarminEthernet(1, 2, "out", name="TX")
        rx = GarminEthernet(3, 4, "in", name="RX")


def test_arinc429_direction_mismatch_raises_immediately():
    a = _ARINCDevice()
    b = _ARINCDevice()
    with pytest.raises(ValueError, match="both are 'out'"):
        a.J1.tx >> b.J1.tx


def test_arinc429_direction_mismatch_in_raises_immediately():
    a = _ARINCDevice()
    b = _ARINCDevice()
    with pytest.raises(ValueError, match="both are 'in'"):
        a.J1.rx >> b.J1.rx


def test_arinc429_valid_connection_succeeds():
    a = _ARINCDevice()
    b = _ARINCDevice()
    a.J1.tx >> b.J1.rx  # should not raise


def test_garmin_ethernet_direction_mismatch_raises_immediately():
    a = _EthernetDevice()
    b = _EthernetDevice()
    with pytest.raises(ValueError, match="both are 'out'"):
        a.J1.tx >> b.J1.tx


def test_garmin_ethernet_valid_connection_succeeds():
    a = _EthernetDevice()
    b = _EthernetDevice()
    a.J1.tx >> b.J1.rx  # should not raise
