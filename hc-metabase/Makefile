deps:
	helm repo add pmint93 https://pmint93.github.io/helm-charts || true
	helm dependency update .

install:
	helm upgrade --install hc-metabase . -n metabase --create-namespace

uninstall:
	helm uninstall hc-metabase -n metabase
