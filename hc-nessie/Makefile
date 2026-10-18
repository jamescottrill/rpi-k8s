deps:
	helm repo add nessie https://charts.projectnessie.org || true
	helm dependency update .

install:
	helm upgrade --install hc-nessie . -n nessie --create-namespace

uninstall:
	helm uninstall hc-nessie -n nessie
