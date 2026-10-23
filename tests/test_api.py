"""Exercise the actual OpenSCAD renderer, not a fabricated STL."""

import io

import pytest
import trimesh

from app import app

BASE = {"width": 130, "depth": 60, "height": 25, "feet": 3, "radius": 3}


def test_preview_returns_layout_without_render():
    response = app.test_client().post("/api/preview", json=BASE)
    assert response.status_code == 200
    assert response.json["units"] == 1


@pytest.mark.parametrize("payload", [{"width": 220}, [], {"height": "nan"}])
def test_invalid_generation_is_not_a_download(payload):
    response = app.test_client().post("/api/generate", json=payload)
    assert response.status_code == 400
    assert "error" in response.json


@pytest.mark.parametrize("height,units", [(25, 1), (50, 2), (100, 3)])
def test_real_stl_download_is_one_watertight_mount(height, units):
    response = app.test_client().post("/api/generate", json={**BASE, "height": height})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert "attachment" in response.headers["Content-Disposition"]
    mesh = trimesh.load(io.BytesIO(response.data), file_type="stl")
    assert mesh.is_watertight
    assert mesh.is_volume
    assert len(mesh.split()) == 1
    assert mesh.extents == pytest.approx([254, 63.4, units * 44.45 - 0.8], abs=0.001)
    assert mesh.volume > 1000
