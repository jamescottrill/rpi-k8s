"""Run a command with secrets from Vault in its environment, without printing them.

Intended for agents such as Claude Code, which can then use a credential without its value
ever reaching their output. Agents may only read secret/agent/*, through a short-lived token
minted from an admin's Keycloak login:

  with_secret.py login                       # opens the browser; stores an 8h read-only token
  with_secret.py list                        # names under secret/agent/
  with_secret.py fields cloudflare           # field names of secret/agent/cloudflare
  with_secret.py run CLOUDFLARE_API_TOKEN=cloudflare#api_token -- flarectl zone list

The command runs with the secret as an environment variable. A shell is only needed when the
value goes into an argument, and the variable must then be expanded by that inner shell:

  with_secret.py run CF=cloudflare#api_token -- \\
      sh -c 'curl -sH "Authorization: Bearer $CF" https://api.cloudflare.com/client/v4/user/tokens/verify'

This keeps secrets out of transcripts; it is not a sandbox, since the command itself could
still print what it is given.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

VAULT_ADDR = os.environ.get("VAULT_ADDR", "https://vault.panga-degree.ts.net")
MOUNT = "secret"
PREFIX = "agent"
TOKEN_ROLE = "agent"
TOKEN_FILE = Path.home() / ".config" / "hc-vault" / "agent-token"


class SecretError(RuntimeError):
    """A Vault call failed or the agent token is missing or expired."""


def vault(args: list[str], token: str | None = None) -> str:
    """Run the local vault CLI against VAULT_ADDR and return its stdout.

    The token goes in the child's environment only, so it never appears in argv and the
    command that `run` executes does not inherit it.
    """
    env = {**os.environ, "VAULT_ADDR": VAULT_ADDR}
    env.pop("VAULT_TOKEN", None)
    if token is not None:
        env["VAULT_TOKEN"] = token
    result = subprocess.run(["vault", *args], env=env, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip()
        if "permission denied" in detail or "missing client token" in detail:
            detail += f"\nThe agent token may have expired; run `{Path(__file__).name} login`."
        raise SecretError(f"vault {' '.join(args[:2])} failed: {detail}")
    return result.stdout


def agent_token() -> str:
    if not TOKEN_FILE.exists():
        raise SecretError(f"No agent token at {TOKEN_FILE}; run `{Path(__file__).name} login`.")
    return TOKEN_FILE.read_text().strip()


def save_token(token: str) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # O_CREAT with 0600 so the file is never readable by others, even briefly
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(token)
    os.chmod(TOKEN_FILE, 0o600)


def parse_spec(spec: str) -> tuple[str, str, str]:
    """Split VAR=path#field into its parts, rejecting anything malformed."""
    var, sep, ref = spec.partition("=")
    path, hash_, field = ref.partition("#")
    if not (sep and hash_ and var and path and field) or not var.isidentifier():
        raise SecretError(f"Expected VAR=path#field, got {spec!r}")
    return var, path.strip("/"), field


def read_field(path: str, field: str, token: str) -> str:
    # The CLI adds a newline when writing a field, which is not part of the value
    return vault(["kv", "get", f"-mount={MOUNT}", f"-field={field}", f"{PREFIX}/{path}"], token=token).rstrip("\n")


def cmd_login(_: argparse.Namespace) -> None:
    # The admin token stays in memory and is revoked once the agent token exists
    admin = vault(["login", "-method=oidc", "-no-store", "-token-only"]).strip()
    try:
        token = vault(["token", "create", f"-role={TOKEN_ROLE}", "-field=token"], token=admin).strip()
    finally:
        vault(["token", "revoke", "-self"], token=admin)
    save_token(token)
    info = json.loads(vault(["token", "lookup", "-format=json"], token=token))["data"]
    print(f"Stored an agent token in {TOKEN_FILE}; policies={info['policies']}, expires {info['expire_time']}.")


def cmd_list(_: argparse.Namespace) -> None:
    print(vault(["kv", "list", f"-mount={MOUNT}", PREFIX], token=agent_token()), end="")


def cmd_fields(args: argparse.Namespace) -> None:
    secret = json.loads(vault(["kv", "get", f"-mount={MOUNT}", "-format=json", f"{PREFIX}/{args.path.strip('/')}"],
                              token=agent_token()))
    print("\n".join(sorted(secret["data"]["data"])))


def cmd_run(args: argparse.Namespace) -> None:
    if not args.command:
        raise SecretError("Nothing to run; put the command after --")
    token = agent_token()
    env = {k: v for k, v in os.environ.items() if k != "VAULT_TOKEN"}
    for spec in args.secrets:
        var, path, field = parse_spec(spec)
        env[var] = read_field(path, field, token)
    os.execvpe(args.command[0], args.command, env)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(required=True)
    sub.add_parser("login").set_defaults(func=cmd_login)
    sub.add_parser("list").set_defaults(func=cmd_list)
    fields = sub.add_parser("fields")
    fields.add_argument("path")
    fields.set_defaults(func=cmd_fields)
    run = sub.add_parser("run")
    run.add_argument("secrets", nargs="+", metavar="VAR=path#field")
    run.set_defaults(func=cmd_run)

    argv = sys.argv[1:] if argv is None else argv
    # argparse cannot split two variadic positionals, so the command after -- is cut off by hand
    command = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    args = parser.parse_args(argv)
    args.command = command
    try:
        args.func(args)
    except SecretError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
