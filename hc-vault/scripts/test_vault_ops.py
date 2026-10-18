import json
import stat
import subprocess
from unittest import mock

import pytest

import vault_ops


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def init_file(tmp_path, monkeypatch):
    path = tmp_path / ".dev" / "init.json"
    monkeypatch.setattr(vault_ops, "INIT_FILE", path)
    return path


def test_vault_without_token_runs_vault_directly():
    with mock.patch("subprocess.run", return_value=completed("out")) as run:
        assert vault_ops.vault(["status"]) == "out"
    cmd = run.call_args.args[0]
    assert cmd[-2:] == ["vault", "status"]
    assert run.call_args.kwargs["input"] == ""


def test_vault_with_token_keeps_secrets_out_of_argv():
    with mock.patch("subprocess.run", return_value=completed()) as run:
        vault_ops.vault(["kv", "put", "secret/x", "-"], token="s.root", stdin='{"k":"v"}')
    cmd = run.call_args.args[0]
    assert "s.root" not in " ".join(cmd)
    assert "v" not in cmd
    assert run.call_args.kwargs["input"] == 's.root\n{"k":"v"}'


def test_vault_raises_with_stderr_on_failure():
    with mock.patch("subprocess.run", return_value=completed(returncode=1, stderr="permission denied")):
        with pytest.raises(vault_ops.VaultError, match="permission denied"):
            vault_ops.vault(["policy", "write"])


def test_status_maps_sealed_exit_code_inside_the_pod():
    with mock.patch("subprocess.run", return_value=completed('{"sealed": true}')) as run:
        assert vault_ops.status() == {"sealed": True}
    assert run.call_args.args[0][-1] == "vault status -format=json || [ $? -eq 2 ]"


def test_status_raises_on_other_failures():
    with mock.patch("subprocess.run", return_value=completed(returncode=1, stderr="connection refused")):
        with pytest.raises(vault_ops.VaultError, match="connection refused"):
            vault_ops.status()


def test_init_writes_file_with_0600_and_does_not_print_secrets(init_file, capsys):
    output = json.dumps({"unseal_keys_b64": ["k1"], "root_token": "s.root"})
    with mock.patch.object(vault_ops, "status", return_value={"initialized": False}), \
         mock.patch.object(vault_ops, "vault", return_value=output):
        vault_ops.cmd_init(None)
    assert json.loads(init_file.read_text())["root_token"] == "s.root"
    assert stat.S_IMODE(init_file.stat().st_mode) == 0o600
    printed = capsys.readouterr().out
    assert "s.root" not in printed and "k1" not in printed


def test_init_refuses_when_already_initialised(init_file):
    with mock.patch.object(vault_ops, "status", return_value={"initialized": True}), \
         mock.patch.object(vault_ops, "vault") as vault:
        with pytest.raises(SystemExit):
            vault_ops.cmd_init(None)
    vault.assert_not_called()


def test_init_refuses_to_overwrite_existing_file(init_file):
    init_file.parent.mkdir()
    init_file.write_text("{}")
    with mock.patch.object(vault_ops, "status", return_value={"initialized": False}):
        with pytest.raises(SystemExit):
            vault_ops.cmd_init(None)


def test_unseal_uses_saved_keys_until_unsealed(init_file):
    init_file.parent.mkdir()
    init_file.write_text(json.dumps({"unseal_keys_b64": ["k1", "k2", "k3", "k4", "k5"], "root_token": "t"}))
    states = iter([{"sealed": True}, {"sealed": True}, {"sealed": False}, {"sealed": False}])
    with mock.patch.object(vault_ops, "status", side_effect=lambda: next(states)), \
         mock.patch.object(vault_ops, "vault") as vault:
        vault_ops.cmd_unseal(None)
    assert [c.kwargs["stdin"] for c in vault.call_args_list] == ["k1", "k2"]
    # `vault operator unseal -` treats "-" as the key itself; only `write key=-` reads stdin.
    assert vault.call_args.args[0] == ["write", "-format=json", "sys/unseal", "key=-"]


def test_unseal_prompts_when_init_file_removed(init_file):
    states = iter([{"sealed": True}] * 3 + [{"sealed": False}])
    with mock.patch.object(vault_ops, "status", side_effect=lambda: next(states)), \
         mock.patch.object(vault_ops, "vault") as vault, \
         mock.patch("getpass.getpass", side_effect=["a", "b", "c"]):
        vault_ops.cmd_unseal(None)
    assert [c.kwargs["stdin"] for c in vault.call_args_list] == ["a", "b", "c"]


def test_configure_skips_enabling_existing_mounts(init_file):
    init_file.parent.mkdir()
    init_file.write_text(json.dumps({"unseal_keys_b64": [], "root_token": "t"}))
    responses = {
        ("secrets", "list"): json.dumps({"secret/": {}}),
        ("auth", "list"): json.dumps({"kubernetes/": {}}),
    }
    calls = []

    def fake_vault(args, token=None, stdin=""):
        calls.append(args)
        return responses.get(tuple(args[:2]), "")

    with mock.patch.object(vault_ops, "vault", side_effect=fake_vault), \
         mock.patch.object(vault_ops, "configure_oidc") as configure_oidc:
        vault_ops.cmd_configure(None)
    configure_oidc.assert_called_once_with("t")
    assert ["secrets", "enable", "-path=secret", "kv-v2"] not in calls
    assert ["auth", "enable", "kubernetes"] not in calls
    assert any(c[:2] == ["write", "auth/kubernetes/role/external-secrets"] for c in calls)


def test_put_secret_sends_values_on_stdin():
    with mock.patch.object(vault_ops, "vault") as vault:
        vault_ops.put_secret("app/creds", {"password": "hunter2"}, token="t")
    args = vault.call_args.args[0]
    assert args == ["kv", "put", "secret/app/creds", "-"]
    assert "hunter2" not in " ".join(args)
    assert json.loads(vault.call_args.kwargs["stdin"]) == {"password": "hunter2"}


class FakeVault:
    """Records vault calls and answers list/read commands from in-memory state."""

    def __init__(self, auths=None, groups=None, aliases=None):
        self.calls = []
        self.auths = auths if auths is not None else {"token/": {}}
        self.groups = groups if groups is not None else {}
        self.aliases = aliases if aliases is not None else []

    def __call__(self, args, token=None, stdin=""):
        self.calls.append((args, stdin))
        if args[:2] == ["auth", "enable"]:
            self.auths[f"{args[2]}/"] = {}
        if args[:2] == ["auth", "list"]:
            return json.dumps({k: {"accessor": f"auth_{k.rstrip('/')}_123"} for k in self.auths})
        if args[:2] == ["kv", "get"]:
            return "kc-client-secret"
        if args[:3] == ["write", "-format=json", "identity/lookup/group"]:
            # Real Vault: exit 0 with empty output when the group does not exist.
            name = args[3].split("=", 1)[1]
            if name not in self.groups:
                return ""
            return json.dumps({"data": {"id": self.groups[name], "alias": {"name": name} if name in self.aliases else {}}})
        if args[:2] == ["write", "-format=json"] and args[2] == "identity/group":
            return json.dumps({"data": {"id": "new-group-id"}})
        return ""

    def commands(self):
        return [args for args, _ in self.calls]


def test_configure_oidc_on_fresh_vault_creates_everything():
    fake = FakeVault()
    with mock.patch.object(vault_ops, "vault", side_effect=fake):
        vault_ops.configure_oidc("t")
    cmds = fake.commands()
    assert ["auth", "enable", "oidc"] in cmds
    assert any(c[:2] == ["write", "-format=json"] and c[2] == "identity/group" for c in cmds)
    assert any(c[:2] == ["write", "identity/group-alias"] for c in cmds)
    assert ["policy", "write", vault_ops.ADMIN_POLICY, "-"] in cmds


def test_configure_oidc_is_idempotent_when_already_configured():
    fake = FakeVault(auths={"token/": {}, "oidc/": {}}, groups={"admins": "gid-1"}, aliases=["admins"])
    with mock.patch.object(vault_ops, "vault", side_effect=fake):
        vault_ops.configure_oidc("t")
    cmds = fake.commands()
    assert ["auth", "enable", "oidc"] not in cmds
    assert not any(c[:2] == ["write", "-format=json"] and c[2] == "identity/group" for c in cmds)
    assert not any(c[:2] == ["write", "identity/group-alias"] for c in cmds)


def test_configure_oidc_adds_missing_alias_to_existing_group():
    fake = FakeVault(auths={"token/": {}, "oidc/": {}}, groups={"admins": "gid-1"})
    with mock.patch.object(vault_ops, "vault", side_effect=fake):
        vault_ops.configure_oidc("t")
    alias = [c for c in fake.commands() if c[:2] == ["write", "identity/group-alias"]]
    assert alias and "canonical_id=gid-1" in alias[0] and "mount_accessor=auth_oidc_123" in alias[0]


def test_configure_oidc_keeps_client_secret_out_of_argv():
    fake = FakeVault()
    with mock.patch.object(vault_ops, "vault", side_effect=fake):
        vault_ops.configure_oidc("t")
    assert all("kc-client-secret" not in " ".join(args) for args, _ in fake.calls)
    config = [stdin for args, stdin in fake.calls if args[:2] == ["write", "auth/oidc/config"]]
    assert config and json.loads(config[0])["oidc_client_secret"] == "kc-client-secret"


def test_kubectl_is_pinned_to_kube_context_when_set(monkeypatch):
    monkeypatch.setattr(vault_ops, "KUBE_CONTEXT", "rpi")
    with mock.patch("subprocess.run", return_value=completed("{}")) as run:
        vault_ops.status()
    assert run.call_args.args[0][:3] == ["kubectl", "--context", "rpi"]


def test_kubectl_uses_current_context_when_unset(monkeypatch):
    monkeypatch.setattr(vault_ops, "KUBE_CONTEXT", None)
    with mock.patch("subprocess.run", return_value=completed("{}")) as run:
        vault_ops.status()
    assert run.call_args.args[0][:2] == ["kubectl", "exec"]
