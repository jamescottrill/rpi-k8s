deps:
	helm repo add minio https://charts.min.io/ || true
	helm dependency update .
install:
	helm upgrade --install hc-minio . -n minio --create-namespace -f iam.yaml
uninstall:
	helm uninstall hc-minio -n minio
