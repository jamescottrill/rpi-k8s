deps:
	helm repo add kyverno https://kyverno.github.io/kyverno/ || true
	helm dependency update .
install:
	helm upgrade --install hc-kyverno . -n kyverno --create-namespace
uninstall:
	helm uninstall hc-kyverno -n kyverno
test:
	kyverno test tests/
