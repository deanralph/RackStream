# AppStream deployment

RackStream runs on **AppStream (10.0.0.100)** at **http://10.0.0.100:8324**. It is LAN-only: no Cloudflare tunnel or public hostname was configured. There is no application authentication, so keep it on a trusted network.

## Layout

- Account: `dean`, rootless Podman.
- Source/build context: `/home/dean/RackStream`.
- Image: `localhost/rackstream:local`.
- Container: `rackstream`.
- User systemd unit: `container-rackstream.service`.
- Installed unit: `/home/dean/.config/systemd/user/container-rackstream.service`.
- Container process: non-root UID/GID `10001:10001`, running Waitress.
- Runtime dependencies: Python 3.14 and Debian's packaged OpenSCAD 2021.01, with Qt's offscreen platform.

The app has no database or persistent user data. Completed STL downloads go to the browser; temporary render directories are deleted after each request. The image contains an explicit application-file allowlist, not Git metadata, examples, documentation or environment files.

## Build

Run as `dean` on AppStream after transferring the source, Containerfile and `.containerignore`:

```sh
cd /home/dean/RackStream
podman build --format docker --tag localhost/rackstream:local --file Containerfile .
```

**Keep `--format docker`:** Podman's default OCI image format ignores the Containerfile's `HEALTHCHECK`. Verify the built image retains it:

```sh
podman image inspect localhost/rackstream:local --format '{{json .Config.Healthcheck}}'
```

The health check tests the HTTP server, not the renderer; also exercise a real STL export after every deployment.

## Install the service

This follows AppStream's existing generated-systemd-unit convention. The provided `container-rackstream.service` is the tested unit for this host. Podman now recommends Quadlet for new setups; this service remains deliberately aligned with the current host convention.

For a **first installation only**, with no existing RackStream container/unit:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/container-rackstream.service ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger dean
systemctl --user enable --now container-rackstream.service
```

Lingering allows the user manager to start at boot and remain running without an SSH session. The unit is enabled under `default.target`, uses `Restart=always` with a five-second delay, and recreates its container from `localhost/rackstream:local`. Startup rate limiting is disabled for this service so an early boot attempt before the LAN address is available does not permanently fail the unit. A failed health check kills the container so systemd can restart it.

To regenerate rather than copy the unit, first create a **stopped** template container with the exact run options below, run `podman generate systemd --new --files --name --restart-policy always --time 30 rackstream`, remove only that template container, and install the generated unit. Preserve `StartLimitIntervalSec=0` in `[Unit]` and `RestartSec=5` in `[Service]` when regenerating. Do not create a second running container on the service's name or port.

```sh
podman create --name rackstream \
  --publish 10.0.0.100:8324:8324 \
  --read-only \
  --tmpfs /work/render-tmp:rw,size=512m,mode=1777 \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --memory 1g \
  --pids-limit 256 \
  --health-on-failure kill \
  localhost/rackstream:local
```

The tmpfs has a sticky writable parent so the non-root application user can create private job directories. Each render's TemporaryDirectory is private and is removed on completion. This Podman host rejects `uid=`/`gid=` options on `--tmpfs`; do not substitute them for the tested mode.

**CPU quotas are intentionally absent:** AppStream's rootless cgroup subtree does not expose the CPU controller. Adding `--cpus` prevents the container from starting. The 1 GiB memory limit, 256-process limit, two-render concurrency cap and 90-second per-render timeout remain enforced. No host-wide cgroup/security configuration was weakened to make it start.

## Operations

Run these on AppStream as `dean`:

```sh
systemctl --user status container-rackstream.service
systemctl --user restart container-rackstream.service
podman ps --filter name=rackstream
podman logs --tail 100 rackstream
podman healthcheck run rackstream
loginctl show-user dean -p Linger
```

For a source update, transfer only the intended project files, rebuild the image with `--format docker`, and restart the service. There are no host bind mounts; editing the source directory does **not** update the running image. Rebuilding the same tag does not replace an already running container until the service restarts.

To stop and prevent automatic startup without deleting source or images:

```sh
systemctl --user disable --now container-rackstream.service
```

No firewall rule was changed during promotion: firewalld was inactive, and LAN access to the selected port was verified. Do not treat a private bind address as a substitute for network access controls if the network or routing changes.

## Promotion verification

The deployed service was checked from another LAN machine, not only from inside the container:

- `/health` returned `status=ok`; Podman reported the container healthy.
- Served JavaScript matched the development source hash.
- The browser calculated the default 1U layout and the actual Generate STL button downloaded a file.
- Actual 1U, 2U and 3U exports were loaded with trimesh: each had positive volume, was watertight, was one connected component, and matched the expected outer dimensions.
- Invalid rack width was rejected with HTTP 400.
- No completed render job directories remained.
- A simulated container crash was recovered automatically by systemd; the replacement container had a new ID and served requests again.
- Service enablement and `Linger=yes` were read back. **The shared AppStream host was not rebooted** as part of verification.

The deployed application source was the initial `1ff52b3` revision plus the local deployment configuration. No application logic changed for containerisation. `DEPLOYED_SOURCE.json` on AppStream records the deployed source file hashes; it is operational metadata, not a credential.
