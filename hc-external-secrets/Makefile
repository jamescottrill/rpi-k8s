deps:
	helm repo add external-secrets https://charts.external-secrets.io || true
	helm dependency update .
install:
	helm upgrade --install hc-external-secrets . -n external-secrets --create-namespace
uninstall:
	helm uninstall hc-external-secrets -n external-secrets
