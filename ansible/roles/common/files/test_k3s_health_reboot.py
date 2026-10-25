import importlib.util
import pathlib
import subprocess
from unittest import mock

import pytest

SPEC = importlib.util.spec_from_file_location("hr", pathlib.Path(__file__).with_name("k3s_health_reboot.py"))
hr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hr)

CFG = hr.Config(threshold=5, boot_grace_s=900, min_interval_s=3600, check_apiserver=False)


def decide(failures, uptime, since_last, healthy=False, cfg=CFG):
    return hr.decide(healthy=healthy, failures=failures, uptime_s=uptime, since_last_reboot_s=since_last, cfg=cfg)


def test_healthy_resets_and_never_reboots():
    assert decide(failures=99, uptime=10_000, since_last=None, healthy=True) == (0, False)


def test_counts_failures_below_threshold_without_rebooting():
    assert decide(failures=3, uptime=10_000, since_last=None) == (4, False)


def test_reboots_when_threshold_reached():
    assert decide(failures=4, uptime=10_000, since_last=None) == (5, True)


def test_no_reboot_during_boot_grace_period():
    assert decide(failures=10, uptime=600, since_last=None) == (11, False)


def test_no_reboot_within_minimum_interval_of_last_health_reboot():
    assert decide(failures=10, uptime=10_000, since_last=1_800) == (11, False)


def test_reboots_once_minimum_interval_has_passed():
    assert decide(failures=10, uptime=10_000, since_last=4_000) == (11, True)


def test_kubelet_check_uses_local_healthz():
    with mock.patch("urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.status = 200
        assert hr.kubelet_healthy() is True
    assert urlopen.call_args.args[0] == "http://127.0.0.1:10248/healthz"


def test_kubelet_check_fails_on_connection_error():
    with mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
        assert hr.kubelet_healthy() is False


def test_apiserver_check_fails_on_non_zero_exit():
    with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "timeout")):
        assert hr.apiserver_healthy() is False


def test_apiserver_check_fails_on_timeout():
    with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("k3s", 20)):
        assert hr.apiserver_healthy() is False


def test_apiserver_only_checked_when_enabled():
    with mock.patch.object(hr, "kubelet_healthy", return_value=True), \
         mock.patch.object(hr, "apiserver_healthy", return_value=False) as api:
        assert hr.node_healthy(hr.Config(5, 900, 3600, check_apiserver=False)) is True
        api.assert_not_called()
        assert hr.node_healthy(hr.Config(5, 900, 3600, check_apiserver=True)) is False


def test_run_persists_counter_and_reboots(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "STATE_DIR", tmp_path)
    monkeypatch.setattr(hr, "uptime_seconds", lambda: 10_000)
    monkeypatch.setattr(hr, "node_healthy", lambda cfg: False)
    (tmp_path / "failures").write_text("4")
    with mock.patch("subprocess.run") as run:
        hr.run(CFG)
    assert (tmp_path / "failures").read_text() == "0"
    assert (tmp_path / "last-reboot").exists()
    assert run.call_args.args[0] == ["systemctl", "reboot"]


def test_run_does_not_reboot_when_healthy(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "STATE_DIR", tmp_path)
    monkeypatch.setattr(hr, "uptime_seconds", lambda: 10_000)
    monkeypatch.setattr(hr, "node_healthy", lambda cfg: True)
    (tmp_path / "failures").write_text("4")
    with mock.patch("subprocess.run") as run:
        hr.run(CFG)
    assert (tmp_path / "failures").read_text() == "0"
    run.assert_not_called()
