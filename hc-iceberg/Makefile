docker-build:
	docker build --platform linux/arm64 -t iceberg-writer:latest -t docker.home.dev/iceberg-writer:latest writer/

docker-push:
	docker push docker.home.dev/iceberg-writer:latest

install:
	helm upgrade --install hc-iceberg . -n iceberg --create-namespace