import json
import stat
import subprocess
from unittest import mock

import pytest

import with_secret


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    path = tmp_path / "hc-vault" / "agent-token"
    monkeypatch.setattr(with_secret, "TOKEN_FILE", path)
    return path


@pytest.fixture
def stored_token(token_file):
    with_secret.save_token("s.agent")
    return token_file


def test_vault_passes_token_in_env_not_argv(monkeypatch):
    monkeypatch.setenv("VAULT_TOKEN", "s.ambient")
    with mock.patch("subprocess.run", return_value=completed("out")) as run:
        assert with_secret.vault(["kv", "get"], token="s.agent") == "out"
    assert "s.agent" not in " ".join(run.call_args.args[0])
    assert run.call_args.kwargs["env"]["VAULT_TOKEN"] == "s.agent"
    assert run.call_args.kwargs["env"]["VAULT_ADDR"] == with_secret.VAULT_ADDR


def test_vault_without_token_drops_any_ambient_token(monkeypatch):
    monkeypatch.setenv("VAULT_TOKEN", "s.ambient")
    with mock.patch("subprocess.run", return_value=completed()) as run:
        with_secret.vault(["login"])
    assert "VAULT_TOKEN" not in run.call_args.kwargs["env"]


def test_vault_hints_at_login_on_permission_denied():
    with mock.patch("subprocess.run", return_value=completed(returncode=2, stderr="Code: 403. permission denied")):
        with pytest.raises(with_secret.SecretError, match="login"):
            with_secret.vault(["kv", "get"], token="s.old")


def test_save_token_is_private(token_file):
    with_secret.save_token("s.agent")
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    assert with_secret.agent_token() == "s.agent"


def test_agent_token_missing_asks_for_login(token_file):
    with pytest.raises(with_secret.SecretError, match="login"):
        with_secret.agent_token()


@pytest.mark.parametrize("spec, expected", [
    ("CF=cloudflare#api_token", ("CF", "cloudflare", "api_token")),
    ("CF=/dns/cloudflare/#token", ("CF", "dns/cloudflare", "token")),
])
def test_parse_spec(spec, expected):
    assert with_secret.parse_spec(spec) == expected


@pytest.mark.parametrize("spec", ["cloudflare#api_token", "CF=cloudflare", "CF=#token", "1CF=cf#t", "CF-X=cf#t"])
def test_parse_spec_rejects_malformed(spec):
    with pytest.raises(with_secret.SecretError):
        with_secret.parse_spec(spec)


def test_run_puts_secret_in_child_env_only(stored_token, monkeypatch, capsys):
    monkeypatch.setenv("VAULT_TOKEN", "s.ambient")
    with mock.patch.object(with_secret, "vault", return_value="cf-secret\n") as vault, \
         mock.patch("os.execvpe") as execvpe:
        with_secret.main(["run", "CF=cloudflare#api_token", "--", "flarectl", "zone", "list"])
    vault.assert_called_once_with(["kv", "get", "-mount=secret", "-field=api_token", "agent/cloudflare"],
                                  token="s.agent")
    file, argv, env = execvpe.call_args.args
    assert (file, argv) == ("flarectl", ["flarectl", "zone", "list"])
    assert env["CF"] == "cf-secret"
    assert "VAULT_TOKEN" not in env
    assert "cf-secret" not in capsys.readouterr().out


def test_run_without_command_fails(stored_token):
    with mock.patch("os.execvpe") as execvpe, pytest.raises(SystemExit, match="Nothing to run"):
        with_secret.main(["run", "CF=cloudflare#api_token"])
    execvpe.assert_not_called()


def test_fields_prints_names_not_values(stored_token, capsys):
    secret = {"data": {"data": {"zone_id": "z-123", "api_token": "cf-secret"}}}
    with mock.patch.object(with_secret, "vault", return_value=json.dumps(secret)):
        with_secret.main(["fields", "cloudflare"])
    out = capsys.readouterr().out
    assert out.split() == ["api_token", "zone_id"]
    assert "cf-secret" not in out and "z-123" not in out


def test_login_mints_agent_token_and_revokes_admin_token(token_file, capsys):
    calls = []

    def fake_vault(args, token=None):
        calls.append((args, token))
        if args[0] == "login":
            return "s.admin\n"
        if args[:2] == ["token", "create"]:
            return "s.agent\n"
        if args[:2] == ["token", "lookup"]:
            return json.dumps({"data": {"policies": ["agent-read"], "expire_time": "later"}})
        return ""

    with mock.patch.object(with_secret, "vault", side_effect=fake_vault):
        with_secret.main(["login"])
    assert (["token", "create", "-role=agent", "-field=token"], "s.admin") in calls
    assert (["token", "revoke", "-self"], "s.admin") in calls
    assert token_file.read_text() == "s.agent"
    out = capsys.readouterr().out
    assert "s.agent" not in out and "s.admin" not in out


def test_login_revokes_admin_token_even_if_minting_fails(token_file):
    def fake_vault(args, token=None):
        if args[0] == "login":
            return "s.admin"
        if args[:2] == ["token", "create"]:
            raise with_secret.SecretError("role not found")
        return ""

    with mock.patch.object(with_secret, "vault", side_effect=fake_vault) as vault, \
         pytest.raises(SystemExit, match="role not found"):
        with_secret.main(["login"])
    assert mock.call(["token", "revoke", "-self"], token="s.admin") in vault.call_args_list
    assert not token_file.exists()
