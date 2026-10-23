"""Regression tests from independent geometry review."""

import io
import math

import numpy as np
import pytest
import trimesh

from app import app


@pytest.mark.parametrize("endpoint", ["/api/preview", "/api/generate"])
def test_huge_json_integer_is_a_validation_error(endpoint):
    response = app.test_client().post(endpoint, json={"width": 10**400})
    assert response.status_code == 400
    assert "error" in response.json


def _ray_hits(mesh, origin):
    """Count intersections along +Y using Moller-Trumbore, without optional spatial indexes."""
    triangles = mesh.triangles
    direction = np.array([0.0, 1.0, 0.0])
    first_edge = triangles[:, 1] - triangles[:, 0]
    second_edge = triangles[:, 2] - triangles[:, 0]
    cross = np.cross(direction, second_edge)
    determinant = np.einsum("ij,ij->i", first_edge, cross)
    viable = np.abs(determinant) > 1e-9
    inverse = np.zeros(len(triangles))
    inverse[viable] = 1 / determinant[viable]
    offset = origin - triangles[:, 0]
    u = inverse * np.einsum("ij,ij->i", offset, cross)
    q = np.cross(offset, first_edge)
    v = inverse * q[:, 1]
    distance = inverse * np.einsum("ij,ij->i", second_edge, q)
    return np.count_nonzero(viable & (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > 0))


def test_large_radius_keeps_clearance_between_polygon_vertices():
    values = {
        "width": 130,
        "depth": 60,
        "height": 120,
        "feet": 0,
        "radius": 60,
        "wall": 2,
        "clearance": 0.1,
    }
    client = app.test_client()
    layout = client.post("/api/preview", json=values).json
    response = client.post("/api/generate", json=values)
    assert response.status_code == 200
    mesh = trimesh.load(io.BytesIO(response.data), file_type="stl")
    # Halfway between the original 48-gon's vertices. This lies in the
    # promised clearance band, outside the device but inside its aperture.
    angle = math.radians(3.75)
    radius = 60.08
    origin = np.array(
        [5 + radius * math.cos(angle), -1, layout["body_bottom"] + 60 + radius * math.sin(angle)]
    )
    assert _ray_hits(mesh, origin) == 0
