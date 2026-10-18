deps:
	helm repo add hashicorp https://helm.releases.hashicorp.com || true
	helm dependency update .
install:
	helm upgrade --install hc-vault . -n vault --create-namespace
uninstall:
	helm uninstall hc-vault -n vault
init:
	python3 scripts/vault_ops.py init
unseal:
	python3 scripts/vault_ops.py unseal
configure:
	python3 scripts/vault_ops.py configure
test:
	python3 -m pytest -q -p no:cacheprovider scripts
