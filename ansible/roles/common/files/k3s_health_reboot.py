#!/usr/bin/env python3
"""Reboot this node if k3s stays unhealthy, run once a minute by a systemd timer.

The hardware watchdog only catches a hung kernel or systemd. This catches the
case where the OS is alive but k3s is wedged (e.g. an etcd stall on the server).
It reboots after `threshold` consecutive failed checks, but never during the
boot grace period and at most once per `min_interval_s`, so a node that cannot
recover does not reboot-loop.
"""

import argparse
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

STATE_DIR = Path("/var/lib/k3s-health")
KUBELET_HEALTHZ = "http://127.0.0.1:10248/healthz"


@dataclass(frozen=True)
class Config:
    threshold: int
    boot_grace_s: int
    min_interval_s: int
    check_apiserver: bool


def kubelet_healthy() -> bool:
    try:
        with urllib.request.urlopen(KUBELET_HEALTHZ, timeout=10) as response:
            return response.status == 200
    except OSError:
        return False


def apiserver_healthy() -> bool:
    """Server nodes only: ask the local API server (and so etcd) whether it is ready."""
    try:
        result = subprocess.run(
            ["k3s", "kubectl", "get", "--raw=/readyz", "--request-timeout=15s"],
            capture_output=True, text=True, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def node_healthy(cfg: Config) -> bool:
    if not kubelet_healthy():
        return False
    return apiserver_healthy() if cfg.check_apiserver else True


def decide(healthy: bool, failures: int, uptime_s: float, since_last_reboot_s: float | None,
           cfg: Config) -> tuple[int, bool]:
    """Return (new consecutive-failure count, whether to reboot now)."""
    if healthy:
        return 0, False
    failures += 1
    in_boot_grace = uptime_s < cfg.boot_grace_s
    rebooted_recently = since_last_reboot_s is not None and since_last_reboot_s < cfg.min_interval_s
    return failures, failures >= cfg.threshold and not in_boot_grace and not rebooted_recently


def uptime_seconds() -> float:
    return float(Path("/proc/uptime").read_text().split()[0])


def run(cfg: Config) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    failures_file = STATE_DIR / "failures"
    last_reboot_file = STATE_DIR / "last-reboot"

    failures = int(failures_file.read_text() or 0) if failures_file.exists() else 0
    since_last = time.time() - last_reboot_file.stat().st_mtime if last_reboot_file.exists() else None

    healthy = node_healthy(cfg)
    failures, reboot = decide(healthy, failures, uptime_seconds(), since_last, cfg)

    if reboot:
        print(f"k3s unhealthy for {failures} consecutive checks; rebooting", file=sys.stderr)
        failures_file.write_text("0")
        last_reboot_file.touch()
        subprocess.run(["systemctl", "reboot"], check=False)
        return
    failures_file.write_text(str(failures))
    if not healthy:
        print(f"k3s unhealthy ({failures}/{cfg.threshold} consecutive checks)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=int, default=5)
    parser.add_argument("--boot-grace", type=int, default=900, help="seconds after boot to never reboot")
    parser.add_argument("--min-interval", type=int, default=3600, help="minimum seconds between health reboots")
    parser.add_argument("--check-apiserver", action="store_true", help="also check the local API server (servers)")
    args = parser.parse_args()
    run(Config(args.threshold, args.boot_grace, args.min_interval, args.check_apiserver))


if __name__ == "__main__":
    main()
