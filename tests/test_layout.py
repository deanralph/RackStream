"""Fit rules are tested separately from the renderer."""

import pytest

from rackstream import calculate_layout


def test_centres_body_and_places_tray_below_feet():
    layout = calculate_layout({"width": 130, "depth": 60, "height": 25, "feet": 3})
    assert layout["units"] == 1
    assert layout["panel_height"] == pytest.approx(43.65)
    assert layout["body_bottom"] + 12.5 == pytest.approx(43.65 / 2)
    assert layout["tray_top"] == pytest.approx(layout["body_bottom"] - 3)
    assert layout["tray_bottom"] == pytest.approx(layout["tray_top"] - 3)
