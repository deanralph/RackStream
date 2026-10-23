"""Deterministic fit calculations for printable mini-rack cradles."""

import math


def _number(values, name, default, minimum, maximum):
    """Reject booleans, nonfinite numbers and unbounded rendering workloads."""
    raw = values.get(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name}: enter a number in millimetres.") from error
    if isinstance(raw, bool) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: must be between {minimum} and {maximum} mm.")
    return value


def calculate_layout(values):
    """Centre the body, reserving real space for feet, tray and panel borders."""
    if not isinstance(values, dict):
        raise ValueError("Send a JSON object containing device dimensions.")
    width = _number(values, "width", 130, 10, 220)
    depth = _number(values, "depth", 60, 10, 250)
    height = _number(values, "height", 25, 3, 140)
    feet = _number(values, "feet", 3, 0, 30)
    radius = _number(values, "radius", 0, 0, 70)
    clearance = _number(values, "clearance", 0.4, 0.1, 2)
    wall = _number(values, "wall", 3, 2, 6)
    includes_feet = values.get("height_includes_feet", False)
    if not isinstance(includes_feet, bool):
        raise ValueError("height_includes_feet must be true or false.")
    if includes_feet:
        height -= feet
    if height < 3:
        raise ValueError("Body height must be at least 3 mm after subtracting feet.")
    if radius > min(width, height) / 2:
        raise ValueError("Corner radius cannot exceed half the smaller body dimension.")
    requested_units = values.get("units", "auto")
    if requested_units not in ("auto", "1", "2", "3", 1, 2, 3) or isinstance(requested_units, bool):
        raise ValueError("Choose auto, 1U, 2U or 3U.")
    opening_width = width + 2 * clearance
    tray_width = opening_width + 2 * wall
    tray_depth = wall + depth + clearance
    # Keep a 1 mm gap at each inner rail. Nominal panel width is not usable width.
    if tray_width > 220.25:
        raise ValueError("Device plus clearance and walls exceeds the 220.25 mm rack body limit.")
    if tray_depth > 254:
        raise ValueError("Tray exceeds the 254 mm working depth reserved on the P1S bed.")
    candidates = (1, 2, 3) if requested_units == "auto" else (int(requested_units),)
    for units in candidates:
        panel_height = units * 44.45 - 0.8
        body_bottom = (panel_height - height) / 2
        tray_top = body_bottom - feet
        # The face opening and tray both need solid material below/above them.
        if tray_top - wall >= 0.8 and body_bottom - clearance >= wall:
            break
    else:
        raise ValueError(
            "Device, feet and tray do not fit the selected U height. "
            "Choose a larger U or smaller device."
        )
    return {
        "units": units,
        "panel_width": 254,
        "panel_height": panel_height,
        "body_width": width,
        "body_height": height,
        "body_depth": depth,
        "body_bottom": body_bottom,
        "tray_top": tray_top,
        "tray_bottom": tray_top - wall,
        "tray_width": tray_width,
        "tray_depth": tray_depth,
        "opening_width": opening_width,
        "opening_height": height + 2 * clearance,
        "opening_radius": radius + clearance,
        "opening_bottom": body_bottom - clearance,
        "wall": wall,
        "feet": feet,
        "clearance": clearance,
        "hole_spacing": 236.525,
        "hole_z": [
            unit * 44.45 + position - 0.4
            for unit in range(units)
            for position in (6.35, 22.225, 38.1)
        ],
        "print_dimensions": [254, tray_depth, panel_height],
        "warnings": [
            "254 mm faceplate: tight nominal fit on the 256 mm P1S bed. "
            "Check slicer exclusions; a brim may not fit.",
            "Open-rear cradle, no positive retention. Check ventilation and cable clearance; "
            "physically fit/load-test before use.",
            "Print orientation and supports must be checked in your slicer. "
            "PETG is a starting suggestion, not a load rating.",
        ],
    }
