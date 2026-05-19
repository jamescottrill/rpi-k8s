deps:
	helm repo add minio https://charts.min.io/ || true
	helm dependency update .
install: deps
	helm upgrade --install hc-minio . -n minio --create-namespace
uninstall:
	helm uninstall hc-minio -n minio
