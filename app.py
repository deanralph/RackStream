"""RackStream web form and bounded, headless OpenSCAD export."""

import io
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from werkzeug.exceptions import HTTPException

from rackstream import calculate_layout

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8192
RENDER_SLOTS = threading.BoundedSemaphore(2)
SCAD_ENV = Environment(loader=FileSystemLoader(ROOT / "scad"), undefined=StrictUndefined)


def render_stl(layout):
    """Render trusted numeric parameters only; never run submitted SCAD or a shell."""
    executable = os.environ.get("OPENSCAD_BIN") or shutil.which("openscad")
    local_bundle = Path.home() / ".local/opt/openscad/squashfs-root/AppRun"
    if not executable and local_bundle.is_file():
        executable = str(local_bundle)
    if not executable:
        raise RuntimeError("OpenSCAD is not installed. Set OPENSCAD_BIN on the server.")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    local_dependencies = Path.home() / ".local/opt/openscad/deps/usr/lib64"
    if executable == str(local_bundle) and local_dependencies.is_dir():
        environment["LD_LIBRARY_PATH"] = (
            str(local_dependencies) + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
        )
    # TemporaryDirectory honours TMPDIR; no jobs or files accumulate after export.
    with tempfile.TemporaryDirectory(prefix="rackstream-") as directory:
        source = Path(directory) / "mount.scad"
        output = Path(directory) / "mount.stl"
        source.write_text(SCAD_ENV.get_template("mount.scad.j2").render(**layout), encoding="utf-8")
        result = subprocess.run(
            [executable, "--hardwarnings", "-o", str(output), str(source)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
            env=environment,
        )
        if result.returncode or not output.is_file() or output.stat().st_size < 84:
            LOGGER.error("OpenSCAD export failed: %s", result.stderr[-4000:])
            raise RuntimeError("OpenSCAD could not generate this mount. Check server logs.")
        return output.read_bytes()


@app.get("/")
def index():
    """Serve the same-origin, dependency-free form."""
    return render_template("index.html")


@app.get("/health")
def health():
    """Small readiness marker without disclosing local paths."""
    return jsonify(status="ok", app="RackStream")


@app.post("/api/preview")
def preview():
    """Use the same geometry rules for the browser and the STL."""
    return jsonify(calculate_layout(request.get_json()))


@app.post("/api/generate")
def generate():
    """Return a completed STL attachment; invalid dimensions never start a render."""
    layout = calculate_layout(request.get_json())
    if not RENDER_SLOTS.acquire(blocking=False):
        return jsonify(error="Both render slots are busy. Try again shortly."), 503
    try:
        data = render_stl(layout)
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        LOGGER.exception("STL generation failed")
        return jsonify(
            error="STL generation failed or timed out. Please retry or check server logs."
        ), 503
    finally:
        RENDER_SLOTS.release()
    LOGGER.info(
        "Generated %sU mount for %sx%sx%s mm body",
        layout["units"],
        layout["body_width"],
        layout["body_depth"],
        layout["body_height"],
    )
    return send_file(
        io.BytesIO(data),
        mimetype="model/stl",
        as_attachment=True,
        download_name=f"RackStream-{layout['units']}U.stl",
        max_age=0,
    )


@app.errorhandler(ValueError)
def invalid_dimensions(error):
    """Report actionable fit validation rather than an HTML error page."""
    return jsonify(error=str(error)), 400


@app.errorhandler(HTTPException)
def invalid_request(error):
    """Keep malformed JSON and oversized request errors consistent for the form."""
    return jsonify(error=error.description), error.code


@app.after_request
def security_headers(response):
    """This application needs no remote scripts, frames, or cross-origin APIs."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob:; connect-src 'self'; object-src 'none'; "
        "frame-ancestors 'none'; base-uri 'self'"
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(
        host=os.environ.get("RACKSTREAM_HOST", "127.0.0.1"),
        port=int(os.environ.get("RACKSTREAM_PORT", "8324")),
        debug=False,
    )
