create-secret:
	kubectl create secret generic kxi-license --from-file=license=kc.lic -n kdb

docker-build:
	docker build -t kdb:latest -t docker.home.dev/kdb:latest .

docker-build-kic:
	DOCKER_BUILDKIT=0 docker build -t docker.home.dev/kdb-insights-core:latest . -f kic.Dockerfile
	docker push docker.home.internal/kdb-insights-core:latest

docker-push:
	docker push docker.home.dev/kdb:latest

install:
	helm upgrade --install hc-kdb . -n kdb --create-namespace
uninstall:
	helm uninstall hc-kdb -n kdb