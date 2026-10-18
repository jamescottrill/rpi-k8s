"""Initialise, unseal and configure the in-cluster Vault.

Every secret (unseal keys, root token, KV data) is sent to the Vault pod on
stdin, so none of it appears in process arguments or terminal output.
`vault operator init` writes its output to `.dev/init.json` (gitignored,
mode 0600); once the keys are copied into a password manager and that file is
deleted, `unseal` and `configure` fall back to hidden prompts.
"""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

NAMESPACE = "vault"
POD = "hc-vault-0"
INIT_FILE = Path(__file__).resolve().parent.parent / ".dev" / "init.json"
KEY_SHARES = 5
KEY_THRESHOLD = 3

ESO_SERVICE_ACCOUNT = "hc-external-secrets"
ESO_NAMESPACE = "external-secrets"
ESO_ROLE = "external-secrets"
ESO_POLICY = "external-secrets-read"
ESO_POLICY_HCL = """\
path "secret/data/*" {
  capabilities = ["read"]
}
path "secret/metadata/*" {
  capabilities = ["read", "list"]
}
"""

# Reads the token from the first stdin line, so whatever follows on stdin is
# still available to the vault command (e.g. a policy or KV JSON body).
_WITH_TOKEN = 'read -r VAULT_TOKEN; export VAULT_TOKEN; exec vault "$@"'


class VaultError(RuntimeError):
    """A vault CLI call inside the pod exited non-zero."""


def vault(args: list[str], token: str | None = None, stdin: str = "") -> str:
    """Run `vault <args>` in the Vault pod and return its stdout.

    When `token` is given it is passed on the first stdin line, ahead of
    `stdin`. Raises VaultError carrying vault's stderr on failure.
    """
    cmd = ["kubectl", "exec", "-i", "-n", NAMESPACE, POD, "--"]
    if token is None:
        cmd += ["vault", *args]
        payload = stdin
    else:
        cmd += ["sh", "-c", _WITH_TOKEN, "sh", *args]
        payload = f"{token}\n{stdin}"
    result = subprocess.run(cmd, input=payload, capture_output=True, text=True)
    if result.returncode != 0:
        raise VaultError(f"vault {args[0]} {args[1] if len(args) > 1 else ''} failed: {result.stderr.strip()}")
    return result.stdout


def status() -> dict:
    """Return `vault status` as a dict.

    `vault status` exits 2 when sealed. kubectl exec collapses every non-zero
    exit to 1, so the sealed case is mapped to success inside the pod instead.
    """
    cmd = ["kubectl", "exec", "-n", NAMESPACE, POD, "--", "sh", "-c", "vault status -format=json || [ $? -eq 2 ]"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VaultError(f"vault status failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def load_init() -> dict | None:
    """Return the saved init output, or None once it has been moved off disk."""
    if INIT_FILE.exists():
        return json.loads(INIT_FILE.read_text())
    return None


def root_token() -> str:
    init = load_init()
    if init:
        return init["root_token"]
    return getpass.getpass("Vault token: ")


def cmd_init(_: argparse.Namespace) -> None:
    if status()["initialized"]:
        sys.exit("Vault is already initialised; refusing to re-initialise.")
    if INIT_FILE.exists():
        sys.exit(f"{INIT_FILE} already exists; refusing to overwrite it.")
    output = vault(["operator", "init", f"-key-shares={KEY_SHARES}", f"-key-threshold={KEY_THRESHOLD}", "-format=json"])
    INIT_FILE.parent.mkdir(exist_ok=True)
    # Create with 0600 from the start rather than chmod-ing after the write.
    fd = os.open(INIT_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(output)
    print(f"Initialised. Unseal keys and root token written to {INIT_FILE} (not printed).")


def cmd_unseal(_: argparse.Namespace) -> None:
    init = load_init()
    keys = init["unseal_keys_b64"][:KEY_THRESHOLD] if init else None
    for i in range(KEY_THRESHOLD):
        if not status()["sealed"]:
            break
        key = keys[i] if keys else getpass.getpass(f"Unseal key {i + 1}/{KEY_THRESHOLD}: ")
        vault(["write", "-format=json", "sys/unseal", "key=-"], stdin=key)
    print("Sealed." if status()["sealed"] else "Unsealed.")


def cmd_configure(_: argparse.Namespace) -> None:
    token = root_token()

    mounts = json.loads(vault(["secrets", "list", "-format=json"], token=token))
    if "secret/" not in mounts:
        vault(["secrets", "enable", "-path=secret", "kv-v2"], token=token)

    auths = json.loads(vault(["auth", "list", "-format=json"], token=token))
    if "kubernetes/" not in auths:
        vault(["auth", "enable", "kubernetes"], token=token)
    # Vault validates service-account JWTs with its own pod token (TokenReview),
    # which the chart's auth-delegator ClusterRoleBinding permits.
    vault(["write", "auth/kubernetes/config", "kubernetes_host=https://kubernetes.default.svc"], token=token)

    vault(["policy", "write", ESO_POLICY, "-"], token=token, stdin=ESO_POLICY_HCL)
    vault(
        [
            "write",
            f"auth/kubernetes/role/{ESO_ROLE}",
            f"bound_service_account_names={ESO_SERVICE_ACCOUNT}",
            f"bound_service_account_namespaces={ESO_NAMESPACE}",
            f"policies={ESO_POLICY}",
            "audience=vault",
            "ttl=1h",
        ],
        token=token,
    )
    print("Configured kv-v2 at secret/, kubernetes auth, and the external-secrets role.")


def put_secret(path: str, data: dict[str, str], token: str) -> None:
    """Write `data` to KV v2 at secret/<path>, sending the values on stdin."""
    vault(["kv", "put", f"secret/{path}", "-"], token=token, stdin=json.dumps(data))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)
    for name, func in (("init", cmd_init), ("unseal", cmd_unseal), ("configure", cmd_configure)):
        sub.add_parser(name).set_defaults(func=func)
    args = parser.parse_args()
    try:
        args.func(args)
    except VaultError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
