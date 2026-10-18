deps:
	helm repo add trino https://trinodb.github.io/charts || true
	helm dependency update .

install:
	helm upgrade --install hc-trino . -n trino --create-namespace

uninstall:
	helm uninstall hc-trino -n trino
