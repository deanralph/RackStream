"""Boundary and measurement semantics for the complete fit envelope."""

import pytest

from rackstream import calculate_layout

BASE = {"width": 130, "depth": 60, "height": 25, "feet": 3}


@pytest.mark.parametrize("height,units", [(25, 1), (50, 2), (100, 3)])
def test_auto_selects_smallest_feet_aware_unit(height, units):
    assert calculate_layout({**BASE, "height": height})["units"] == units


def test_inclusive_measurement_matches_body_only_measurement():
    first = calculate_layout(BASE)
    second = calculate_layout({**BASE, "height": 28, "height_includes_feet": True})
    assert first == second


@pytest.mark.parametrize(
    "change",
    [
        {"width": 220},
        {"depth": 260},
        {"height": 140},
        {"height": 50, "units": "1"},
        {"feet": -1},
        {"width": "nan"},
        {"height": float("inf")},
        {"radius": 20},
        {"width": True},
        {"wall": 0},
        {"units": "1.5"},
        {"height_includes_feet": "false"},
        {"height_includes_feet": True, "height": 3},
        {"depth": None},
        {"clearance": -1},
    ],
)
def test_rejects_impossible_or_malformed_input(change):
    with pytest.raises(ValueError):
        calculate_layout({**BASE, **change})


def test_returns_preview_geometry_and_printer_warning():
    layout = calculate_layout({**BASE, "radius": 3})
    assert layout["opening_radius"] == pytest.approx(3.4)
    assert layout["tray_width"] < 222.25
    assert layout["hole_spacing"] == 236.525
    assert len(layout["hole_z"]) == 3
    assert layout["warnings"]
    assert layout["print_dimensions"][0] == 254
