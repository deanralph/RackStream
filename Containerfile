FROM docker.io/library/python:3.14-slim-bookworm

# Debian's packaged OpenSCAD includes its Qt/CGAL runtime; no AppImage or GPU
# is required for headless STL export. Keep build tools out of the image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openscad fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 rackstream \
    && useradd --uid 10001 --gid rackstream --create-home rackstream \
    && mkdir -p /work/render-tmp \
    && chown rackstream:rackstream /work/render-tmp

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen \
    OPENSCAD_BIN=/usr/bin/openscad \
    TMPDIR=/work/render-tmp

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Explicit allowlist: documentation, examples, tests, git metadata and any
# developer environment files cannot accidentally end up in the image.
COPY app.py rackstream.py ./
COPY scad/ ./scad/
COPY static/ ./static/
COPY templates/ ./templates/

USER 10001:10001
EXPOSE 8324
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import json, urllib.request; result=json.load(urllib.request.urlopen('http://127.0.0.1:8324/health', timeout=3)); assert result.get('status') == 'ok'"

CMD ["waitress-serve", "--listen=0.0.0.0:8324", "--threads=4", "app:app"]
